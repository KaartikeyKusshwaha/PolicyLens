"""Read-only operator health checks; nonzero exit enables external monitoring."""

import argparse
import hashlib
import ipaddress
import json
import re
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

import httpx

MAX_RECEIPT_BYTES = 65536
MAX_ARCHIVE_BYTES = 192 * 1024 * 1024
SCHEMA = "policylens.operational-watchdog.v1"


def origin_url(origin):
    value = urlsplit(origin)
    try:
        loopback = (
            value.hostname == "localhost"
            or ipaddress.ip_address(value.hostname).is_loopback
        )
    except ValueError:
        loopback = False
    if (
        (value.scheme != "https" and not (value.scheme == "http" and loopback))
        or not value.hostname
        or value.username
        or value.password
        or value.path not in ("", "/")
        or value.query
        or value.fragment
    ):
        raise ValueError(
            "Use a credential-free HTTPS origin, or HTTP loopback origin, without paths or queries"
        )
    _ = value.port
    return origin.rstrip("/") + "/api/ready"


def receipt(path):
    if (
        path.is_symlink()
        or not path.is_file()
        or path.stat().st_size > MAX_RECEIPT_BYTES
    ):
        raise ValueError("Backup receipt unavailable")
    with path.open("rb") as stream:
        content = stream.read(MAX_RECEIPT_BYTES + 1)
    if len(content) > MAX_RECEIPT_BYTES:
        raise ValueError("Backup receipt oversized")
    result = json.loads(content)
    if not isinstance(result, dict):
        raise ValueError("Invalid backup receipt")
    return result


def fresh(value, at, max_age_hours):
    stamp = datetime.fromisoformat(value)
    if (
        stamp.tzinfo is None
        or stamp > at + timedelta(minutes=5)
        or stamp < at - timedelta(hours=max_age_hours)
    ):
        raise ValueError("Backup time is stale, naive or future dated")
    return stamp


def backup_check(directory, at, max_age_hours):
    root = Path(directory).absolute()
    if root.resolve() != root or not root.is_dir():
        return {
            "name": "offsite_backup",
            "healthy": False,
            "code": "backup_directory_unavailable",
        }
    try:
        attempt, saved = (
            receipt(root / "last-attempt.json"),
            receipt(root / "last-success.json"),
        )
        if attempt.get("success") is not True:
            return {
                "name": "offsite_backup",
                "healthy": False,
                "code": "latest_backup_attempt_failed",
            }
        completed = fresh(saved["completed_at"], at, max_age_hours)
        attempted = fresh(attempt["completed_at"], at, max_age_hours)
        fresh(saved["snapshot_created_at"], at, max_age_hours)
        if (
            saved.get("success") is not True
            or attempted != completed
            or any(
                attempt.get(name) != saved.get(name)
                for name in (
                    "archive",
                    "encrypted_sha256",
                    "encrypted_bytes",
                    "snapshot_created_at",
                )
            )
        ):
            raise ValueError("Latest successful backup receipts disagree")
        name = saved["archive"]
        if not isinstance(name, str) or not re.fullmatch(
            r"policylens-\d{8}T\d{6}Z-[a-f0-9]{16}\.tar\.gz\.fernet", name
        ):
            raise ValueError("Unsafe backup name")
        target = root / name
        size = saved["encrypted_bytes"]
        expected = saved["encrypted_sha256"]
        if (
            type(size) is not int
            or not 1 <= size <= MAX_ARCHIVE_BYTES
            or not isinstance(expected, str)
            or not re.fullmatch(r"[a-f0-9]{64}", expected)
        ):
            raise ValueError("Backup integrity metadata missing")
        if target.is_symlink() or not target.is_file() or target.stat().st_size != size:
            raise ValueError("Backup artifact missing or size changed")
        digest, actual_size = hashlib.sha256(), 0
        with target.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                actual_size += len(block)
                if actual_size > size:
                    raise ValueError("Backup artifact grew during verification")
                digest.update(block)
        if actual_size != size or digest.hexdigest() != expected:
            raise ValueError("Backup artifact checksum changed")
        return {
            "name": "offsite_backup",
            "healthy": True,
            "code": "fresh_receipt_and_matching_archive",
        }
    except (OSError, ValueError, TypeError, KeyError, OverflowError):
        return {
            "name": "offsite_backup",
            "healthy": False,
            "code": "backup_receipt_or_archive_invalid",
        }


def history_check(receipt_directory, directory, kind, at, max_age_hours):
    name = kind + "_backup"
    try:
        root = Path(directory).absolute()
        if root.resolve() != root or not root.is_dir():
            raise ValueError("History directory unavailable")
        receipts = Path(receipt_directory).absolute()
        if receipts.resolve() != receipts:
            raise ValueError("Receipt directory redirected")
        attempt, saved = (
            receipt(receipts / "last-attempt.json"),
            receipt(receipts / "last-success.json"),
        )
        if attempt.get("success") is not True or saved.get("success") is not True:
            raise ValueError("Combined attempt failed")
        if attempt["completed_at"] != saved["completed_at"] or attempt.get(
            kind
        ) != saved.get(kind):
            raise ValueError("Combined history receipts disagree")
        fresh(saved["completed_at"], at, max_age_hours)
        metadata = saved[kind]
        if not isinstance(metadata, dict) or metadata.get("success") is not True:
            raise ValueError("History verification receipt missing")
        fresh(metadata["source_created_at"], at, max_age_hours)
        prefix = "deletion-state" if kind == "deletion_state" else "checkpoint-history"
        archive = metadata["archive"]
        digest, size, identity = (
            metadata["encrypted_sha256"],
            metadata["encrypted_bytes"],
            metadata["bundle_sha256"],
        )
        if (
            not isinstance(archive, str)
            or not re.fullmatch(prefix + r"-[a-f0-9]{64}\.fernet", archive)
            or archive != prefix + "-" + identity + ".fernet"
        ):
            raise ValueError("Unsafe history identity")
        if (
            type(size) is not int
            or not 1 <= size <= MAX_ARCHIVE_BYTES
            or not isinstance(digest, str)
            or not re.fullmatch(r"[a-f0-9]{64}", digest)
        ):
            raise ValueError("History integrity metadata invalid")
        target = root / archive
        if target.is_symlink() or not target.is_file() or target.stat().st_size != size:
            raise ValueError("History artifact missing or size changed")
        actual, total = hashlib.sha256(), 0
        with target.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                total += len(block)
                if total > size:
                    raise ValueError("History artifact grew")
                actual.update(block)
        if total != size or actual.hexdigest() != digest:
            raise ValueError("History ciphertext checksum changed")
        return {
            "name": name,
            "healthy": True,
            "code": "fresh_receipt_and_matching_history_archive",
        }
    except (OSError, ValueError, TypeError, KeyError, OverflowError):
        return {
            "name": name,
            "healthy": False,
            "code": "history_receipt_or_archive_invalid",
        }


def readiness_check(client, url):
    try:
        with client.stream("GET", url) as response:
            if response.status_code != 200:
                return {
                    "name": "readiness",
                    "healthy": False,
                    "code": "readiness_http_failure",
                }
            content = bytearray()
            for block in response.iter_bytes(chunk_size=1024):
                content.extend(block)
                if len(content) > 4096:
                    raise ValueError("Readiness response oversized")
            result = json.loads(content)
        if not isinstance(result, dict) or result.get("status") != "ready":
            raise ValueError("Readiness not established")
        return {"name": "readiness", "healthy": True, "code": "ready"}
    except (httpx.HTTPError, ValueError, TypeError):
        return {
            "name": "readiness",
            "healthy": False,
            "code": "readiness_unavailable_or_invalid",
        }


def check(
    origin,
    offsite_directory,
    disk_path,
    *,
    min_free_bytes=1024 * 1024 * 1024,
    max_age_hours=30,
    transport=None,
    at=None,
    deletion_state_directory=None,
    checkpoint_directory=None,
):
    url = origin_url(origin)
    if (
        type(min_free_bytes) is not int
        or min_free_bytes <= 0
        or type(max_age_hours) is not int
        or not 1 <= max_age_hours <= 168
    ):
        raise ValueError("Use a positive disk floor and backup age of 1–168 hours")
    at = at or datetime.now(timezone.utc)
    with httpx.Client(
        timeout=5, follow_redirects=False, trust_env=False, transport=transport
    ) as client:
        checks = [readiness_check(client, url)]
    checks.append(backup_check(offsite_directory, at, max_age_hours))
    for kind, directory in (
        ("deletion_state", deletion_state_directory),
        ("checkpoint_history", checkpoint_directory),
    ):
        if directory is not None:
            checks.append(
                history_check(offsite_directory, directory, kind, at, max_age_hours)
            )
    try:
        free = shutil.disk_usage(disk_path).free
        checks.append(
            {
                "name": "disk_space",
                "healthy": free >= min_free_bytes,
                "code": "disk_floor_met"
                if free >= min_free_bytes
                else "disk_below_floor",
                "free_bytes": free,
                "minimum_bytes": min_free_bytes,
            }
        )
    except OSError:
        checks.append(
            {"name": "disk_space", "healthy": False, "code": "disk_path_unavailable"}
        )
    return {
        "schema": SCHEMA,
        "checked_at": at.isoformat(),
        "healthy": all(item["healthy"] for item in checks),
        "checks": checks,
        "scope": "Readiness HTTP, local offsite-receiver receipts/archive SHA-256 and disk floor only. Does not decrypt/revalidate backup databases, prove independent off-machine custody, monitor deletion-guard freshness or certify recovery. No notification was sent.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin", required=True)
    parser.add_argument("--offsite-directory", type=Path, required=True)
    parser.add_argument("--disk-path", type=Path, required=True)
    parser.add_argument("--deletion-state-directory", type=Path)
    parser.add_argument("--checkpoint-directory", type=Path)
    parser.add_argument("--min-free-mib", type=int, default=1024)
    parser.add_argument("--max-backup-age-hours", type=int, default=30)
    args = parser.parse_args(argv)
    try:
        result = check(
            args.origin,
            args.offsite_directory,
            args.disk_path,
            min_free_bytes=args.min_free_mib * 1024 * 1024,
            max_age_hours=args.max_backup_age_hours,
            deletion_state_directory=args.deletion_state_directory,
            checkpoint_directory=args.checkpoint_directory,
        )
    except (ValueError, TypeError):
        result = {
            "schema": SCHEMA,
            "healthy": False,
            "checks": [
                {
                    "name": "configuration",
                    "healthy": False,
                    "code": "watchdog_configuration_invalid",
                }
            ],
        }
    print(json.dumps(result))
    return 0 if result["healthy"] else 1


if __name__ == "__main__":
    sys.exit(main())
