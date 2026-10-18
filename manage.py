"""Operator recovery commands. Uses the same venv and backend/.env as the app."""

import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

from config import Settings  # noqa: E402
from recovery import create_snapshot, restore_snapshot, verify_snapshot  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    backup = commands.add_parser(
        "backup", help="Snapshot all databases while the app is stopped."
    )
    backup.add_argument("--output", type=Path, required=True)
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
    args = parser.parse_args()
    if args.command == "backup":
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
    elif args.command == "verify":
        result = verify_snapshot(args.backup)
        print(json.dumps({"verified": True, "databases": len(result["files"])}))
    else:
        print(json.dumps(restore_snapshot(args.backup, args.destination)))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, OSError, sqlite3.Error) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
