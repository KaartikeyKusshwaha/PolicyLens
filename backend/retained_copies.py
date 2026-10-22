"""Human-reviewed custody records. Never opens/deletes a supplied location."""

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Literal

from pydantic import Field, field_validator, model_validator

from models import Input
from operations import audit, canonical, uid
from providers import problem
from retention import active_policy, blocking_holds, get, records, save
from store import now

MAX_COPIES = 2000
MAX_HISTORY = 50
MAX_SCOPE_CASES = 5000


class CopyInput(Input):
    category: Literal[
        "backup",
        "recovery_snapshot",
        "plaintext_original",
        "evidence_export",
        "audit_checkpoint",
        "downstream_copy",
    ]
    scope: Literal["workspace", "customer", "case"]
    target_id: str = Field(default="", max_length=100)
    custodian: str = Field(min_length=3, max_length=160)
    location_reference: str = Field(min_length=3, max_length=500)
    content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    copy_created_at: datetime
    preserve_until: datetime
    reason: str = Field(min_length=10, max_length=2000)

    @field_validator("copy_created_at", "preserve_until", mode="before")
    @classmethod
    def explicit_dates(cls, value):
        if not isinstance(value, (str, datetime)):
            raise ValueError(
                "Use a date with an explicit timezone, not a numeric timestamp."
            )
        return value

    @field_validator("copy_created_at", "preserve_until")
    @classmethod
    def aware(cls, value):
        if value.tzinfo is None:
            raise ValueError("Copy dates must have an explicit timezone.")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def boundaries(self):
        if (self.scope == "workspace") != (self.target_id == ""):
            raise ValueError(
                "Workspace copies have no target; customer/case copies require one."
            )
        if self.copy_created_at > datetime.now(timezone.utc):
            raise ValueError("A copy cannot be registered with a future creation time.")
        if self.preserve_until < self.copy_created_at:
            raise ValueError("Preservation cannot end before the copy was created.")
        return self


class CopyReview(Input):
    reason: str = Field(min_length=10, max_length=2000)


class RemovalReport(CopyReview):
    evidence_reference: str = Field(min_length=3, max_length=500)
    evidence_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


def policy_required(db):
    policy = active_policy(db)
    if not policy:
        raise problem(
            409,
            "retention_policy_required",
            "Approve a retention policy before reconciling copies.",
        )
    return policy


def minimum_until(copy, policy):
    days = (
        policy["backup_days"]
        if copy["category"] in ("backup", "recovery_snapshot", "plaintext_original")
        else policy["audit_minimum_days"]
        if copy["category"] == "audit_checkpoint"
        else max(
            policy[key]
            for key in (
                "customer_days",
                "resolved_case_days",
                "terminal_job_days",
                "audit_minimum_days",
                "backup_days",
            )
        )
    )
    try:
        return datetime.fromisoformat(copy["copy_created_at"]) + timedelta(days=days)
    except (ValueError, TypeError, OverflowError) as exc:
        raise problem(
            422,
            "retention_copy_date",
            "A copy retention deadline cannot be calculated safely.",
        ) from exc


def effective_until(copy, policy):
    return max(
        datetime.fromisoformat(copy["preserve_until"]), minimum_until(copy, policy)
    )


def applicable_holds(db, copy):
    if copy["scope"] == "workspace":
        return [
            hold
            for hold in records(db, "retention_hold")
            if hold["status"] in ("active", "release_requested")
        ]
    customer_id = copy["customer_id"]
    if copy["scope"] == "case":
        return blocking_holds(db, customer_id, [copy["target_id"]])
    cases = [
        row[0]
        for row in db.execute(
            "SELECT id FROM records WHERE kind='case' AND json_extract(payload,'$.customer_id')=? LIMIT ?",
            (customer_id, MAX_SCOPE_CASES + 1),
        )
    ]
    if len(cases) > MAX_SCOPE_CASES:
        raise problem(
            422,
            "retention_capacity",
            "Copy hold discovery exceeds the pilot case bound; no holds were omitted.",
        )
    return blocking_holds(db, customer_id, cases)


def removal_checks(db, copy, *, approved=False):
    policy = policy_required(db)
    if applicable_holds(db, copy):
        raise problem(
            409,
            "retention_copy_held",
            "A legal hold applies to this copy, including any pending release.",
        )
    if effective_until(copy, policy) > datetime.now(timezone.utc):
        raise problem(
            409,
            "retention_copy_not_due",
            "The copy's effective preservation period has not elapsed.",
        )
    if approved and copy["removal_policy_id"] != policy["id"]:
        raise problem(
            409,
            "retention_copy_stale",
            "The retention policy changed. Cancel the removal and request a fresh review.",
        )
    return policy


def transition(db, copy, user, action, reason):
    history = copy.setdefault("history", [])
    if len(history) >= MAX_HISTORY:
        raise problem(
            422,
            "retention_capacity",
            "This copy's review history reached the pilot bound.",
        )
    history.append(
        {
            "action": action,
            "actor": user["id"],
            "at": now(),
            "reason": reason,
            "policy_id": copy.get("removal_policy_id", copy["registered_policy_id"]),
            "evidence_sha256": copy.get("evidence_sha256"),
        }
    )
    save(db, "retained_copy", copy)
    audit(
        db,
        user["id"],
        "retained_copy_" + action,
        {
            "id": copy["id"],
            "status": copy["status"],
            "record_sha256": hashlib.sha256(canonical(copy).encode()).hexdigest(),
        },
    )
    return copy


def register(store, data, user):
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        policy = policy_required(db)
        if len(records(db, "retained_copy")) >= MAX_COPIES:
            raise problem(
                422,
                "retention_capacity",
                "Copy custody history reached the pilot bound.",
            )
        customer_id = None
        if data.scope != "workspace":
            target = get(db, data.scope, data.target_id)
            customer_id = (
                target["id"] if data.scope == "customer" else target["customer_id"]
            )
        value = {
            **data.model_dump(mode="json"),
            "id": uid(),
            "customer_id": customer_id,
            "created_at": now(),
            "created_by": user["id"],
            "status": "retained",
            "registered_policy_id": policy["id"],
            "history": [],
        }
        if data.preserve_until < minimum_until(value, policy):
            raise problem(
                422,
                "retention_copy_preservation",
                "The chosen preservation date is earlier than the approved policy permits.",
            )
        return transition(db, value, user, "registered", data.reason)


def request_removal(store, record_id, data, user):
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        value = get(db, "retained_copy", record_id)
        if value["status"] != "retained":
            raise problem(
                409,
                "retention_copy_state",
                "Only a retained copy can enter removal review.",
            )
        policy = removal_checks(db, value)
        value.update(
            status="removal_requested",
            removal_requested_by=user["id"],
            removal_policy_id=policy["id"],
            removal_requested_at=now(),
        )
        return transition(db, value, user, "removal_requested", data.reason)


def approve_removal(store, record_id, data, user):
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        value = get(db, "retained_copy", record_id)
        if value["status"] != "removal_requested":
            raise problem(
                409, "retention_copy_state", "This copy has no pending removal request."
            )
        if value["removal_requested_by"] == user["id"]:
            raise problem(
                403,
                "independent_approval",
                "A different reviewer must authorize copy removal.",
            )
        removal_checks(db, value, approved=True)
        value.update(
            status="removal_authorized",
            removal_approved_by=user["id"],
            removal_approved_at=now(),
        )
        return transition(db, value, user, "removal_authorized", data.reason)


def report_removal(store, record_id, data, user):
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        value = get(db, "retained_copy", record_id)
        if value["status"] != "removal_authorized":
            raise problem(
                409,
                "retention_copy_state",
                "Authorize copy removal before submitting the custodian report.",
            )
        removal_checks(db, value, approved=True)
        value.update(
            status="removal_reported",
            removal_reported_by=user["id"],
            removal_reported_at=now(),
            evidence_reference=data.evidence_reference,
            evidence_sha256=data.evidence_sha256,
        )
        return transition(db, value, user, "removal_reported", data.reason)


def confirm_removal(store, record_id, data, user):
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        value = get(db, "retained_copy", record_id)
        if value["status"] != "removal_reported":
            raise problem(
                409,
                "retention_copy_state",
                "A custodian report must precede independent confirmation.",
            )
        if value["removal_reported_by"] == user["id"]:
            raise problem(
                403,
                "independent_approval",
                "A different reviewer must confirm the custodian report.",
            )
        removal_checks(db, value, approved=True)
        value.update(
            status="removal_confirmed",
            removal_confirmed_by=user["id"],
            removal_confirmed_at=now(),
        )
        return transition(db, value, user, "removal_confirmed", data.reason)


def review_reported_removal(store, record_id, data, user):
    """Re-review existing reported facts after policy changes; never undo a report."""
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        value = get(db, "retained_copy", record_id)
        if value["status"] != "removal_reported":
            raise problem(
                409,
                "retention_copy_state",
                "Only a reported removal can receive a refreshed policy review.",
            )
        if value["removal_reported_by"] == user["id"]:
            raise problem(
                403,
                "independent_approval",
                "A different reviewer must re-review the reported removal.",
            )
        policy = removal_checks(db, value)
        if value["removal_policy_id"] == policy["id"]:
            raise problem(
                409,
                "retention_copy_state",
                "The report already references the current policy.",
            )
        value["removal_policy_id"] = policy["id"]
        return transition(
            db, value, user, "reported_removal_policy_reviewed", data.reason
        )


def cancel_removal(store, record_id, data, user):
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        value = get(db, "retained_copy", record_id)
        if value["status"] not in ("removal_requested", "removal_authorized"):
            raise problem(
                409,
                "retention_copy_state",
                "Only an unreported removal workflow can be cancelled.",
            )
        value["status"] = "retained"
        for key in list(value):
            if key.startswith("removal_"):
                value.pop(key)
        return transition(db, value, user, "removal_cancelled", data.reason)
