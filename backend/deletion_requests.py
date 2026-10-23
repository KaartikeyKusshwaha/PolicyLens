"""Reviewed, expiring deletion plans; execution belongs to the offline operator."""

from datetime import datetime, timedelta, timezone

from pydantic import Field

from deletion import digest, plan, timestamp
from models import Input
from operations import audit, canonical, uid
from providers import problem
from retention import get, records, save
from store import now

MAX_REQUESTS = 2000
MAX_REQUEST_BYTES = 2_000_000


class RequestInput(Input):
    customer_id: str = Field(min_length=1, max_length=100)
    inventory_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    reason: str = Field(min_length=20, max_length=2000)


class ReviewInput(Input):
    reason: str = Field(min_length=20, max_length=2000)


class ApprovalInput(ReviewInput):
    discovery_reference: str = Field(min_length=3, max_length=500)
    discovery_evidence_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    acknowledge_retained_audit: bool = Field(strict=True)
    acknowledge_physical_and_restore_limits: bool = Field(strict=True)


def append_event(db, value, user, action, reason):
    value.setdefault("history", []).append(
        {"action": action, "actor": user["id"], "at": now(), "reason": reason}
    )
    save(db, "deletion_request", value)
    audit(
        db,
        user["id"],
        "deletion_request_" + action,
        {
            "id": value["id"],
            "inventory_sha256": value["inventory_sha256"],
            "record_sha256": digest(value),
        },
    )
    return value


def current_plan(db, workspace_id, value):
    current = plan(db, workspace_id, value["customer_id"])
    if current["inventory_sha256"] != value["inventory_sha256"]:
        raise problem(
            409,
            "deletion_request_stale",
            "Customer records, policy, holds or custody changed. Cancel this request and submit a fresh preview.",
        )
    return current


def require_live(value):
    if timestamp(value["expires_at"]) <= datetime.now(timezone.utc):
        raise problem(
            409,
            "deletion_request_expired",
            "This request expired. Cancel it and obtain a fresh preview and review.",
        )


def create(store, workspace_id, data, user):
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        history = records(db, "deletion_request")
        if len(history) >= MAX_REQUESTS:
            raise problem(
                422,
                "retention_capacity",
                "Deletion request history reached the pilot bound.",
            )
        if any(
            item["customer_id"] == data.customer_id
            and item["status"] in ("requested", "approved")
            for item in history
        ):
            raise problem(
                409,
                "deletion_request_pending",
                "Cancel or reject the existing customer request before creating another.",
            )
        snapshot = plan(db, workspace_id, data.customer_id)
        if snapshot["inventory_sha256"] != data.inventory_sha256:
            raise problem(
                409,
                "deletion_request_stale",
                "The preview changed before submission. Inspect a fresh preview.",
            )
        if len(canonical(snapshot).encode()) > MAX_REQUEST_BYTES:
            raise problem(
                422,
                "retention_capacity",
                "The complete request exceeds its bound; no partial plan was retained.",
            )
        value = {
            "id": uid(),
            "customer_id": data.customer_id,
            "workspace_id": workspace_id,
            "inventory_sha256": data.inventory_sha256,
            "created_by": user["id"],
            "created_at": now(),
            "expires_at": (
                datetime.now(timezone.utc) + timedelta(hours=24)
            ).isoformat(),
            "status": "requested",
            "snapshot": snapshot,
            "history": [],
            "reason": data.reason,
            "scope": "Review of a logical deletion plan only. Execution requires the stopped-installation operator CLI and external suppression state. Audit history and external/physical/restore limits remain.",
        }
        return append_event(db, value, user, "submitted", data.reason)


def approve(store, workspace_id, record_id, data, user):
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        value = get(db, "deletion_request", record_id)
        if value["status"] != "requested":
            raise problem(
                409,
                "deletion_request_state",
                "Only a requested plan can receive approval.",
            )
        if value["created_by"] == user["id"]:
            raise problem(
                403,
                "independent_approval",
                "A different reviewer must approve this deletion plan.",
            )
        require_live(value)
        current = current_plan(db, workspace_id, value)
        if any(
            block["code"] != "external_copy_reconciliation_required"
            for block in current["blockers"]
        ):
            raise problem(
                409,
                "deletion_request_blocked",
                "The plan still has unresolved retention, hold, operational, shared-reference or registered-copy blockers.",
            )
        if (
            not data.acknowledge_retained_audit
            or not data.acknowledge_physical_and_restore_limits
        ):
            raise problem(
                422,
                "deletion_limits_acknowledgement",
                "Review and acknowledge retained audit and physical/restore limits.",
            )
        value.update(
            status="approved",
            approved_by=user["id"],
            approved_at=now(),
            discovery_reference=data.discovery_reference,
            discovery_evidence_sha256=data.discovery_evidence_sha256,
            acknowledge_retained_audit=True,
            acknowledge_physical_and_restore_limits=True,
        )
        return append_event(db, value, user, "approved", data.reason)


def finish_review(store, record_id, data, user, *, action):
    with store.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        value = get(db, "deletion_request", record_id)
        if value["status"] not in ("requested", "approved"):
            raise problem(
                409, "deletion_request_state", "This request is already terminal."
            )
        if action == "rejected" and value["created_by"] == user["id"]:
            raise problem(
                403,
                "independent_approval",
                "Authors can cancel their request; rejection belongs to a different reviewer.",
            )
        if (
            action == "cancelled"
            and user["id"] != value["created_by"]
            and user["role"] != "admin"
        ):
            raise problem(
                403,
                "role_required",
                "Only its author or an administrator can cancel this request.",
            )
        value["status"] = action
        return append_event(db, value, user, action, data.reason)


def inspect(store, workspace_id, record_id):
    with store.connect() as db:
        db.execute("BEGIN")
        value = get(db, "deletion_request", record_id)
        if value["status"] == "executed":
            return {
                "request": value,
                "receipt": get(db, "deletion_receipt", value["receipt_id"]),
                "current_inventory_sha256": None,
                "stale": False,
                "expired": False,
                "current_blockers": [],
                "execution_available": False,
            }
        current = plan(db, workspace_id, value["customer_id"])
        return {
            "request": value,
            "current_inventory_sha256": current["inventory_sha256"],
            "stale": value["inventory_sha256"] != current["inventory_sha256"],
            "expired": timestamp(value["expires_at"]) <= datetime.now(timezone.utc),
            "current_blockers": current["blockers"],
            "execution_available": False,
        }
