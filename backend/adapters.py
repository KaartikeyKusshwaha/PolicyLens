"""Previewed, tenant-mapped external engine evidence imports. No upstream writes."""

import hashlib
import json
from datetime import datetime
from typing import Generic, Literal, Protocol, TypeVar
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    field_validator,
    model_validator,
)

from models import Input
from operations import Operations, audit, canonical, uid
from providers import problem
from store import now

MAX_BYTES = 2_000_000
CONTRACTS = {
    "v1": "e634b9ce7dad4d991b5d47cf4ee03bdec5004c04",
    "v1beta": "3bdcd784dbb6f3c325c505878d052d69b33df1c7",
}


class SourceObject(BaseModel):
    model_config = ConfigDict(extra="allow", str_strip_whitespace=False)


class Ref(SourceObject):
    id: UUID
    name: str | None = Field(default=None, max_length=1000)


class Scenario(Ref):
    iteration_id: UUID
    version: str = Field(min_length=1, max_length=100)


class Timestamped(SourceObject):
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def timezone_required(cls, value):
        if value.tzinfo is None:
            raise ValueError("Source timestamps require a timezone.")
        return value


class Trigger(SourceObject):
    object_id: str = Field(min_length=1, max_length=500)
    updated_at: datetime

    @field_validator("updated_at")
    @classmethod
    def timezone_required(cls, value):
        if value.tzinfo is None:
            raise ValueError("Source timestamps require a timezone.")
        return value


class MarbleCase(Timestamped):
    id: UUID
    inbox: Ref
    name: str = Field(min_length=1, max_length=1000)
    status: Literal["pending", "investigating", "closed"]
    outcome: Literal["unset", "confirmed_risk", "valuable_alert", "false_positive"]
    contributors: list[Ref] = Field(max_length=100)
    tags: list[Ref] = Field(max_length=100)
    review_level: Literal["probable_false_positive", "investigate", "escalate"] | None


class MarbleDecision(Timestamped):
    id: UUID
    outcome: Literal["approve", "review", "block_and_review", "decline"]
    review_status: Literal["pending", "approve", "decline"] | None
    scenario: Scenario
    trigger_object: Trigger
    score: StrictInt
    case: Ref | None = None


class Pagination(Input):
    has_more: bool
    next_page_id: str | None = Field(default=None, max_length=2000)


T = TypeVar("T")


class Page(Input, Generic[T]):
    data: list[T] = Field(default_factory=list, max_length=500)
    pagination: Pagination | None = None
    metadata: dict = Field(default_factory=dict)


class CustomerMapping(Input):
    object_type: Literal["case", "decision"]
    source_id: UUID
    customer_id: str = Field(min_length=1, max_length=100)


class MarbleBundle(Input):
    schema_version: Literal["policylens.marble-import.v1"]
    source_instance: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,99}$")
    case_api_version: Literal["v1beta"] = "v1beta"
    decision_api_version: Literal["v1"] = "v1"
    cases: Page[MarbleCase] = Field(default_factory=Page[MarbleCase])
    decisions: Page[MarbleDecision] = Field(default_factory=Page[MarbleDecision])
    customer_mappings: list[CustomerMapping] = Field(
        default_factory=list, max_length=1000
    )
    acknowledge_partial_pages: bool = False

    @model_validator(mode="after")
    def unique_objects(self):
        if not self.cases.data and not self.decisions.data:
            raise ValueError("Supply cases or decisions to import.")
        for page in (self.cases, self.decisions):
            if len({x.id for x in page.data}) != len(page.data):
                raise ValueError("Source IDs must be unique within each page.")
            if (
                page.pagination
                and page.pagination.has_more
                and not self.acknowledge_partial_pages
            ):
                raise ValueError("Explicitly acknowledge that more source pages exist.")
        keys = [(x.object_type, x.source_id) for x in self.customer_mappings]
        if len(set(keys)) != len(keys):
            raise ValueError("Duplicate customer mappings are not allowed.")
        actual = {("case", x.id) for x in self.cases.data} | {
            ("decision", x.id) for x in self.decisions.data
        }
        if any(key not in actual for key in keys):
            raise ValueError("Map only source objects included in the bundle.")
        return self


class EngineAdapter(Protocol):
    name: str

    def parse(self, payload: dict): ...
    def objects(self, bundle): ...


class MarbleAdapter:
    name = "marble"

    def parse(self, payload):
        return MarbleBundle.model_validate(payload)

    def objects(self, bundle):
        return [
            ("case", value.model_dump(mode="json"), "v1beta")
            for value in bundle.cases.data
        ] + [
            ("decision", value.model_dump(mode="json"), "v1")
            for value in bundle.decisions.data
        ]


ADAPTERS: dict[str, EngineAdapter] = {"marble": MarbleAdapter()}


def stable(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def digest(value):
    return hashlib.sha256(stable(value).encode()).hexdigest()


def object_key(provider, instance, kind, source_id):
    return digest(
        {
            "purpose": "external-engine-object",
            "provider": provider,
            "instance": instance,
            "kind": kind,
            "source_id": source_id,
        }
    )


def record(db, kind, identifier):
    row = db.execute(
        "SELECT payload FROM records WHERE kind=? AND id=?", (kind, identifier)
    ).fetchone()
    return json.loads(row[0]) if row else None


def parse(provider, payload):
    if provider not in ADAPTERS:
        raise problem(404, "adapter_unknown", "This engine adapter is not supported.")
    try:
        if len(stable(payload).encode()) > MAX_BYTES:
            raise problem(413, "adapter_size", "Import bundles are limited to 2 MB.")
        bundle = ADAPTERS[provider].parse(payload)
    except (ValueError, TypeError, RecursionError) as exc:
        raise problem(
            422,
            "adapter_schema",
            "Invalid engine export bundle, version, timestamp, duplicate ID or pagination acknowledgement. Use the documented adapter schema.",
        ) from exc
    return bundle


def plan(db, provider, bundle):
    mappings = {
        (x.object_type, str(x.source_id)): x.customer_id
        for x in bundle.customer_mappings
    }
    objects, cases = [], {}
    for kind, raw, api_version in ADAPTERS[provider].objects(bundle):
        source_id = raw["id"]
        key = object_key(provider, bundle.source_instance, kind, source_id)
        prior = record(db, "adapter_object", key)
        source_case_id = (
            raw["case"]["id"] if kind == "decision" and raw.get("case") else None
        )
        customer_id = mappings.get((kind, source_id)) or (
            prior["customer_id"] if prior else None
        )
        errors = []
        parent = None
        if kind == "decision" and source_case_id:
            parent = cases.get(source_case_id) or record(
                db,
                "adapter_object",
                object_key(provider, bundle.source_instance, "case", source_case_id),
            )
            if parent is None:
                errors.append("referenced_source_case_not_imported")
            else:
                if customer_id and parent["customer_id"] != customer_id:
                    errors.append("case_customer_mapping_conflict")
                customer_id = parent["customer_id"]
        if not customer_id:
            errors.append("customer_mapping_required")
        elif record(db, "customer", customer_id) is None:
            errors.append("customer_not_in_workspace")
        source_hash = digest(raw)
        if prior and (
            prior["sha256"] != source_hash or prior["customer_id"] != customer_id
        ):
            errors.append("source_identity_changed")
        creates_alert = kind == "decision" and raw["outcome"] != "approve"
        parent_case = parent.get("local_case_id") if parent else None
        if creates_alert and not prior and parent_case:
            native = record(db, "case", parent_case)
            if native is None or native["status"] == "resolved":
                errors.append("local_case_requires_human_reopen")
        item = {
            "id": key,
            "object_type": kind,
            "source_name": raw.get("name", "Marble decision"),
            "source_id": source_id,
            "customer_id": customer_id,
            "source_case_id": source_case_id,
            "local_case_id": prior.get("local_case_id") if prior else parent_case,
            "alert_id": prior.get("alert_id") if prior else None,
            "sha256": source_hash,
            "api_version": api_version,
            "contract_git_blob": CONTRACTS[api_version],
            "action": "replay" if prior else "new",
            "creates_alert": creates_alert and prior is None,
            "raw": raw,
            "errors": errors,
        }
        objects.append(item)
        if kind == "case":
            cases[source_id] = item
    return objects


def preview(store, provider, payload):
    bundle = parse(provider, payload)
    with store.connect() as db:
        db.execute("BEGIN")
        objects = plan(db, provider, bundle)
    return {
        "preview_sha256": digest(
            {"provider": provider, "bundle": bundle.model_dump(mode="json")}
        ),
        "can_import": not any(x["errors"] for x in objects),
        "objects": [{k: v for k, v in x.items() if k != "raw"} for x in objects],
        "scope": "Selected exported records, not complete engine history. Upstream outcomes are source evidence; local cases stay open for human review. No transactions, active controls or payment actions are created.",
    }


def save_record(db, kind, value):
    stamp = now()
    db.execute(
        "INSERT INTO records VALUES (?,?,?,?,?)",
        (kind, value["id"], stamp, stamp, canonical(value)),
    )


def import_bundle(store, provider, payload, preview_sha256, user):
    bundle = parse(provider, payload)
    identifier = digest(
        {"provider": provider, "bundle": bundle.model_dump(mode="json")}
    )
    if identifier != preview_sha256:
        raise problem(
            409,
            "adapter_preview_changed",
            "The bundle or mappings changed. Preview again.",
        )
    ops = Operations(store)
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        previous = record(db, "adapter_import", identifier)
        if previous:
            return {**previous, "replayed": True}
        objects = plan(db, provider, bundle)
        if any(x["errors"] for x in objects):
            raise problem(
                409,
                "adapter_plan_conflict",
                "Import mappings, source identity or local case state changed or need review. Preview again; no partial import was committed.",
            )
        cases = {}
        for item in objects:
            kind, raw = item["object_type"], item["raw"]
            if item["action"] == "replay":
                if kind == "case":
                    cases[item["source_id"]] = item["local_case_id"]
                continue
            source = {
                "provider": provider,
                "instance": bundle.source_instance,
                "object_type": kind,
                "source_id": item["source_id"],
                "sha256": item["sha256"],
                "api_version": item["api_version"],
                "contract_git_blob": item["contract_git_blob"],
            }
            if kind == "decision" and item["source_case_id"]:
                item["local_case_id"] = (
                    cases.get(item["source_case_id"]) or item["local_case_id"]
                )
            if kind == "case" or (item["creates_alert"] and not item["local_case_id"]):
                customer = record(db, "customer", item["customer_id"])
                title = (
                    "Review imported Marble case " + item["source_id"]
                    if kind == "case"
                    else "Review imported Marble decision " + item["source_id"]
                )
                native = ops._open_case(
                    db,
                    customer,
                    title,
                    "medium",
                    "External engine records imported for human review. Upstream status/outcome does not determine the local disposition. No transaction interpretation has been inferred.",
                    user["id"],
                    group_existing=False,
                )
                native["external_source"] = {
                    **source,
                    **(
                        {
                            "source_name": raw["name"],
                            "source_status": raw["status"],
                            "source_outcome": raw["outcome"],
                        }
                        if kind == "case"
                        else {}
                    ),
                }
                db.execute(
                    "UPDATE records SET payload=? WHERE kind='case' AND id=?",
                    (canonical(native), native["id"]),
                )
                item["local_case_id"] = native["id"]
            if kind == "case":
                cases[item["source_id"]] = item["local_case_id"]
            if item["creates_alert"]:
                alert_id = uid()
                scenario = raw["scenario"]
                alert = {
                    "id": alert_id,
                    "case_id": item["local_case_id"],
                    "origin": "external_engine",
                    "external_source": source,
                    "transaction_id": None,
                    "rule_id": None,
                    "rule_title": "Imported Marble scenario",
                    "rule_version": scenario["version"],
                    "rule_snapshot": {
                        "origin": "marble",
                        "scenario": {
                            k: scenario[k] for k in ("id", "iteration_id", "version")
                        },
                        "scope": "External scenario evidence; not an approved PolicyLens control.",
                    },
                    "facts": {
                        "source_outcome": raw["outcome"],
                        "source_score": raw["score"],
                        "source_review_status": raw["review_status"],
                        "trigger_object_id": raw["trigger_object"]["object_id"],
                    },
                    "created_at": now(),
                    "priority": "medium",
                }
                db.execute(
                    "INSERT INTO alerts VALUES (?,?,?,?,?)",
                    (
                        alert_id,
                        "adapter:" + item["id"],
                        item["local_case_id"],
                        alert["created_at"],
                        canonical(alert),
                    ),
                )
                item["alert_id"] = alert_id
                audit(
                    db,
                    user["id"],
                    "external_alert_imported",
                    {"id": alert_id, "case_id": item["local_case_id"], **source},
                )
            saved = {
                **item,
                "provider": provider,
                "source_instance": bundle.source_instance,
                "imported_at": now(),
                "imported_by": user["id"],
            }
            save_record(db, "adapter_object", saved)
            audit(
                db,
                user["id"],
                "external_object_imported",
                {"id": item["id"], "local_case_id": item["local_case_id"], **source},
            )
        receipt = {
            "id": identifier,
            "provider": provider,
            "source_instance": bundle.source_instance,
            "created_at": now(),
            "created_by": user["id"],
            "objects": [{k: v for k, v in x.items() if k != "raw"} for x in objects],
            "source_coverage": "selected_exported_records",
            "source_metadata": {
                "cases": bundle.cases.metadata,
                "decisions": bundle.decisions.metadata,
            },
            "pagination": {
                "cases": bundle.cases.pagination.model_dump()
                if bundle.cases.pagination
                else None,
                "decisions": bundle.decisions.pagination.model_dump()
                if bundle.decisions.pagination
                else None,
            },
            "acknowledged_partial_pages": bundle.acknowledge_partial_pages,
        }
        save_record(db, "adapter_import", receipt)
        audit(
            db,
            user["id"],
            "engine_bundle_imported",
            {
                "id": identifier,
                "provider": provider,
                "instance": bundle.source_instance,
                "objects": len(objects),
                "source_coverage": receipt["source_coverage"],
            },
        )
    return {**receipt, "replayed": False}
