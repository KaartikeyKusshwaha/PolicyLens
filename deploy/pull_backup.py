"""Pull, verify and encrypt a server snapshot without writing plaintext to disk."""

import argparse
import hashlib
import io
import json
import os
import re
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
from contextlib import closing, contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from types import SimpleNamespace

from cryptography.fernet import Fernet

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from database import DB_ERRORS, connect_database, descriptor  # noqa: E402
from snapshot_mapping import verify_workspace_mapping  # noqa: E402

MAX_BYTES = 128 * 1024 * 1024


@contextmanager
def verification_database(data, settings):
    """Never materialize a decrypted database on disk."""
    if settings is None:
        if not data.startswith(b"SQLite format 3\x00"):
            raise ValueError("Snapshot member is not a SQLite database.")
        with closing(sqlite3.connect(":memory:")) as connection:
            # Documented WAL deserialize workaround affects this memory copy only.
            # https://www.sqlite.org/c3ref/deserialize.html
            connection.deserialize(data[:18] + b"\x01\x01" + data[20:])
            yield connection
    else:
        if data.startswith(b"SQLite format 3\x00"):
            raise ValueError("Encrypted snapshot contains a plaintext database.")
        # This native binding has no deserialize API. Only original ciphertext is
        # staged in the private directory; SQLCipher decrypts pages in memory.
        with tempfile.TemporaryDirectory(
            prefix="policylens-cipher-verify-"
        ) as directory:
            path = Path(directory) / "encrypted.db"
            handle = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(handle, "wb") as file:
                file.write(data)
            with closing(connect_database(path, settings, readonly=True)) as connection:
                yield connection


def verify_archive(payload, max_age_hours=30, *, database_key_file=None):
    if len(payload) > MAX_BYTES:
        raise ValueError("Archive is too large.")
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
        members = archive.getmembers()
        if len(members) > 10001 or sum(m.size for m in members) > MAX_BYTES:
            raise ValueError("Expanded archive exceeds its bounds.")
        names = set()
        for member in members:
            path = PurePosixPath(member.name)
            if (
                not member.isfile()
                or path.is_absolute()
                or ".." in path.parts
                or "\\" in member.name
                or ":" in member.name
                or member.name in names
            ):
                raise ValueError("Archive contains an unsafe or duplicate member.")
            names.add(member.name)
        if "manifest.json" not in names:
            raise ValueError("Archive has no manifest.")
        manifest = json.load(archive.extractfile("manifest.json"))
        if manifest.get("format") != 1 or not manifest.get("files"):
            raise ValueError("Unsupported snapshot manifest.")
        settings = None
        encryption = manifest.get("database_encryption", {"scheme": "none"})
        if database_key_file is not None:
            settings = SimpleNamespace(
                database_encryption="sqlcipher4",
                security_key_path=Path(database_key_file),
                deployment_mode="public",
            )
        if encryption != descriptor(settings):
            raise ValueError(
                "Snapshot encryption mode or original installation key does not match."
            )
        stamp = datetime.fromisoformat(manifest["created_at"])
        current = datetime.now(timezone.utc)
        if (
            stamp.tzinfo is None
            or stamp > current + timedelta(minutes=5)
            or stamp < current - timedelta(hours=max_age_hours)
        ):
            raise ValueError("Snapshot timestamp is stale, naive or future-dated.")
        expected = {item["path"] for item in manifest["files"]}
        if (
            len(expected) != len(manifest["files"])
            or names != expected | {"manifest.json"}
            or "identity.db" not in expected
            or not set(manifest["organization_paths"].values()) <= expected
        ):
            raise ValueError("Snapshot manifest and archive members do not agree.")
        for item in manifest["files"]:
            data = archive.extractfile(item["path"]).read()
            if (
                len(data) != item["bytes"]
                or hashlib.sha256(data).hexdigest() != item["sha256"]
            ):
                raise ValueError("Snapshot checksum or size mismatch.")
            try:
                with verification_database(data, settings) as connection:
                    connection.execute("PRAGMA trusted_schema=OFF")
                    connection.execute("PRAGMA query_only=ON")
                    if connection.execute("PRAGMA integrity_check").fetchall() != [
                        ("ok",)
                    ]:
                        raise ValueError("Snapshot database integrity check failed.")
                    if (
                        settings is not None
                        and connection.execute(
                            "PRAGMA cipher_integrity_check"
                        ).fetchall()
                    ):
                        raise ValueError(
                            "Snapshot SQLCipher page authentication failed."
                        )
                    if item["path"] == "identity.db":
                        verify_workspace_mapping(
                            manifest,
                            connection.execute(
                                "SELECT id,db_path FROM organizations"
                            ).fetchall(),
                        )
            except DB_ERRORS as exc:
                raise ValueError("Snapshot database could not be verified.") from exc
    return manifest


def collect(host, identity, known_hosts, *, deletion_state=False):
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*@[A-Za-z0-9][A-Za-z0-9.-]*", host):
        raise ValueError("Use a user@hostname SSH target.")
    for path in (identity, known_hosts):
        if not Path(path).is_file():
            raise ValueError(
                "The SSH identity and verified known-hosts file must exist."
            )
    command = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=yes",
        "-o",
        "ConnectTimeout=15",
        "-o",
        "ServerAliveInterval=15",
        "-o",
        "ServerAliveCountMax=3",
        "-o",
        "UserKnownHostsFile=" + str(Path(known_hosts).resolve()),
        "-i",
        str(Path(identity).resolve()),
        host,
        "sudo",
        "-n",
        "/opt/policylens/.venv/bin/python",
        "/opt/policylens/deploy/deletion_state_backup.py"
        if deletion_state
        else "/opt/policylens/deploy/export_backup.py",
    ]
    if deletion_state:
        command.append("latest")
    result = subprocess.run(command, capture_output=True, timeout=180, check=False)
    if result.returncode:
        raise RuntimeError("Verified SSH snapshot export failed.")
    return result.stdout


def write_json(path, value):
    temporary = path.with_suffix(".pending")
    with temporary.open("w", encoding="utf-8") as file:
        json.dump(value, file, indent=2)
    temporary.chmod(0o600)
    os.replace(temporary, path)


def persist(
    payload, key_file, destination, max_age_hours=30, *, database_key_file=None
):
    for key_path in (key_file, database_key_file):
        if key_path is not None and Path(key_path).resolve().is_relative_to(
            destination.resolve()
        ):
            raise ValueError("Keep all decryption keys outside the backup destination.")
    manifest = verify_archive(
        payload, max_age_hours, database_key_file=database_key_file
    )
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    cipher = Fernet(key_file.read_bytes().strip())
    encrypted = cipher.encrypt(payload)
    # Authenticate and verify the encrypted result before publishing the backup.
    verify_archive(
        cipher.decrypt(encrypted), max_age_hours, database_key_file=database_key_file
    )
    stamp = datetime.fromisoformat(manifest["created_at"]).strftime("%Y%m%dT%H%M%SZ")
    digest = hashlib.sha256(payload).hexdigest()
    target = destination / (
        "policylens-" + stamp + "-" + digest[:16] + ".tar.gz.fernet"
    )
    if target.exists():
        if hashlib.sha256(cipher.decrypt(target.read_bytes())).hexdigest() != digest:
            raise ValueError("An existing backup with this identity does not match.")
    else:
        temporary = target.with_suffix(".pending")
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as file:
            file.write(encrypted)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, target)
    return {
        "success": True,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "snapshot_created_at": manifest["created_at"],
        "databases": len(manifest["files"]),
        "archive": target.name,
        "encrypted_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "encrypted_bytes": target.stat().st_size,
        "plaintext_sha256": digest,
        "database_encryption": manifest.get("database_encryption", {"scheme": "none"}),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    parser.add_argument("--identity", type=Path, required=True)
    parser.add_argument("--known-hosts", type=Path, required=True)
    parser.add_argument("--key-file", type=Path, required=True)
    parser.add_argument(
        "--database-key-file",
        type=Path,
        help="Separate protected recovery copy of the original raw installation key; requires SQLCipher snapshots.",
    )
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument(
        "--deletion-state-destination",
        type=Path,
        help="Also require verified encrypted retention of the newest staged complete deletion history; requires --database-key-file.",
    )
    parser.add_argument(
        "--max-age-hours", type=int, default=30, choices=range(1, 169), metavar="1..168"
    )
    args = parser.parse_args()
    args.destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        if (
            args.deletion_state_destination is not None
            and args.database_key_file is None
        ):
            raise ValueError(
                "Deletion history transfer requires the original installation recovery key"
            )
        if args.key_file.resolve().is_relative_to(args.destination.resolve()):
            raise ValueError("Keep the decryption key outside the backup destination.")
        result = persist(
            collect(args.host, args.identity, args.known_hosts),
            args.key_file,
            args.destination,
            args.max_age_hours,
            database_key_file=args.database_key_file,
        )
        if args.deletion_state_destination is not None:
            from deploy.deletion_state_backup import persist as persist_deletion_state

            result["deletion_state"] = persist_deletion_state(
                collect(
                    args.host, args.identity, args.known_hosts, deletion_state=True
                ),
                args.database_key_file,
                args.key_file,
                args.deletion_state_destination,
                max_age_hours=args.max_age_hours,
            )
    except Exception:
        result = {
            "success": False,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "error": "Backup transfer or verification failed. Check SSH access, key availability and snapshot age/integrity.",
        }
        write_json(args.destination / "last-attempt.json", result)
        print(json.dumps(result), file=sys.stderr)
        return 1
    write_json(args.destination / "last-success.json", result)
    write_json(args.destination / "last-attempt.json", result)
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
