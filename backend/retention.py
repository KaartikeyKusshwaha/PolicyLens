"""Tenant-local retention governance. No automatic deletion or legal defaults."""

import hashlib
import json
from typing import Literal

from pydantic import Field, model_validator

from models import Input
from operations import audit, canonical, uid
from providers import problem
from store import now

MAX_GOVERNANCE_RECORDS = 2000


class RetentionPolicy(Input):
    title: str = Field(min_length=3, max_length=160)
    rationale: str = Field(min_length=20, max_length=3000)
    customer_days: int = Field(ge=1, le=36500, strict=True)
    resolved_case_days: int = Field(ge=1, le=36500, strict=True)
    terminal_job_days: int = Field(ge=1, le=36500, strict=True)
    backup_days: int = Field(ge=1, le=36500, strict=True)
    audit_minimum_days: int = Field(ge=1, le=36500, strict=True)
    external_copy_procedure: str = Field(min_length=20, max_length=4000)
    parent_id: str | None = Field(default=None, max_length=100)


class HoldInput(Input):
    scope: Literal["workspace", "customer", "case"]
    target_id: str = Field(default="", max_length=100)
    reason: str = Field(min_length=10, max_length=2000)
    authority_reference: str = Field(min_length=3, max_length=300)

    @model_validator(mode="after")
    def scope_target(self):
        if (self.scope == "workspace") != (self.target_id == ""):
            raise ValueError(
                "Workspace holds have no target; customer/case holds require one."
            )
        return self


class Review(Input):
    reason: str = Field(min_length=10, max_length=2000)


def records(db, kind):
    rows = db.execute(
        "SELECT payload FROM records WHERE kind=? ORDER BY created_at,id LIMIT ?",
        (kind, MAX_GOVERNANCE_RECORDS + 1),
    ).fetchall()
    if len(rows) > MAX_GOVERNANCE_RECORDS:
        raise problem(
            422,
            "retention_capacity",
            "Retention governance exceeds the pilot bound; no records were omitted.",
        )
    return [json.loads(row[0]) for row in rows]


def get(db, kind, record_id):
    row = db.execute(
        "SELECT payload FROM records WHERE kind=? AND id=?", (kind, record_id)
    ).fetchone()
    if not row:
        raise problem(404, "not_found", "Retention record not found in this workspace.")
    return json.loads(row[0])


def save(db, kind, value):
    db.execute(
        "INSERT INTO records VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET updated_at=excluded.updated_at,payload=excluded.payload",
        (kind, value["id"], value["created_at"], now(), canonical(value)),
    )


def active_policy(db):
    active = [
        item for item in records(db, "retention_policy") if item["status"] == "active"
    ]
    if len(active) > 1:
        raise problem(
            409,
            "retention_conflict",
            "Multiple active retention policies require operator review.",
        )
    return active[0] if active else None


def state(store):
    with store.connect() as db:
        db.execute("BEGIN")
        policies = records(db, "retention_policy")
        holds = records(db, "retention_hold")
        copies = records(db, "retained_copy")
        active = active_policy(db)
    return {
        "active_policy": active,
        "policies": policies,
        "holds": holds,
        "copies": copies,
        "deletion_enabled": False,
        "deletion_preview_available": True,
        "limits": "Deletion inventory previews are available; execution and copy reconciliation are unfinished. Holds remain effective during release review. No statutory retention period is supplied.",
    }


def draft_policy(store, data, user):
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        active = active_policy(db)
        if data.parent_id != (active["id"] if active else None):
            raise problem(
                409,
                "retention_stale",
                "The active policy changed; review it before drafting a replacement.",
            )
        if len(records(db, "retention_policy")) >= MAX_GOVERNANCE_RECORDS:
            raise problem(
                422,
                "retention_capacity",
                "Retention policy history reached the pilot bound.",
            )
        configuration = data.model_dump()
        value = {
            **configuration,
            "id": uid(),
            "created_at": now(),
            "created_by": user["id"],
            "status": "draft",
            "configuration_sha256": hashlib.sha256(
                canonical(configuration).encode()
            ).hexdigest(),
        }
        save(db, "retention_policy", value)
        audit(
            db,
            user["id"],
            "retention_policy_drafted",
            {"id": value["id"], "configuration_sha256": value["configuration_sha256"]},
        )
        return value


def approve_policy(store, record_id, review, user):
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        value = get(db, "retention_policy", record_id)
        if value["created_by"] == user["id"]:
            raise problem(
                403,
                "independent_approval",
                "A different reviewer must approve the retention policy.",
            )
        if value["status"] != "draft":
            raise problem(
                409, "retention_state", "Only a draft retention policy can be approved."
            )
        current = active_policy(db)
        if value["parent_id"] != (current["id"] if current else None):
            raise problem(
                409,
                "retention_stale",
                "The active policy changed; draft a new version for review.",
            )
        if current:
            current["status"] = "superseded"
            save(db, "retention_policy", current)
        value.update(
            status="active",
            approved_by=user["id"],
            approved_at=now(),
            approval_reason=review.reason,
        )
        save(db, "retention_policy", value)
        audit(
            db,
            user["id"],
            "retention_policy_approved",
            {"id": value["id"], "configuration_sha256": value["configuration_sha256"]},
        )
        return value


def place_hold(store, data, user):
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        if data.scope != "workspace":
            get(db, data.scope, data.target_id)
        if len(records(db, "retention_hold")) >= MAX_GOVERNANCE_RECORDS:
            raise problem(
                422, "retention_capacity", "Legal hold history reached the pilot bound."
            )
        value = {
            **data.model_dump(),
            "id": uid(),
            "created_at": now(),
            "created_by": user["id"],
            "status": "active",
        }
        save(db, "retention_hold", value)
        audit(
            db,
            user["id"],
            "retention_hold_placed",
            {
                "id": value["id"],
                "scope": value["scope"],
                "target_id": value["target_id"],
            },
        )
        return value


def request_release(store, record_id, review, user):
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        value = get(db, "retention_hold", record_id)
        if value["status"] != "active":
            raise problem(
                409, "retention_state", "Only an active hold can enter release review."
            )
        value.update(
            status="release_requested",
            release_requested_by=user["id"],
            release_requested_at=now(),
            release_reason=review.reason,
        )
        save(db, "retention_hold", value)
        audit(db, user["id"], "retention_hold_release_requested", {"id": value["id"]})
        return value


def approve_release(store, record_id, review, user):
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        value = get(db, "retention_hold", record_id)
        if value["status"] != "release_requested":
            raise problem(
                409, "retention_state", "This hold has no pending release request."
            )
        if value["release_requested_by"] == user["id"]:
            raise problem(
                403,
                "independent_approval",
                "A different reviewer must approve releasing the hold.",
            )
        value.update(
            status="released",
            released_by=user["id"],
            released_at=now(),
            release_approval_reason=review.reason,
        )
        save(db, "retention_hold", value)
        audit(db, user["id"], "retention_hold_released", {"id": value["id"]})
        return value


def blocking_holds(db, customer_id=None, case_ids=()):
    return [
        item
        for item in records(db, "retention_hold")
        if item["status"] in ("active", "release_requested")
        and (
            item["scope"] == "workspace"
            or (item["scope"] == "customer" and item["target_id"] == customer_id)
            or (item["scope"] == "case" and item["target_id"] in case_ids)
        )
    ]
