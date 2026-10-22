"""Signed external audit anchors. Database-only rewrites cannot replace retained anchors."""

import base64
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from operations import canonical
from runtime import InstallationLock
from security import SecretBox
from store import now
from database import DB_ERRORS

ZERO = "0" * 64
SCHEMA = "policylens.audit-checkpoint.v1"
MAX_EVENTS = 100000
MAX_BUNDLE_BYTES = 8_000_000


class AuditBundleLimit(ValueError):
    """Export size alone must not be reported as automatic retention failure."""


def verify_signature(document, fingerprint=None):
    try:
        if (
            set(document) != {"payload", "public_key", "signature", "algorithm"}
            or document["algorithm"] != "Ed25519"
        ):
            raise ValueError("Unsupported signed checkpoint.")
        payload = document["payload"]
        fields = {
            "schema",
            "workspace_id",
            "sequence",
            "head_hash",
            "created_at",
            "previous_checkpoint_sha256",
        }
        if set(payload) != fields or payload["schema"] != SCHEMA:
            raise ValueError("Unsupported checkpoint payload.")
        if (
            not isinstance(payload["workspace_id"], str)
            or str(uuid.UUID(payload["workspace_id"])) != payload["workspace_id"]
        ):
            raise ValueError("Invalid workspace identity.")
        if (
            type(payload["sequence"]) is not int
            or not 0 <= payload["sequence"] <= 1000000000
        ):
            raise ValueError("Invalid checkpoint sequence.")
        if not all(
            re.fullmatch(r"[0-9a-f]{64}", payload[name])
            for name in ("head_hash", "previous_checkpoint_sha256")
        ):
            raise ValueError("Invalid checkpoint hash.")
        if datetime.fromisoformat(payload["created_at"]).tzinfo is None:
            raise ValueError("Checkpoint timestamp must include a timezone.")
        public = base64.b64decode(document["public_key"], validate=True)
        signature = base64.b64decode(document["signature"], validate=True)
        actual = hashlib.sha256(public).hexdigest()
        if fingerprint is not None:
            if (
                not isinstance(fingerprint, str)
                or not re.fullmatch(r"[0-9a-f]{64}", fingerprint)
                or not hmac.compare_digest(actual, fingerprint)
            ):
                raise ValueError(
                    "Checkpoint signing identity does not match the trusted fingerprint."
                )
        Ed25519PublicKey.from_public_bytes(public).verify(
            signature, canonical(payload).encode()
        )
    except (KeyError, TypeError, ValueError, InvalidSignature) as exc:
        raise ValueError("Signed checkpoint verification failed.") from exc
    return {
        "signature_valid": True,
        "trusted_key": fingerprint is not None,
        "fingerprint": actual,
    }


def verify_chain(events, anchor=None):
    previous, sequence, matched = ZERO, 0, anchor is None
    if anchor and anchor["sequence"] == 0:
        matched = anchor["head_hash"] == ZERO
    for row in events:
        if not hasattr(row, "keys") or set(row.keys()) != {
            "seq",
            "at",
            "actor",
            "action",
            "data",
            "previous",
            "hash",
        }:
            raise ValueError("Unsupported audit event fields.")
        sequence += 1
        if sequence > MAX_EVENTS:
            raise ValueError(
                "Audit verification exceeds the 100,000-event pilot bound."
            )
        if any(
            not isinstance(row[name], str)
            for name in ("at", "actor", "action", "previous", "hash")
        ):
            raise ValueError("Invalid audit event types.")
        data = (
            row["data"]
            if isinstance(row["data"], dict)
            else json.loads(row["data"])
            if isinstance(row["data"], str)
            else None
        )
        if not isinstance(data, dict):
            raise ValueError("Audit event data must be an object.")
        content = canonical(
            {
                "at": row["at"],
                "actor": row["actor"],
                "action": row["action"],
                "data": data,
                "previous": previous,
            }
        )
        expected = hashlib.sha256(content.encode()).hexdigest()
        if (
            type(row["seq"]) is not int
            or row["seq"] != sequence
            or row["previous"] != previous
            or row["hash"] != expected
        ):
            raise ValueError("Audit chain is incomplete or has been modified.")
        previous = expected
        if anchor and sequence == anchor["sequence"]:
            matched = hmac.compare_digest(previous, anchor["head_hash"])
    if not matched:
        raise ValueError(
            "Database history conflicts with a retained external checkpoint."
        )
    return {"sequence": sequence, "head_hash": previous}


def verify_bundle(bundle, fingerprint):
    if not isinstance(fingerprint, str) or not re.fullmatch(
        r"[0-9a-f]{64}", fingerprint
    ):
        raise ValueError(
            "Supply the checkpoint fingerprint trusted independently of this bundle."
        )
    if (
        not isinstance(bundle, dict)
        or bundle.get("format") != "policylens.audit-bundle.v1"
        or set(bundle) != {"format", "checkpoint", "events"}
        or not isinstance(bundle.get("events"), list)
    ):
        raise ValueError("Unsupported audit bundle.")
    signed = verify_signature(bundle["checkpoint"], fingerprint)
    payload = bundle["checkpoint"]["payload"]
    result = verify_chain(bundle["events"], payload)
    if (
        result["sequence"] != payload["sequence"]
        or result["head_hash"] != payload["head_hash"]
    ):
        raise ValueError(
            "Bundle contains an unsigned tail or omits checkpointed events."
        )
    return {
        **signed,
        **result,
        "workspace_id": payload["workspace_id"],
        "fully_anchored": True,
    }


class Checkpoints:
    def __init__(self, hub, settings):
        self.hub, self.settings = hub, settings
        self.errors = {}
        self._thread_lock = threading.Lock()
        self._last_tick = 0

    def root(self):
        configured = self.settings.checkpoint_directory
        if configured is None:
            raise ValueError("External checkpoints are not configured.")
        root = Path(configured).resolve()
        data = self.settings.database_path.parent.resolve()
        if root == data or root.is_relative_to(data):
            raise ValueError(
                "Checkpoint storage must be outside the installation database directory."
            )
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if os.name != "nt" and root.stat().st_mode & 0o077:
            raise ValueError("Checkpoint storage permissions must be 0700.")
        return root

    def signing_key(self, root):
        has_anchors = next(root.glob("*/checkpoint-*.json"), None) is not None
        master = SecretBox(self.settings).key(create=not has_anchors)
        seed = hmac.new(
            master, b"policylens:checkpoint-signing:v1", hashlib.sha256
        ).digest()
        return Ed25519PrivateKey.from_private_bytes(seed)

    @staticmethod
    def identity(key):
        public = key.public_key().public_bytes_raw()
        return base64.b64encode(public).decode(), hashlib.sha256(public).hexdigest()

    @staticmethod
    def workspace(root, org_id):
        name = str(uuid.UUID(org_id))
        if name != org_id:
            raise ValueError("Use a registered workspace ID.")
        directory = root / name
        if directory.resolve() != directory:
            raise ValueError("Workspace checkpoint paths cannot be redirected.")
        directory.mkdir(exist_ok=True, mode=0o700)
        return directory

    @staticmethod
    def latest(directory, fingerprint, org_id):
        files = sorted(directory.glob("checkpoint-*.json"))
        if len(files) > 100000:
            raise ValueError(
                "Checkpoint storage exceeds the pilot bound; apply the approved retention policy."
            )
        if not files:
            return None
        file = files[-1]
        if (
            file.is_symlink()
            or file.resolve().parent != directory
            or file.stat().st_size > 16384
        ):
            raise ValueError("Checkpoint file is unsafe or too large.")
        document = json.loads(file.read_text(encoding="utf-8"))
        verify_signature(document, fingerprint)
        payload = document["payload"]
        expected = (
            f"checkpoint-{payload['sequence']:020d}-{payload['head_hash'][:16]}.json"
        )
        if file.name != expected or payload["workspace_id"] != org_id:
            raise ValueError(
                "Checkpoint filename or workspace does not match its signature."
            )
        return document

    def capture(self, org_id, *, include_events=False, snapshot_reader=None):
        if snapshot_reader is not None and not include_events:
            raise ValueError(
                "A consistent evidence snapshot requires the audit bundle."
            )
        # Resolve through registered workspace membership before creating any paths.
        store = self.hub.store(org_id)
        root = self.root()
        with self._thread_lock, InstallationLock(root):
            key = self.signing_key(root)
            public, fingerprint = self.identity(key)
            directory = self.workspace(root, org_id)
            previous = self.latest(directory, fingerprint, org_id)
            with store.connect() as db:
                db.execute("BEGIN")
                rows = db.execute("SELECT * FROM audit_chain ORDER BY seq")
                if include_events:
                    events, size = [], 0
                    for row in rows:
                        if len(events) >= MAX_EVENTS:
                            raise ValueError(
                                "Audit export exceeds the pilot event bound."
                            )
                        size += (
                            sum(len(str(row[field]).encode()) for field in row.keys())
                            + 200
                        )
                        if size > MAX_BUNDLE_BYTES:
                            raise AuditBundleLimit(
                                "Audit bundle exceeds the 8 MB export bound; use a scoped evidence pack."
                            )
                        events.append({**dict(row), "data": json.loads(row["data"])})
                    result = verify_chain(
                        events, previous["payload"] if previous else None
                    )
                else:
                    events = None
                    result = verify_chain(
                        rows, previous["payload"] if previous else None
                    )
                snapshot = snapshot_reader(db) if snapshot_reader is not None else None
            if previous and previous["payload"]["sequence"] == result["sequence"]:
                document = previous
            else:
                payload = {
                    "schema": SCHEMA,
                    "workspace_id": org_id,
                    **result,
                    "created_at": now(),
                    "previous_checkpoint_sha256": hashlib.sha256(
                        canonical(previous).encode()
                    ).hexdigest()
                    if previous
                    else ZERO,
                }
                document = {
                    "payload": payload,
                    "public_key": public,
                    "signature": base64.b64encode(
                        key.sign(canonical(payload).encode())
                    ).decode(),
                    "algorithm": "Ed25519",
                }
                target = (
                    directory
                    / f"checkpoint-{result['sequence']:020d}-{result['head_hash'][:16]}.json"
                )
                temporary = directory / (
                    ".checkpoint-" + secrets.token_hex(12) + ".pending"
                )
                descriptor = os.open(
                    temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
                )
                with os.fdopen(descriptor, "w", encoding="utf-8") as output:
                    output.write(canonical(document) + "\n")
                    output.flush()
                    os.fsync(output.fileno())
                if target.exists():
                    raise ValueError(
                        "A conflicting checkpoint already exists; it was not overwritten."
                    )
                os.replace(temporary, target)
            self.errors.pop(org_id, None)
            if include_events:
                bundle = {
                    "format": "policylens.audit-bundle.v1",
                    "checkpoint": document,
                    "events": events,
                }
                return (bundle, snapshot) if snapshot_reader is not None else bundle
            return document

    def status(self, org_id):
        if self.settings.checkpoint_directory is None:
            return {"configured": False, "status": "not_configured"}
        try:
            root = self.root()
            _, fingerprint = self.identity(self.signing_key(root))
            directory = self.workspace(root, org_id)
            latest = self.latest(directory, fingerprint, org_id)
            with self.hub.store(org_id).connect() as db:
                db.execute("BEGIN")
                current = verify_chain(
                    db.execute("SELECT * FROM audit_chain ORDER BY seq"),
                    latest["payload"] if latest else None,
                )
            if org_id in self.errors:
                return {
                    "configured": True,
                    "status": "failed",
                    "code": self.errors[org_id],
                }
            return {
                "configured": True,
                "status": "retained" if latest else "pending",
                "fingerprint": fingerprint,
                "checkpoint": latest,
                "interval_seconds": self.settings.checkpoint_interval_seconds,
                "unanchored_events": current["sequence"]
                - (latest["payload"]["sequence"] if latest else 0),
                "scope": "Retained outside database storage; not proof of off-machine retention or resistance to host/signing-key compromise.",
            }
        except (ValueError, RuntimeError, OSError, *DB_ERRORS):
            self.errors[org_id] = "checkpoint_verification_failed"
            return {
                "configured": True,
                "status": "failed",
                "code": "checkpoint_verification_failed",
            }

    def tick(self, force=False):
        if self.settings.checkpoint_directory is None:
            return
        stamp = time.monotonic()
        if (
            not force
            and stamp - self._last_tick < self.settings.checkpoint_interval_seconds
        ):
            return
        self._last_tick = stamp
        for org in self.hub.organizations():
            try:
                self.capture(org["id"])
            except (ValueError, RuntimeError, OSError, *DB_ERRORS):
                self.errors[org["id"]] = "checkpoint_capture_failed"
                logging.getLogger("policylens.checkpoints").error(
                    "External checkpoint capture failed for workspace %s", org["id"]
                )
