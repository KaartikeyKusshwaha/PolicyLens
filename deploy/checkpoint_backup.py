"""Complete signed checkpoint-history bundles and encrypted receiver retention."""

import argparse
import base64
import hashlib
import json
import os
import re
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from auth import Hub  # noqa: E402
from checkpoints import Checkpoints, verify_signature, ZERO  # noqa: E402
from config import Settings  # noqa: E402
from deletion_execution import sync_directory  # noqa: E402
from operations import canonical  # noqa: E402
from runtime import InstallationLock  # noqa: E402

SCHEMA = "policylens.checkpoint-history-backup.v1"
MAX_BYTES = 32 * 1024 * 1024
MAX_ANCHORS = 10000
STAGING_ROOT = Path("/var/backups/policylens-checkpoint-history")


def verify(content, fingerprint, *, max_age_hours=30, at=None):
    if (
        not isinstance(content, bytes)
        or len(content) > MAX_BYTES
        or not isinstance(fingerprint, str)
        or not re.fullmatch(r"[a-f0-9]{64}", fingerprint)
    ):
        raise ValueError("Checkpoint history input or trusted fingerprint invalid")
    document = json.loads(content)
    if (
        not isinstance(document, dict)
        or set(document) != {"payload", "public_key", "signature", "algorithm"}
        or document["algorithm"] != "Ed25519"
    ):
        raise ValueError("Unsupported checkpoint history envelope")
    public = base64.b64decode(document["public_key"], validate=True)
    if hashlib.sha256(public).hexdigest() != fingerprint:
        raise ValueError(
            "Checkpoint history signing identity differs from the trusted fingerprint"
        )
    try:
        Ed25519PublicKey.from_public_bytes(public).verify(
            base64.b64decode(document["signature"], validate=True),
            canonical(document["payload"]).encode(),
        )
    except InvalidSignature as exc:
        raise ValueError("Checkpoint history signature failed") from exc
    payload = document["payload"]
    if (
        not isinstance(payload, dict)
        or set(payload) != {"schema", "created_at", "workspaces"}
        or payload["schema"] != SCHEMA
    ):
        raise ValueError("Unsupported checkpoint history payload")
    stamp = datetime.fromisoformat(payload["created_at"])
    at = at or datetime.now(timezone.utc)
    if (
        stamp.tzinfo is None
        or stamp > at + timedelta(minutes=5)
        or stamp < at - timedelta(hours=max_age_hours)
    ):
        raise ValueError("Checkpoint history creation time is stale or future dated")
    workspaces = payload["workspaces"]
    if not isinstance(workspaces, dict) or not 1 <= len(workspaces) <= 2000:
        raise ValueError("Checkpoint history workspace inventory invalid")
    files, heads = {}, {}
    for workspace_id, anchors in workspaces.items():
        if (
            str(uuid.UUID(workspace_id)) != workspace_id
            or not isinstance(anchors, list)
            or not anchors
        ):
            raise ValueError("Invalid checkpoint workspace or missing history")
        previous, sequence = ZERO, -1
        for anchor in anchors:
            if len(files) >= MAX_ANCHORS or len(canonical(anchor).encode()) > 16384:
                raise ValueError("Checkpoint history exceeds its complete bound")
            verify_signature(anchor, fingerprint)
            value = anchor["payload"]
            if (
                value["workspace_id"] != workspace_id
                or value["sequence"] <= sequence
                or value["previous_checkpoint_sha256"] != previous
            ):
                raise ValueError("Checkpoint history was omitted, reordered or changed")
            previous, sequence = (
                hashlib.sha256(canonical(anchor).encode()).hexdigest(),
                value["sequence"],
            )
            name = (
                workspace_id
                + f"/checkpoint-{sequence:020d}-{value['head_hash'][:16]}.json"
            )
            files[name] = previous
        heads[workspace_id] = {"sequence": sequence, "checkpoint_sha256": previous}
    return {
        "created_at": payload["created_at"],
        "files": files,
        "heads": heads,
        "fingerprint": fingerprint,
    }


def export_bundle(settings):
    with InstallationLock(settings.database_path.parent):
        hub = Hub(settings)
        manager = Checkpoints(hub, settings)
        organizations = hub.organizations()
        if not organizations:
            raise ValueError("Complete workspace setup before exporting checkpoints")
        for org in organizations:
            manager.capture(org["id"])
        root = manager.root()
        with InstallationLock(root):
            key = manager.signing_key(root)
            public, fingerprint = manager.identity(key)
            workspaces, total, count = {}, 0, 0
            expected = {org["id"] for org in organizations}
            if {
                path.name
                for path in root.iterdir()
                if path.name != ".installation.lock"
            } != expected:
                raise ValueError(
                    "Checkpoint root contains unregistered or incomplete history"
                )
            for org in organizations:
                directory = manager.workspace(root, org["id"])
                anchors = []
                for path in sorted(directory.iterdir()):
                    if (
                        path.is_symlink()
                        or not path.is_file()
                        or not re.fullmatch(
                            r"checkpoint-\d{20}-[a-f0-9]{16}\.json", path.name
                        )
                        or path.stat().st_size > 16384
                    ):
                        raise ValueError(
                            "Checkpoint history contains unsafe/incomplete artifacts"
                        )
                    count += 1
                    total += path.stat().st_size
                    if count > MAX_ANCHORS or total > MAX_BYTES:
                        raise ValueError(
                            "Checkpoint history exceeds its complete export bound"
                        )
                    anchor = json.loads(path.read_bytes())
                    value = anchor["payload"]
                    if (
                        path.name
                        != f"checkpoint-{value['sequence']:020d}-{value['head_hash'][:16]}.json"
                    ):
                        raise ValueError(
                            "Checkpoint filename differs from signed content"
                        )
                    anchors.append(anchor)
                workspaces[org["id"]] = anchors
            payload = {
                "schema": SCHEMA,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "workspaces": workspaces,
            }
            document = {
                "payload": payload,
                "public_key": public,
                "signature": base64.b64encode(
                    key.sign(canonical(payload).encode())
                ).decode(),
                "algorithm": "Ed25519",
            }
            content = (canonical(document) + "\n").encode()
            verify(content, fingerprint)
            return content


def persist(content, fingerprint, key_file, destination):
    current = verify(content, fingerprint)
    destination = Path(destination).absolute()
    if destination.resolve() != destination or Path(key_file).resolve().is_relative_to(
        destination
    ):
        raise ValueError(
            "Keep checkpoint archive keys outside nonredirected receiver storage"
        )
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    cipher = Fernet(Path(key_file).read_bytes().strip())
    with InstallationLock(destination):
        prior, newest, count, total = {}, None, 0, 0
        for path in destination.iterdir():
            if path.name == ".installation.lock":
                continue
            if (
                path.is_symlink()
                or not path.is_file()
                or not re.fullmatch(
                    r"checkpoint-history-[a-f0-9]{64}\.fernet", path.name
                )
            ):
                raise ValueError(
                    "Checkpoint receiver contains incomplete or unknown history"
                )
            count += 1
            total += path.stat().st_size
            if (
                count > 2000
                or total > 256 * 1024 * 1024
                or path.stat().st_size > 2 * MAX_BYTES
            ):
                raise ValueError(
                    "Checkpoint receiver complete history exceeds its bound"
                )
            raw = cipher.decrypt(path.read_bytes())
            if hashlib.sha256(raw).hexdigest() != path.stem.rsplit("-", 1)[1]:
                raise ValueError("Checkpoint receiver archive identity changed")
            retained = verify(raw, fingerprint, max_age_hours=100 * 365 * 24)
            stamp = datetime.fromisoformat(retained["created_at"])
            newest = max(newest, stamp) if newest else stamp
            for name, digest in retained["files"].items():
                if name in prior and prior[name] != digest:
                    raise ValueError("Retained checkpoint histories conflict")
                prior[name] = digest
        if newest and datetime.fromisoformat(current["created_at"]) < newest:
            raise ValueError("Checkpoint history predates retained receiver state")
        if any(current["files"].get(name) != digest for name, digest in prior.items()):
            raise ValueError("Checkpoint history omits or rewrites retained anchors")
        digest = hashlib.sha256(content).hexdigest()
        target = destination / ("checkpoint-history-" + digest + ".fernet")
        if not target.exists():
            if count >= 2000 or total + len(content) * 2 > 256 * 1024 * 1024:
                raise ValueError("Checkpoint receiver has no publication capacity")
            encrypted = cipher.encrypt(content)
            verify(cipher.decrypt(encrypted), fingerprint)
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
            "fingerprint": fingerprint,
            "archive": target.name,
            "encrypted_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            "encrypted_bytes": target.stat().st_size,
            "source_created_at": current["created_at"],
            "anchors": len(current["files"]),
            "heads": current["heads"],
            "scope": "Encrypted signed anchor history retained. No audit narratives/keys included. Does not independently prove source truth, host integrity, current DB linkage or off-machine custody.",
        }


def recover(archive, fingerprint, key_file, destination, trusted_bundle_sha256):
    archive, destination = Path(archive), Path(destination).absolute()
    if (
        archive.is_symlink()
        or not archive.is_file()
        or archive.stat().st_size > 2 * MAX_BYTES
    ):
        raise ValueError("Checkpoint recovery archive unavailable or oversized")
    if destination.resolve() != destination or destination.exists():
        raise ValueError("Checkpoint recovery requires a new nonredirected directory")
    content = Fernet(Path(key_file).read_bytes().strip()).decrypt(archive.read_bytes())
    if hashlib.sha256(content).hexdigest() != trusted_bundle_sha256:
        raise ValueError(
            "Checkpoint recovery bundle differs from the independently retained current digest"
        )
    inventory = verify(content, fingerprint, max_age_hours=100 * 365 * 24)
    payload = json.loads(content)["payload"]
    destination.mkdir(parents=True, mode=0o700)
    with InstallationLock(destination):
        pending = destination / "restoration.pending"
        descriptor = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(
                b"Incomplete checkpoint history recovery. Do not start service.\n"
            )
            stream.flush()
            os.fsync(stream.fileno())
        for workspace_id, anchors in payload["workspaces"].items():
            directory = destination / workspace_id
            directory.mkdir(mode=0o700)
            for anchor in anchors:
                value = anchor["payload"]
                name = f"checkpoint-{value['sequence']:020d}-{value['head_hash'][:16]}.json"
                descriptor = os.open(
                    directory / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
                )
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write((canonical(anchor) + "\n").encode())
                    stream.flush()
                    os.fsync(stream.fileno())
            sync_directory(directory)
        sync_directory(destination)
        pending.unlink()
        sync_directory(destination)
    return {
        "restored_anchors": len(inventory["files"]),
        "fingerprint": fingerprint,
        "bundle_sha256": trusted_bundle_sha256,
        "source_modified": False,
        "scope": "Signed external anchors reconstructed; matching database/audit chain and original signing key still require verification.",
    }


def staging_root(root):
    root = Path(root).absolute()
    if root.resolve() != root:
        raise ValueError("Checkpoint staging cannot be redirected")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name != "nt" and root.stat().st_mode & 0o077:
        raise ValueError("Checkpoint staging permissions must be 0700")
    return root


def stage(settings, root=STAGING_ROOT):
    from deploy.deletion_state_backup import staged_files

    root = staging_root(root)
    if root.is_relative_to(settings.database_path.parent.resolve()):
        raise ValueError("Checkpoint staging must be outside database storage")
    with InstallationLock(root):
        files, total = staged_files(root)
        content = export_bundle(settings)
        if len(files) >= 2000 or total + len(content) > 256 * 1024 * 1024:
            raise ValueError("Checkpoint staging has no publication capacity")
        digest = hashlib.sha256(content).hexdigest()
        target = root / (
            "state-"
            + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            + "-"
            + digest
            + ".json"
        )
        if target.exists():
            raise ValueError("Checkpoint staging identity already exists")
        pending = target.with_suffix(".pending")
        descriptor = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(pending, target)
        sync_directory(root)
        return {"staged": True, "bundle_sha256": digest, "file": target.name}


def latest(settings, root=STAGING_ROOT):
    from deploy.deletion_state_backup import staged_files

    if not Path(root).is_dir():
        raise ValueError("Checkpoint staging is unavailable")
    root = staging_root(root)
    with InstallationLock(root):
        files, total = staged_files(root)
        if not files or total > 256 * 1024 * 1024:
            raise ValueError("Checkpoint staging inventory missing or oversized")
        path = max(files)
        if path.stat().st_size > MAX_BYTES:
            raise ValueError("Staged checkpoint bundle oversized")
        with path.open("rb") as stream:
            content = stream.read(MAX_BYTES + 1)
        if hashlib.sha256(content).hexdigest() != path.stem.rsplit("-", 1)[1]:
            raise ValueError("Staged checkpoint checksum changed")
        manager = Checkpoints(None, settings)
        _, fingerprint = manager.identity(manager.signing_key(manager.root()))
        verify(content, fingerprint)
        return content


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("export")
    commands.add_parser("stage")
    commands.add_parser("latest")
    receive = commands.add_parser("receive")
    receive.add_argument("--fingerprint", required=True)
    receive.add_argument("--key-file", type=Path, required=True)
    receive.add_argument("--destination", type=Path, required=True)
    restore = commands.add_parser("recover")
    restore.add_argument("--archive", type=Path, required=True)
    restore.add_argument("--fingerprint", required=True)
    restore.add_argument("--key-file", type=Path, required=True)
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
            content = sys.stdin.buffer.read(MAX_BYTES + 1)
            print(
                json.dumps(
                    persist(content, args.fingerprint, args.key_file, args.destination)
                )
            )
        else:
            print(
                json.dumps(
                    recover(
                        args.archive,
                        args.fingerprint,
                        args.key_file,
                        args.destination,
                        args.bundle_sha256,
                    )
                )
            )
        return 0
    except Exception:
        print(
            "Checkpoint history backup failed; inspect trusted operator configuration and retained history.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
