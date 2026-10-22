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
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath

from cryptography.fernet import Fernet

MAX_BYTES = 128 * 1024 * 1024


def verify_archive(payload, max_age_hours=30):
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
            with closing(sqlite3.connect(":memory:")) as connection:
                try:
                    if not data.startswith(b"SQLite format 3\x00"):
                        raise ValueError("Snapshot member is not a SQLite database.")
                    # SQLite's documented WAL deserialize workaround applies only
                    # to this private verification copy. Archive bytes stay intact.
                    # https://www.sqlite.org/c3ref/deserialize.html
                    memory_copy = data[:18] + b"\x01\x01" + data[20:]
                    connection.deserialize(memory_copy)
                    connection.execute("PRAGMA trusted_schema=OFF")
                    connection.execute("PRAGMA query_only=ON")
                    if connection.execute("PRAGMA integrity_check").fetchall() != [
                        ("ok",)
                    ]:
                        raise ValueError("Snapshot database integrity check failed.")
                    if item["path"] == "identity.db":
                        ids = {
                            row[0]
                            for row in connection.execute(
                                "SELECT id FROM organizations"
                            )
                        }
                        if ids != set(manifest["organization_paths"]):
                            raise ValueError(
                                "Snapshot workspace mappings are inconsistent."
                            )
                except sqlite3.Error as exc:
                    raise ValueError(
                        "Snapshot database could not be verified."
                    ) from exc
    return manifest


def collect(host, identity, known_hosts):
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
        "/opt/policylens/deploy/export_backup.py",
    ]
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


def persist(payload, key_file, destination, max_age_hours=30):
    manifest = verify_archive(payload, max_age_hours)
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    cipher = Fernet(key_file.read_bytes().strip())
    encrypted = cipher.encrypt(payload)
    # Authenticate and verify the encrypted result before publishing the backup.
    verify_archive(cipher.decrypt(encrypted), max_age_hours)
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
        "plaintext_sha256": digest,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    parser.add_argument("--identity", type=Path, required=True)
    parser.add_argument("--known-hosts", type=Path, required=True)
    parser.add_argument("--key-file", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument(
        "--max-age-hours", type=int, default=30, choices=range(1, 169), metavar="1..168"
    )
    args = parser.parse_args()
    args.destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        if args.key_file.resolve().is_relative_to(args.destination.resolve()):
            raise ValueError("Keep the decryption key outside the backup destination.")
        result = persist(
            collect(args.host, args.identity, args.known_hosts),
            args.key_file,
            args.destination,
            args.max_age_hours,
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
