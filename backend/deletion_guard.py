"""Key-authenticated, independently pinned deletion state for offline restores.

This guard refuses resurrection; it never deletes or rewrites a backup.
"""

import hashlib
import hmac
import json
import os
import re
import uuid
from contextlib import closing
from datetime import datetime
from pathlib import Path

from database import connect_database
from operations import canonical
from runtime import InstallationLock
from security import SecretBox
from store import now

SCHEMA = "policylens.deletion-restore-guard.v1"
MAX_BYTES = 8_000_000
MAX_RECEIPTS = 2000
MAX_CANDIDATES = 10000
TABLE_KEYS = {
    "records": "id",
    "transactions": "id",
    "alerts": "id",
    "jobs": "id",
    "job_steps": "job_id",
    "decisions": "id",
    "reviews": "id",
}
OPERATIONAL_KINDS = {
    "customer",
    "case",
    "case_note",
    "case_evidence",
    "task",
    "screening",
    "adapter_object",
}


def sha256(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def guard_key(settings, *, create=False):
    return hmac.new(
        SecretBox(settings).key(create=create),
        b"policylens:deletion-restore-guard:v1",
        hashlib.sha256,
    ).digest()


def valid_id(value):
    return isinstance(value, str) and 1 <= len(value) <= 100


def validate_payload(payload):
    if (
        not isinstance(payload, dict)
        or set(payload) != {"schema", "created_at", "workspaces", "receipts"}
        or payload["schema"] != SCHEMA
    ):
        raise ValueError("Unsupported deletion guard")
    try:
        if datetime.fromisoformat(payload["created_at"]).tzinfo is None:
            raise ValueError("Missing timezone")
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid deletion guard timestamp") from exc
    workspaces = payload["workspaces"]
    if not isinstance(workspaces, list) or not 1 <= len(workspaces) <= 10000:
        raise ValueError("Invalid guard workspaces")
    if any(
        not isinstance(value, str) or str(uuid.UUID(value)) != value
        for value in workspaces
    ) or len(set(workspaces)) != len(workspaces):
        raise ValueError("Invalid guard workspace identities")
    receipts = payload["receipts"]
    if not isinstance(receipts, list) or len(receipts) > MAX_RECEIPTS:
        raise ValueError("Deletion guard exceeds receipt bound")
    seen = set()
    count = 0
    for receipt in receipts:
        if not isinstance(receipt, dict) or set(receipt) != {
            "workspace_id",
            "receipt_id",
            "request_id",
            "receipt_sha256",
            "customer_id",
            "candidates",
        }:
            raise ValueError("Invalid deletion guard receipt")
        if receipt["workspace_id"] not in workspaces or any(
            not valid_id(receipt[name])
            for name in ("receipt_id", "request_id", "customer_id")
        ):
            raise ValueError("Invalid deletion guard receipt identity")
        if not isinstance(receipt["receipt_sha256"], str) or not re.fullmatch(
            r"[a-f0-9]{64}", receipt["receipt_sha256"]
        ):
            raise ValueError("Invalid deletion receipt hash")
        identity = (receipt["workspace_id"], receipt["receipt_id"])
        if identity in seen:
            raise ValueError("Duplicate deletion receipt")
        seen.add(identity)
        if not isinstance(receipt["candidates"], list) or not receipt["candidates"]:
            raise ValueError("Missing deletion targets")
        for item in receipt["candidates"]:
            count += 1
            if count > MAX_CANDIDATES:
                raise ValueError("Deletion guard exceeds target bound")
            if not isinstance(item, dict) or set(item) != {
                "table",
                "kind",
                "record_id",
            }:
                raise ValueError("Invalid deletion target")
            if (
                not isinstance(item["table"], str)
                or item["table"] not in TABLE_KEYS
                or not valid_id(item["record_id"])
            ):
                raise ValueError("Unsupported deletion target")
            if (
                not isinstance(item["kind"], str)
                or (
                    item["table"] == "records" and item["kind"] not in OPERATIONAL_KINDS
                )
                or (item["table"] != "records" and item["kind"] != item["table"])
            ):
                raise ValueError("Unsupported deletion target kind")
        if not any(
            item
            == {
                "table": "records",
                "kind": "customer",
                "record_id": receipt["customer_id"],
            }
            for item in receipt["candidates"]
        ):
            raise ValueError("Customer tombstone is missing")


def read_guard(path, trusted_sha256, settings):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ValueError("Deletion guard is missing, redirected or oversized")
    if not isinstance(trusted_sha256, str) or not re.fullmatch(
        r"[a-f0-9]{64}", trusted_sha256
    ):
        raise ValueError(
            "Supply the independently retained current deletion guard SHA-256"
        )
    with path.open("rb") as stream:
        content = stream.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES or not hmac.compare_digest(
        hashlib.sha256(content).hexdigest(), trusted_sha256
    ):
        raise ValueError("Deletion guard does not match its trusted SHA-256")
    document = json.loads(content)
    if not isinstance(document, dict) or set(document) != {"payload", "hmac_sha256"}:
        raise ValueError("Invalid deletion guard envelope")
    expected = hmac.new(
        guard_key(settings), canonical(document["payload"]).encode(), hashlib.sha256
    ).hexdigest()
    if not isinstance(document["hmac_sha256"], str) or not hmac.compare_digest(
        expected, document["hmac_sha256"]
    ):
        raise ValueError("Deletion guard authentication failed")
    validate_payload(document["payload"])
    return document["payload"]


def export_guard(settings, output):
    """Export only while the complete source installation is stopped."""
    root = settings.database_path.parent.resolve()
    output = Path(output).absolute()
    if (
        output.is_relative_to(root)
        or output.is_symlink()
        or output.parent.resolve() != output.parent
    ):
        raise ValueError(
            "Keep deletion guards outside the database directory without redirected paths"
        )
    with InstallationLock(root):
        if (root / "identity.db").is_symlink():
            raise ValueError("Identity database cannot be redirected")
        with closing(
            connect_database(root / "identity.db", settings, readonly=True)
        ) as db:
            organizations = db.execute(
                "SELECT id,db_path FROM organizations ORDER BY id"
            ).fetchall()
        receipts, total, targets = [], 0, 0
        for workspace_id, path in organizations:
            source = Path(path).resolve()
            if (
                Path(path).is_symlink()
                or not source.is_relative_to(root)
                or not source.is_file()
            ):
                raise ValueError(
                    "Workspace database is missing or outside the installation"
                )
            with closing(connect_database(source, settings, readonly=True)) as db:
                for row in db.execute(
                    "SELECT id,payload FROM records WHERE kind='deletion_receipt' ORDER BY id"
                ):
                    total += len(row[1].encode())
                    if len(receipts) >= MAX_RECEIPTS or total > MAX_BYTES:
                        raise ValueError("Deletion receipts exceed the guard bound")
                    value = json.loads(row[1])
                    if (
                        value["id"] != row[0]
                        or value["workspace_id"] != workspace_id
                        or value["status"] != "executed"
                    ):
                        raise ValueError("Invalid completed deletion receipt")
                    targets += len(value["deleted_records"])
                    if targets > MAX_CANDIDATES:
                        raise ValueError("Deletion guard exceeds target bound")
                    receipts.append(
                        {
                            "workspace_id": workspace_id,
                            "receipt_id": row[0],
                            "request_id": value["request_id"],
                            "receipt_sha256": sha256(value),
                            "customer_id": value["customer_id"],
                            "candidates": [
                                {
                                    name: item[name]
                                    for name in ("table", "kind", "record_id")
                                }
                                for item in value["deleted_records"]
                            ],
                        }
                    )
        payload = {
            "schema": SCHEMA,
            "created_at": now(),
            "workspaces": [row[0] for row in organizations],
            "receipts": receipts,
        }
        validate_payload(payload)
        document = {
            "payload": payload,
            "hmac_sha256": hmac.new(
                guard_key(settings, create=not receipts),
                canonical(payload).encode(),
                hashlib.sha256,
            ).hexdigest(),
        }
        content = (canonical(document) + "\n").encode()
        if len(content) > MAX_BYTES:
            raise ValueError("Complete deletion guard exceeds its byte bound")
        descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        return {
            "sha256": hashlib.sha256(content).hexdigest(),
            "receipts": len(receipts),
            "workspaces": len(organizations),
        }


def check_snapshot(directory, manifest, settings, payload):
    """Read all guard targets before creating a restore destination."""
    root = Path(directory).resolve()
    if not set(manifest["organization_paths"]).issubset(payload["workspaces"]):
        raise ValueError("Deletion guard omits a snapshot workspace")
    for workspace_id, relative in manifest["organization_paths"].items():
        from recovery import safe_child

        with closing(
            connect_database(safe_child(root, relative), settings, readonly=True)
        ) as db:
            receipts = [
                item
                for item in payload["receipts"]
                if item["workspace_id"] == workspace_id
            ]
            expected = {item["receipt_id"]: item["receipt_sha256"] for item in receipts}
            size = 0
            for index, row in enumerate(
                db.execute(
                    "SELECT id,payload FROM records WHERE kind='deletion_receipt'"
                )
            ):
                size += len(row[1].encode())
                if index >= MAX_RECEIPTS or size > MAX_BYTES:
                    raise ValueError(
                        "Snapshot deletion receipts exceed the guard bound"
                    )
                if expected.get(row[0]) != sha256(json.loads(row[1])):
                    raise ValueError(
                        "Deletion guard omits or changes a snapshot receipt"
                    )
            for receipt in receipts:
                for item in receipt["candidates"]:
                    table, column = item["table"], TABLE_KEYS[item["table"]]
                    query = f"SELECT 1 FROM {table} WHERE {column}=?"
                    parameters = (item["record_id"],)
                    if table == "records":
                        query += " AND kind=?"
                        parameters += (item["kind"],)
                    if db.execute(query + " LIMIT 1", parameters).fetchone():
                        raise ValueError(
                            "Snapshot would resurrect deleted operational records; restore refused"
                        )
