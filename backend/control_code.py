"""Bounded YAML configuration, never authority to activate a control."""

import hashlib
import json
from typing import Literal

import yaml
from pydantic import Field, model_validator

from models import Input
from operations import Operations, audit, canonical
from product_models import RuleInput
from providers import problem
from store import now

MAX_BYTES = 256_000


class ControlLoader(yaml.SafeLoader):
    """Safe constructors plus bounds and rejection of ambiguous/reused nodes."""

    def __init__(self, stream):
        super().__init__(stream)
        self.node_count = 0
        self.node_depth = 0

    def compose_node(self, parent, index):
        event = self.peek_event()
        if isinstance(event, yaml.AliasEvent) or getattr(event, "anchor", None):
            raise ValueError("YAML anchors and aliases are not supported.")
        self.node_count += 1
        self.node_depth += 1
        if self.node_count > 20000 or self.node_depth > 16:
            raise ValueError("YAML nesting/node count exceeds the import bound.")
        try:
            return super().compose_node(parent, index)
        finally:
            self.node_depth -= 1

    def construct_mapping(self, node, deep=False):
        result = {}
        if not isinstance(node, yaml.MappingNode):
            raise ValueError("Expected a YAML mapping.")
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or key in result:
                raise ValueError("YAML keys must be unique strings.")
            result[key] = self.construct_object(value_node, deep=deep)
        return result


class PolicyPin(Input):
    id: str = Field(min_length=1, max_length=100)
    version: str = Field(min_length=1, max_length=30)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ParentPin(Input):
    id: str = Field(min_length=1, max_length=100)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class CodeControl(Input):
    key: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,99}$")
    policy: PolicyPin
    replaces: ParentPin | None = None
    configuration: RuleInput

    @model_validator(mode="after")
    def matching_policy(self):
        if self.policy.id != self.configuration.policy_id:
            raise ValueError("The policy pin must match configuration.policy_id.")
        return self


class CodeDocument(Input):
    schema_version: Literal["policylens.controls.v1"]
    workspace_id: str = Field(min_length=1, max_length=100)
    controls: list[CodeControl] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique_keys(self):
        if len({c.key for c in self.controls}) != len(self.controls):
            raise ValueError("Control keys must be unique in a document.")
        parents = [c.replaces.id for c in self.controls if c.replaces]
        if len(parents) != len(set(parents)):
            raise ValueError("Do not replace the same control twice in one import.")
        return self


class CodeRequest(Input):
    model_config = {"str_strip_whitespace": False, "extra": "forbid"}
    yaml: str = Field(min_length=1, max_length=MAX_BYTES)
    source_commit: str = Field(default="", pattern=r"^(?:[0-9a-f]{40}|[0-9a-f]{64})?$")
    source_path: str = Field(default="", max_length=240)


class ImportRequest(CodeRequest):
    preview_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


def policy_hash(policy):
    return hashlib.sha256(
        canonical(
            {
                k: policy[k]
                for k in ("title", "content", "topic", "version", "source_url")
            }
        ).encode()
    ).hexdigest()


def control_hash(control):
    value = {k: control[k] for k in RuleInput.model_fields}
    return hashlib.sha256(
        canonical(
            {
                "configuration": value,
                "version": control["version"],
                "policy_version": control["policy_version"],
            }
        ).encode()
    ).hexdigest()


def parse_document(content):
    if len(content.encode()) > MAX_BYTES:
        raise problem(413, "control_code_size", "Control YAML exceeds 256 KB.")
    try:
        # This loader inherits only SafeLoader constructors; arbitrary Python tags
        # are refused and composition bounds are applied before construction.
        value = yaml.load(content, Loader=ControlLoader)
        document = CodeDocument.model_validate(value)
    except (yaml.YAMLError, ValueError, TypeError, RecursionError) as exc:
        raise problem(
            422,
            "invalid_control_code",
            "Invalid control YAML. Use the exported schema; duplicate keys, aliases, custom tags and activation/approval fields are not accepted.",
        ) from exc
    return document


def validate_pins(db, document, org_id):
    if document.workspace_id != org_id:
        raise problem(
            409,
            "control_code_workspace",
            "This YAML names another workspace. Explicitly remap workspace and policy pins before importing.",
        )
    for item in document.controls:
        policy = db.execute(
            "SELECT * FROM policies WHERE id=?", (item.policy.id,)
        ).fetchone()
        if (
            not policy
            or policy["version"] != item.policy.version
            or policy_hash(policy) != item.policy.sha256
        ):
            raise problem(
                409,
                "control_code_policy_changed",
                "A policy pin is missing or changed. Export/review the current policy configuration before importing.",
            )
        if item.replaces:
            parent = db.execute(
                "SELECT payload FROM records WHERE kind='rule' AND id=?",
                (item.replaces.id,),
            ).fetchone()
            parent = json.loads(parent[0]) if parent else None
            if (
                not parent
                or parent["status"] == "superseded"
                or parent["policy_id"] != item.policy.id
                or control_hash(parent) != item.replaces.sha256
            ):
                raise problem(
                    409,
                    "control_code_parent_changed",
                    "The replaced control is missing, superseded, changed or belongs to another policy.",
                )


def identity(document, request):
    return hashlib.sha256(
        canonical(
            {
                "document": document.model_dump(mode="json"),
                "source_commit": request.source_commit,
                "source_path": request.source_path,
            }
        ).encode()
    ).hexdigest()


def preview(store, org_id, request):
    document = parse_document(request.yaml)
    with store.connect() as db:
        db.execute("BEGIN")
        validate_pins(db, document, org_id)
    return {
        "preview_sha256": identity(document, request),
        "count": len(document.controls),
        "controls": document.model_dump(mode="json")["controls"],
        "source_commit": request.source_commit,
        "source_path": request.source_path,
        "mode": "draft_only",
        "scope": "Source commit/path are supplied provenance assertions; the server does not fetch Git or verify repository signatures. Imported controls need independent in-app approval.",
    }


def import_controls(store, org_id, request, user):
    document = parse_document(request.yaml)
    digest = identity(document, request)
    if digest != request.preview_sha256:
        raise problem(
            409,
            "control_code_preview_changed",
            "YAML or provenance changed after preview. Preview again.",
        )
    ops = Operations(store)
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        prior = db.execute(
            "SELECT payload FROM records WHERE kind='control_code_import' AND id=?",
            (digest,),
        ).fetchone()
        if prior:
            return {**json.loads(prior[0]), "replayed": True}
        validate_pins(db, document, org_id)
        created = [
            {
                "key": item.key,
                "control": ops.draft_rule(
                    db,
                    item.configuration,
                    user,
                    item.replaces.id if item.replaces else None,
                ),
            }
            for item in document.controls
        ]
        stamp = now()
        result = {
            "id": digest,
            "created_at": stamp,
            "created_by": user["id"],
            "controls": created,
            "source_commit": request.source_commit,
            "source_path": request.source_path,
            "document_sha256": hashlib.sha256(
                canonical(document.model_dump(mode="json")).encode()
            ).hexdigest(),
            "mode": "draft_only",
        }
        db.execute(
            "INSERT INTO records VALUES (?,?,?,?,?)",
            ("control_code_import", digest, stamp, stamp, canonical(result)),
        )
        audit(
            db,
            user["id"],
            "control_code_imported",
            {
                "id": digest,
                "control_ids": [item["control"]["id"] for item in created],
                "source_commit": request.source_commit,
                "source_path": request.source_path,
            },
        )
    return {**result, "replayed": False}


def export_controls(store, org_id, control_id=None):
    with store.connect() as db:
        db.execute("BEGIN")
        rows = db.execute(
            "SELECT payload FROM records WHERE kind='rule' AND json_extract(payload,'$.status')!='superseded' AND (? IS NULL OR id=?) ORDER BY id LIMIT 101",
            (control_id, control_id),
        ).fetchall()
        if not rows:
            raise problem(
                404,
                "control_code_empty",
                "No matching controls are available to export.",
            )
        if len(rows) > 100:
            raise problem(
                413,
                "control_code_count",
                "Export at most 100 controls; export individual versions for larger workspaces.",
            )
        controls = []
        for row in rows:
            rule = json.loads(row[0])
            policy = db.execute(
                "SELECT * FROM policies WHERE id=?", (rule["policy_id"],)
            ).fetchone()
            if not policy:
                raise problem(
                    409, "control_code_policy_missing", "A control's policy is missing."
                )
            if policy["version"] != rule["policy_version"]:
                archived = db.execute(
                    "SELECT payload FROM policy_versions WHERE policy_id=? AND version=?",
                    (rule["policy_id"], rule["policy_version"]),
                ).fetchone()
                if not archived:
                    raise problem(
                        409,
                        "control_code_policy_missing",
                        "The control's pinned policy version is missing.",
                    )
                policy = {**json.loads(archived[0]), "id": rule["policy_id"]}
            controls.append(
                {
                    "key": "control-" + rule["id"],
                    "policy": {
                        "id": policy["id"],
                        "version": policy["version"],
                        "sha256": policy_hash(policy),
                    },
                    "replaces": {"id": rule["id"], "sha256": control_hash(rule)},
                    "configuration": {k: rule[k] for k in RuleInput.model_fields},
                }
            )
    text = yaml.safe_dump(
        {
            "schema_version": "policylens.controls.v1",
            "workspace_id": org_id,
            "controls": controls,
        },
        sort_keys=False,
        allow_unicode=True,
    )
    if len(text.encode()) > MAX_BYTES:
        raise problem(
            413,
            "control_code_size",
            "The complete YAML export exceeds 256 KB; export individual controls.",
        )
    return text
