"""Operator recovery commands. Uses the same venv and backend/.env as the app."""

import argparse
import json
import os
import secrets
import sys
from pathlib import Path
from urllib.parse import urlencode, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

from config import Settings  # noqa: E402
from recovery import (
    create_snapshot,
    migrate_encryption,
    restore_snapshot,
    verify_snapshot,
)  # noqa: E402
from auth import Hub  # noqa: E402
from checkpoints import Checkpoints, verify_bundle  # noqa: E402
from database import DB_ERRORS  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    security_key = commands.add_parser(
        "security-key",
        help="Create a private 32-byte installation encryption key; never overwrite.",
    )
    security_key.add_argument("--output", type=Path, required=True)
    checkpoint = commands.add_parser(
        "checkpoint",
        help="Retain and export a signed full audit bundle for one workspace.",
    )
    checkpoint.add_argument("--workspace", required=True)
    checkpoint.add_argument("--output", type=Path, required=True)
    verify_checkpoint = commands.add_parser(
        "verify-checkpoint",
        help="Independently verify a signed audit bundle against a trusted public-key fingerprint.",
    )
    verify_checkpoint.add_argument("bundle", type=Path)
    verify_checkpoint.add_argument("--fingerprint", required=True)
    backup = commands.add_parser(
        "backup", help="Snapshot all databases while the app is stopped."
    )
    backup.add_argument("--output", type=Path, required=True)
    migrate = commands.add_parser(
        "migrate-encryption",
        help="Export a stopped plaintext installation to a NEW SQLCipher snapshot; never overwrite source databases.",
    )
    migrate.add_argument("--output", type=Path, required=True)
    verify = commands.add_parser(
        "verify", help="Verify checksums and SQLite integrity."
    )
    verify.add_argument("backup", type=Path)
    restore = commands.add_parser(
        "restore",
        help="Restore to a new directory, rebase workspace paths and revoke sessions.",
    )
    restore.add_argument("backup", type=Path)
    restore.add_argument("--destination", type=Path, required=True)
    reset = commands.add_parser(
        "password-reset", help="Write a private, one-use 15-minute reset link."
    )
    reset.add_argument("--email", required=True)
    reset.add_argument("--origin", required=True)
    reset.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "security-key":
        descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as file:
            file.write(secrets.token_bytes(32))
        print(
            json.dumps(
                {"created": True, "bytes": 32, "key_file": str(args.output.resolve())}
            )
        )
    elif args.command == "checkpoint":
        with args.output.open("x", encoding="utf-8") as file:
            args.output.chmod(0o600)
            settings = Settings()
            result = Checkpoints(Hub(settings), settings).capture(
                args.workspace, include_events=True
            )
            json.dump(result, file, ensure_ascii=False)
        print(
            json.dumps(
                {
                    "retained": True,
                    "bundle_file": str(args.output.resolve()),
                    "sequence": result["checkpoint"]["payload"]["sequence"],
                }
            )
        )
    elif args.command == "verify-checkpoint":
        if args.bundle.stat().st_size > 16_000_000:
            raise ValueError("Audit bundle exceeds the verification input bound.")
        bundle = json.loads(args.bundle.read_text(encoding="utf-8"))
        print(json.dumps({"verified": True, **verify_bundle(bundle, args.fingerprint)}))
    elif args.command == "backup":
        result = create_snapshot(Settings(), args.output)
        print(
            json.dumps(
                {
                    "verified": True,
                    "databases": len(result["files"]),
                    "path": str(args.output.resolve()),
                }
            )
        )
    elif args.command == "migrate-encryption":
        result = migrate_encryption(Settings(), args.output)
        print(
            json.dumps(
                {
                    "verified": True,
                    "databases": len(result["files"]),
                    "path": str(args.output.resolve()),
                    "database_encryption": result["database_encryption"],
                    "source_modified": False,
                    "next_step": "Restore this encrypted snapshot into a new directory using sqlcipher4 and the original installation key before switching the service.",
                }
            )
        )
    elif args.command == "verify":
        result = verify_snapshot(args.backup, Settings())
        print(json.dumps({"verified": True, "databases": len(result["files"])}))
    elif args.command == "restore":
        print(json.dumps(restore_snapshot(args.backup, args.destination, Settings())))
    else:
        origin = urlsplit(args.origin)
        settings = Settings()
        hosts = settings.allowed_hosts.split(",")
        if (
            origin.hostname not in [host.strip() for host in hosts]
            or origin.username
            or origin.password
            or origin.query
            or origin.fragment
            or origin.path not in ("", "/")
            or origin.scheme not in ("http", "https")
            or (settings.deployment_mode == "public" and origin.scheme != "https")
        ):
            raise ValueError(
                "Use an allowed application origin with HTTPS in public mode."
            )
        # Refuse to overwrite any existing file, including before issuing a token.
        with args.output.open("x", encoding="utf-8") as file:
            args.output.chmod(0o600)
            reset = Hub(settings).issue_password_reset(args.email)
            fragment = urlencode(
                {"token": reset["token"], "email": args.email.strip().lower()}
            )
            file.write(args.origin.rstrip("/") + "/reset-password#" + fragment + "\n")
        print(
            json.dumps(
                {
                    "reset_link_file": str(args.output.resolve()),
                    "expires_at": reset["expires_at"],
                }
            )
        )


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, OSError, *DB_ERRORS) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
