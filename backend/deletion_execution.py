"""Stopped-installation logical deletion with durable external prepare/commit."""

import hashlib
import json
import os
import uuid
from pathlib import Path

from auth import Hub
from database import encrypted
from deletion import digest
from deletion_guard import (
    MAX_BYTES,
    MAX_RECEIPTS,
    export_guard,
    read_guard,
    receipt_entry,
    validate_payload,
    SCHEMA,
)
from deletion_requests import append_event, current_plan, require_live
from operations import audit, canonical, uid
from providers import problem
from retention import get, save
from runtime import InstallationLock
from store import now

MAX_STATE_BYTES = 64 * 1024 * 1024


def directory(settings):
    if settings.deletion_state_directory is None:
        raise ValueError(
            "Configure DELETION_STATE_DIRECTORY outside the database directory before deletion"
        )
    path = Path(settings.deletion_state_directory).absolute()
    data = settings.database_path.parent.resolve()
    if path.resolve() != path or path == data or path.is_relative_to(data):
        raise ValueError(
            "Deletion state must stay outside the database directory without redirected paths"
        )
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name != "nt" and path.stat().st_mode & 0o077:
        raise ValueError("Deletion state directory permissions must be 0700")
    return path


def state_files(root):
    files, size = [], 0
    for path in root.iterdir():
        if path.name == ".installation.lock":
            continue
        if (
            path.is_symlink()
            or not path.is_file()
            or path.suffix not in (".pending", ".guard", ".aborted")
        ):
            raise ValueError(
                "Deletion state contains an unrecognized or redirected artifact"
            )
        size += path.stat().st_size
        if len(files) >= MAX_RECEIPTS or size > MAX_STATE_BYTES:
            raise ValueError("Deletion state exceeds its complete-history bound")
        files.append(path)
    return files


def read_state(path, settings):
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("Deletion state file is oversized")
    # Runtime trusts the installation key and retained receipt hashes. Restore
    # separately requires the operator's independently retained current digest.
    with path.open("rb") as stream:
        content = stream.read(MAX_BYTES + 1)
    return read_guard(path, hashlib.sha256(content).hexdigest(), settings)


def local_entries(hub):
    entries = []
    organizations = hub.organizations()
    for org in organizations:
        with hub.store(org["id"]).connect() as db:
            size = 0
            for row in db.execute(
                "SELECT id,payload FROM records WHERE kind='deletion_receipt'"
            ):
                size += len(row[1].encode())
                if len(entries) >= MAX_RECEIPTS or size > MAX_BYTES:
                    raise ValueError(
                        "Deletion receipts exceed the complete-history bound"
                    )
                value = json.loads(row[1])
                if row[0] != value["id"]:
                    raise ValueError("Deletion receipt identity changed")
                entries.append(receipt_entry(value, org["id"]))
    payload = {
        "schema": SCHEMA,
        "created_at": now(),
        "workspaces": [org["id"] for org in organizations],
        "receipts": entries,
    }
    if organizations:
        validate_payload(payload)
        if len(canonical(payload).encode()) > MAX_BYTES:
            raise ValueError("Deletion receipts exceed the complete-history byte bound")
    return entries


def verify_runtime(hub, settings):
    entries = local_entries(hub)
    current = {(item["workspace_id"], item["receipt_id"]): item for item in entries}
    if settings.deletion_state_directory is None:
        if entries:
            raise ValueError(
                "Deletion receipts require their original external DELETION_STATE_DIRECTORY"
            )
        return
    files = state_files(directory(settings))
    if any(path.suffix == ".pending" for path in files):
        raise ValueError(
            "An interrupted deletion requires offline reconciliation before startup or another deletion"
        )
    external = {}
    for path in files:
        payload = read_state(path, settings)
        if path.suffix == ".aborted":
            # The extension is not authenticated. Bind an aborted publication
            # to the exact cancellation saved by rollback reconciliation, and
            # require every prior receipt in that guard to remain committed.
            uncommitted = [
                item
                for item in payload["receipts"]
                if (item["workspace_id"], item["receipt_id"]) not in current
            ]
            if len(uncommitted) != 1:
                raise ValueError(
                    "Aborted deletion state does not identify exactly one cancelled execution"
                )
            aborted = uncommitted[0]
            if path.stem != aborted["request_id"]:
                raise ValueError(
                    "Aborted deletion filename does not match its authenticated request"
                )
            with hub.store(aborted["workspace_id"]).connect() as db:
                request = get(db, "deletion_request", aborted["request_id"])
            if (
                request["status"] != "cancelled"
                or request.get("aborted_execution_receipt_id") != aborted["receipt_id"]
                or request["customer_id"] != aborted["customer_id"]
            ):
                raise ValueError(
                    "Aborted deletion state lacks its matching cancelled request"
                )
            if any(
                current.get((item["workspace_id"], item["receipt_id"])) != item
                for item in payload["receipts"]
                if item is not aborted
            ):
                raise ValueError(
                    "Aborted deletion state contains missing or changed prior receipts"
                )
            continue
        for item in payload["receipts"]:
            identity = (item["workspace_id"], item["receipt_id"])
            if identity in external and external[identity] != item:
                raise ValueError("External deletion history conflicts")
            external[identity] = item
    if external != current:
        raise ValueError(
            "External deletion history and live receipts differ; do not replace missing history or start a rolled-back installation"
        )
    from deletion_guard import TABLE_KEYS

    for item in entries:
        with hub.store(item["workspace_id"]).connect() as db:
            for candidate in item["candidates"]:
                table, column = candidate["table"], TABLE_KEYS[candidate["table"]]
                query = f"SELECT 1 FROM {table} WHERE {column}=?"
                parameters = (candidate["record_id"],)
                if table == "records":
                    query += " AND kind=?"
                    parameters += (candidate["kind"],)
                if db.execute(query + " LIMIT 1", parameters).fetchone():
                    raise ValueError(
                        "Deleted operational records reappeared; startup is refused"
                    )


def sync_directory(root):
    if os.name != "nt":
        handle = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(handle)
        finally:
            os.close(handle)


def complete_file(pending, suffix):
    target = pending.with_suffix(suffix)
    if target.exists():
        raise ValueError("Deletion state outcome already exists")
    os.replace(pending, target)
    sync_directory(target.parent)
    return target


def validate_approval(hub, value, workspace_id):
    if (
        value["workspace_id"] != workspace_id
        or value["status"] != "approved"
        or value["created_by"] == value.get("approved_by")
    ):
        raise ValueError(
            "Execution requires an independently approved request in this workspace"
        )
    with hub.connect() as db:
        author = db.execute(
            "SELECT role FROM memberships WHERE user_id=? AND org_id=?",
            (value["created_by"], workspace_id),
        ).fetchone()
        reviewer = db.execute(
            "SELECT role FROM memberships WHERE user_id=? AND org_id=?",
            (value["approved_by"], workspace_id),
        ).fetchone()
    if (
        not author
        or author[0] != "admin"
        or not reviewer
        or reviewer[0] not in ("admin", "reviewer")
    ):
        raise ValueError(
            "Deletion maker/checker no longer have the required memberships"
        )
    if (
        not value.get("acknowledge_retained_audit")
        or not value.get("acknowledge_physical_and_restore_limits")
        or not value.get("discovery_evidence_sha256")
    ):
        raise ValueError(
            "Deletion request lacks reviewed discovery evidence and retained-data acknowledgements"
        )


def execute(
    settings, workspace_id, request_id, reason, *, acknowledge_retained_data=False
):
    if not encrypted(settings):
        raise ValueError(
            "Logical deletion requires the explicit SQLCipher trust baseline"
        )
    if not acknowledge_retained_data or not 20 <= len(reason) <= 2000:
        raise ValueError(
            "Acknowledge retained audit/pages/copies and supply an execution reason of 20–2000 characters"
        )
    workspace_id, request_id = str(uuid.UUID(workspace_id)), str(uuid.UUID(request_id))
    with InstallationLock(settings.database_path.parent):
        hub = Hub(settings)
        verify_runtime(hub, settings)
        root = directory(settings)
        with InstallationLock(root):
            files = state_files(root)
            if len(files) >= MAX_RECEIPTS:
                raise ValueError("Deletion state history reached its pilot bound")
            store = hub.store(workspace_id)
            pending = root / (request_id + ".pending")
            with store.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                value = get(db, "deletion_request", request_id)
                validate_approval(hub, value, workspace_id)
                require_live(value)
                current = current_plan(db, workspace_id, value)
                if any(
                    item["code"] != "external_copy_reconciliation_required"
                    for item in current["blockers"]
                ):
                    raise problem(
                        409,
                        "deletion_execution_blocked",
                        "Retention, hold, shared-reference or custody blockers remain",
                    )
                stamp = now()
                receipt = {
                    "id": uid(),
                    "created_at": stamp,
                    "workspace_id": workspace_id,
                    "request_id": request_id,
                    "customer_id": value["customer_id"],
                    "inventory_sha256": value["inventory_sha256"],
                    "status": "executed",
                    "maker_id": value["created_by"],
                    "reviewer_id": value["approved_by"],
                    "executed_by": "offline-operator",
                    "reason": reason,
                    "deleted_records": current["candidates"],
                    "scope": "Logical operational-row removal only. Immutable audit/governance, free pages/WAL and external copies remain outside this receipt's erasure claim.",
                }
                # Publish the entire prospective suppression set BEFORE deleting.
                # A crash/rollback leaves an authenticated pending file that
                # blocks startup until an operator proves commit or full rollback.
                result = export_guard(
                    settings, pending, prospective_receipt=receipt, already_locked=True
                )
                if (
                    sum(path.stat().st_size for path in files) + pending.stat().st_size
                    > MAX_STATE_BYTES
                ):
                    raise ValueError(
                        "Deletion publication exceeds its complete-history byte bound; reconcile the pending operation"
                    )
                sync_directory(root)
                for item in reversed(current["candidates"]):
                    table = item["table"]
                    if table not in (
                        "records",
                        "transactions",
                        "alerts",
                        "jobs",
                        "job_steps",
                        "decisions",
                        "reviews",
                    ):
                        raise ValueError("Deletion candidate table is unsupported")
                    row = db.execute(
                        f"SELECT rowid AS _rowid,* FROM {table} WHERE rowid=?",
                        (item["rowid"],),
                    ).fetchone()
                    if row is None or digest(dict(row)) != item["sha256"]:
                        raise ValueError(
                            "An execution candidate changed; transaction rolled back"
                        )
                    if (
                        db.execute(
                            f"DELETE FROM {table} WHERE rowid=?", (item["rowid"],)
                        ).rowcount
                        != 1
                    ):
                        raise ValueError(
                            "Deletion did not remove exactly one pinned row"
                        )
                require_live(value)
                save(db, "deletion_receipt", receipt)
                value.update(
                    status="executed",
                    receipt_id=receipt["id"],
                    executed_at=stamp,
                    scope=receipt["scope"],
                )
                append_event(db, value, {"id": "offline-operator"}, "executed", reason)
                audit(
                    db,
                    "offline-operator",
                    "deletion_executed",
                    {
                        "receipt_id": receipt["id"],
                        "receipt_sha256": digest(receipt),
                        "records": len(receipt["deleted_records"]),
                    },
                )
            target = complete_file(pending, ".guard")
            return {
                "receipt_id": receipt["id"],
                "deleted_records": len(receipt["deleted_records"]),
                "guard_path": str(target),
                "guard_sha256": result["sha256"],
                "physical_erasure_proven": False,
            }


def reconcile(settings, workspace_id, request_id, outcome, reason):
    if outcome not in ("commit", "abort") or not 20 <= len(reason) <= 2000:
        raise ValueError("Choose commit or abort and provide a reconciliation reason")
    workspace_id, request_id = str(uuid.UUID(workspace_id)), str(uuid.UUID(request_id))
    with InstallationLock(settings.database_path.parent):
        hub = Hub(settings)
        root = directory(settings)
        with InstallationLock(root):
            pending = root / (request_id + ".pending")
            payload = read_state(pending, settings)
            matches = [
                item
                for item in payload["receipts"]
                if item["workspace_id"] == workspace_id
                and item["request_id"] == request_id
            ]
            if len(matches) != 1:
                raise ValueError("Pending deletion does not match workspace/request")
            expected = matches[0]
            store = hub.store(workspace_id)
            with store.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                value = get(db, "deletion_request", request_id)
                if outcome == "commit":
                    receipt = get(db, "deletion_receipt", expected["receipt_id"])
                    if (
                        receipt_entry(receipt, workspace_id) != expected
                        or value["status"] != "executed"
                        or value.get("receipt_id") != expected["receipt_id"]
                    ):
                        raise ValueError("A matching committed receipt is required")
                    from deletion_guard import TABLE_KEYS

                    for item in expected["candidates"]:
                        table, column = item["table"], TABLE_KEYS[item["table"]]
                        if db.execute(
                            f"SELECT 1 FROM {table} WHERE {column}=? LIMIT 1",
                            (item["record_id"],),
                        ).fetchone():
                            raise ValueError(
                                "A committed deletion still has operational targets"
                            )
                else:
                    if (
                        not (
                            value["status"] == "approved"
                            or (
                                value["status"] == "cancelled"
                                and value.get("aborted_execution_receipt_id")
                                == expected["receipt_id"]
                            )
                        )
                        or db.execute(
                            "SELECT 1 FROM records WHERE kind='deletion_receipt' AND id=?",
                            (expected["receipt_id"],),
                        ).fetchone()
                    ):
                        raise ValueError("Cannot abort a committed or changed deletion")
                    current_plan(db, workspace_id, value)
                    if value["status"] == "approved":
                        value.update(
                            status="cancelled",
                            aborted_execution_receipt_id=expected["receipt_id"],
                        )
                        append_event(
                            db,
                            value,
                            {"id": "offline-operator"},
                            "execution_aborted",
                            reason,
                        )
                audit(
                    db,
                    "offline-operator",
                    "deletion_reconciled",
                    {"request_id": request_id, "outcome": outcome, "reason": reason},
                )
            target = complete_file(
                pending, ".guard" if outcome == "commit" else ".aborted"
            )
            verify_runtime(hub, settings)
            return {
                "outcome": outcome,
                "guard_path": str(target),
                "guard_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                "physical_erasure_proven": False,
            }
