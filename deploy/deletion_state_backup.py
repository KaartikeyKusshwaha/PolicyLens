"""Authenticated encrypted copies of complete stopped-installation deletion state."""

import argparse
import base64
import hashlib
import hmac
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from cryptography.fernet import Fernet

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from auth import Hub  # noqa: E402
from config import Settings  # noqa: E402
from deletion_execution import directory, state_files, verify_runtime, sync_directory  # noqa: E402
from deletion_guard import MAX_BYTES, guard_key, validate_payload  # noqa: E402
from operations import canonical  # noqa: E402
from runtime import InstallationLock  # noqa: E402

SCHEMA = "policylens.deletion-state-backup.v1"
MAX_BUNDLE_BYTES = 96 * 1024 * 1024
STAGING_ROOT = Path("/var/backups/policylens-deletion-state")


def sign(payload, settings):
    return {
        "payload": payload,
        "hmac_sha256": hmac.new(
            guard_key(settings), canonical(payload).encode(), hashlib.sha256
        ).hexdigest(),
    }


def authenticate(document, settings):
    if not isinstance(document, dict) or set(document) != {"payload", "hmac_sha256"}:
        raise ValueError("Invalid authenticated deletion document")
    expected = sign(document["payload"], settings)["hmac_sha256"]
    if not isinstance(document["hmac_sha256"], str) or not hmac.compare_digest(
        expected, document["hmac_sha256"]
    ):
        raise ValueError("Deletion backup authentication failed")
    return document["payload"]


def export_bundle(settings):
    with InstallationLock(settings.database_path.parent):
        hub = Hub(settings)
        root = directory(settings)
        with InstallationLock(root):
            verify_runtime(hub, settings)
            files = {}
            for path in sorted(state_files(root)):
                if path.suffix not in (".guard", ".aborted"):
                    raise ValueError("Reconcile pending deletion state before export")
                if path.stat().st_size > MAX_BYTES:
                    raise ValueError("Deletion state artifact oversized")
                files[path.name] = base64.b64encode(path.read_bytes()).decode()
            # Empty external state is valid only before any deletion. A receiver
            # with prior history refuses rollback to such an empty bundle.
            payload = {
                "schema": SCHEMA,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "files": files,
            }
            content = (canonical(sign(payload, settings)) + "\n").encode()
            if len(content) > MAX_BUNDLE_BYTES:
                raise ValueError("Complete deletion state backup exceeds its bound")
            return content


def verify_bundle(content, settings, *, at=None, max_age_hours=30):
    if not isinstance(content, bytes) or len(content) > MAX_BUNDLE_BYTES:
        raise ValueError("Deletion state bundle exceeds its bound")
    payload = authenticate(json.loads(content), settings)
    if set(payload) != {"schema", "created_at", "files"} or payload["schema"] != SCHEMA:
        raise ValueError("Unsupported deletion state backup")
    at = at or datetime.now(timezone.utc)
    stamp = datetime.fromisoformat(payload["created_at"])
    if (
        stamp.tzinfo is None
        or stamp > at + timedelta(minutes=5)
        or stamp < at - timedelta(hours=max_age_hours)
    ):
        raise ValueError("Deletion state backup is stale or future dated")
    if not isinstance(payload["files"], dict) or len(payload["files"]) > 2000:
        raise ValueError("Deletion state backup inventory invalid")
    records = {}
    for name, encoded in payload["files"].items():
        import uuid

        path = Path(name)
        if (
            path.name != name
            or path.suffix not in (".guard", ".aborted")
            or str(uuid.UUID(path.stem)) != path.stem
        ):
            raise ValueError("Unsafe deletion state artifact name")
        if not isinstance(encoded, str) or len(encoded) > 4 * ((MAX_BYTES + 2) // 3):
            raise ValueError("Deletion state artifact exceeds its bound")
        raw = base64.b64decode(encoded, validate=True)
        if len(raw) > MAX_BYTES:
            raise ValueError("Deletion state artifact exceeds its bound")
        guard = authenticate(json.loads(raw), settings)
        validate_payload(guard)
        records[name] = hashlib.sha256(raw).hexdigest()
    return {"created_at": payload["created_at"], "files": records}


def persist(
    content, installation_key, encryption_key, destination, *, max_age_hours=30
):
    destination = Path(destination).absolute()
    if destination.resolve() != destination:
        raise ValueError("Deletion backup destination cannot be redirected")
    for path in (installation_key, encryption_key):
        if Path(path).resolve().is_relative_to(destination):
            raise ValueError("Keep recovery keys outside deletion backups")
    settings = SimpleNamespace(
        security_key_path=Path(installation_key), deployment_mode="public"
    )
    inventory = verify_bundle(content, settings, max_age_hours=max_age_hours)
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    cipher = Fernet(Path(encryption_key).read_bytes().strip())
    with InstallationLock(destination):
        # Read and authenticate every retained encrypted bundle. No mutable
        # last-success receipt can authorize dropping historical artifacts.
        prior, count, total, newest = {}, 0, 0, None
        for path in destination.iterdir():
            if path.name == ".installation.lock":
                continue
            if path.is_symlink() or not path.is_file() or path.suffix != ".fernet":
                raise ValueError(
                    "Deletion backup history contains unknown/pending artifacts"
                )
            count += 1
            total += path.stat().st_size
            if (
                count > 2000
                or total > 512 * 1024 * 1024
                or path.stat().st_size > 2 * MAX_BUNDLE_BYTES
            ):
                raise ValueError(
                    "Deletion backup history exceeds its complete verification bound"
                )
            old = verify_bundle(
                cipher.decrypt(path.read_bytes()),
                settings,
                max_age_hours=100 * 365 * 24,
            )
            old_stamp = datetime.fromisoformat(old["created_at"])
            newest = max(newest, old_stamp) if newest else old_stamp
            for name, digest in old["files"].items():
                if name in prior and prior[name] != digest:
                    raise ValueError("Retained deletion backup history conflicts")
                prior[name] = digest
        if (
            newest is not None
            and datetime.fromisoformat(inventory["created_at"]) < newest
        ):
            raise ValueError("New deletion state predates previously retained history")
        if any(
            inventory["files"].get(name) != digest for name, digest in prior.items()
        ):
            raise ValueError(
                "New deletion state omits or changes previously retained history"
            )
        digest = hashlib.sha256(content).hexdigest()
        target = destination / ("deletion-state-" + digest + ".fernet")
        if not target.exists():
            if count >= 2000 or total + len(content) * 2 > 512 * 1024 * 1024:
                raise ValueError("Deletion backup history has no publication capacity")
            encrypted = cipher.encrypt(content)
            verify_bundle(
                cipher.decrypt(encrypted), settings, max_age_hours=max_age_hours
            )
            pending = target.with_suffix(".pending")
            descriptor = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(encrypted)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(pending, target)
            sync_directory(destination)
        return {
            "success": True,
            "bundle_sha256": digest,
            "archive": target.name,
            "encrypted_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            "encrypted_bytes": target.stat().st_size,
            "artifacts": len(inventory["files"]),
            "source_created_at": inventory["created_at"],
            "scope": "Authenticated encrypted complete deletion history copy; current recovery guard digest still requires independent retention. No physical erasure or deployed off-machine custody proof.",
        }


def recover(
    archive, installation_key, encryption_key, destination, trusted_bundle_sha256
):
    """Reconstruct a separately trusted current state copy into a NEW directory."""
    archive, destination = Path(archive), Path(destination).absolute()
    if (
        archive.is_symlink()
        or not archive.is_file()
        or archive.stat().st_size > 2 * MAX_BUNDLE_BYTES
    ):
        raise ValueError("Deletion recovery archive missing, redirected or oversized")
    if destination.resolve() != destination or destination.exists():
        raise ValueError(
            "Deletion recovery requires a new directory without redirected parents"
        )
    settings = SimpleNamespace(
        security_key_path=Path(installation_key), deployment_mode="public"
    )
    content = Fernet(Path(encryption_key).read_bytes().strip()).decrypt(
        archive.read_bytes()
    )
    if not isinstance(trusted_bundle_sha256, str) or not hmac.compare_digest(
        hashlib.sha256(content).hexdigest(), trusted_bundle_sha256
    ):
        raise ValueError(
            "Deletion recovery bundle does not match the independently retained current SHA-256"
        )
    inventory = verify_bundle(content, settings, max_age_hours=100 * 365 * 24)
    payload = authenticate(json.loads(content), settings)
    destination.mkdir(parents=True, mode=0o700)
    with InstallationLock(destination):
        incomplete = destination / "restoration.pending"
        descriptor = os.open(incomplete, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(
                b"Incomplete external deletion history restoration. Do not start service.\n"
            )
            stream.flush()
            os.fsync(stream.fileno())
        for name, encoded in payload["files"].items():
            raw = base64.b64decode(encoded, validate=True)
            descriptor = os.open(
                destination / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
            )
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
        sync_directory(destination)
        incomplete.unlink()
        sync_directory(destination)
    return {
        "restored_artifacts": len(inventory["files"]),
        "bundle_sha256": trusted_bundle_sha256,
        "source_modified": False,
        "scope": "External history restored only; database restore and runtime receipt/target checks remain required.",
    }


def staged_files(root):
    files, total = [], 0
    for path in root.iterdir():
        if path.name == ".installation.lock":
            continue
        if (
            path.is_symlink()
            or not path.is_file()
            or not re.fullmatch(r"state-\d{8}T\d{12}Z-[a-f0-9]{64}\.json", path.name)
        ):
            raise ValueError(
                "Deletion staging contains incomplete or unknown artifacts"
            )
        total += path.stat().st_size
        if len(files) >= 2000 or total > 512 * 1024 * 1024:
            raise ValueError("Deletion staging history exceeds its bound")
        files.append(path)
    return files, total


def stage(settings, root=STAGING_ROOT):
    root = Path(root).absolute()
    if root.resolve() != root or root.is_relative_to(
        settings.database_path.parent.resolve()
    ):
        raise ValueError(
            "Deletion staging must be outside database storage without redirection"
        )
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name != "nt" and root.stat().st_mode & 0o077:
        raise ValueError("Deletion staging permissions must be 0700")
    with InstallationLock(root):
        files, total = staged_files(root)
        content = export_bundle(settings)
        if len(files) >= 2000 or total + len(content) > 512 * 1024 * 1024:
            raise ValueError("Deletion staging has no publication capacity")
        digest = hashlib.sha256(content).hexdigest()
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        target = root / ("state-" + stamp + "-" + digest + ".json")
        pending = target.with_suffix(".pending")
        if target.exists():
            raise ValueError("Deletion staging identity already exists")
        descriptor = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(pending, target)
        sync_directory(root)
        return {"staged": True, "bundle_sha256": digest, "file": target.name}


def latest(settings, root=STAGING_ROOT):
    root = Path(root).absolute()
    if root.resolve() != root or not root.is_dir():
        raise ValueError("Deletion staging directory unavailable or redirected")
    if os.name != "nt" and root.stat().st_mode & 0o077:
        raise ValueError("Deletion staging permissions must be 0700")
    with InstallationLock(root):
        files, _ = staged_files(root)
        if not files:
            raise ValueError("No complete staged deletion history is available")
        selected = max(files)
        if selected.stat().st_size > MAX_BUNDLE_BYTES:
            raise ValueError("Staged deletion bundle oversized")
        with selected.open("rb") as stream:
            content = stream.read(MAX_BUNDLE_BYTES + 1)
        if hashlib.sha256(content).hexdigest() != selected.stem.rsplit("-", 1)[1]:
            raise ValueError("Staged deletion history checksum changed")
        verify_bundle(content, settings)
        return content


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser(
        "export",
        help="Write authenticated state to stdout from a stopped server; no installation keys included.",
    )
    commands.add_parser(
        "stage",
        help="Stage complete state while stopped for the fixed verified-SSH exporter.",
    )
    commands.add_parser(
        "latest",
        help="Read the newest authenticated staged state; never fall back after failure.",
    )
    receive = commands.add_parser(
        "receive", help="Verify stdin and retain an encrypted complete-history copy."
    )
    receive.add_argument("--installation-key", type=Path, required=True)
    receive.add_argument("--encryption-key", type=Path, required=True)
    receive.add_argument("--destination", type=Path, required=True)
    restore = commands.add_parser(
        "recover",
        help="Reconstruct authenticated external history into a NEW directory using a separately trusted current digest.",
    )
    restore.add_argument("--archive", type=Path, required=True)
    restore.add_argument("--installation-key", type=Path, required=True)
    restore.add_argument("--encryption-key", type=Path, required=True)
    restore.add_argument("--destination", type=Path, required=True)
    restore.add_argument("--bundle-sha256", required=True)
    args = parser.parse_args()
    try:
        if args.command == "export":
            sys.stdout.buffer.write(export_bundle(Settings()))
        elif args.command == "stage":
            print(json.dumps(stage(Settings())))
        elif args.command == "latest":
            sys.stdout.buffer.write(latest(Settings()))
        elif args.command == "receive":
            content = sys.stdin.buffer.read(MAX_BUNDLE_BYTES + 1)
            print(
                json.dumps(
                    persist(
                        content,
                        args.installation_key,
                        args.encryption_key,
                        args.destination,
                    )
                )
            )
        else:
            print(
                json.dumps(
                    recover(
                        args.archive,
                        args.installation_key,
                        args.encryption_key,
                        args.destination,
                        args.bundle_sha256,
                    )
                )
            )
        return 0
    except Exception:
        print(
            "Deletion state backup failed; inspect trusted operator configuration and retained history.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
