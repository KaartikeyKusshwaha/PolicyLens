"""Offline whole-installation snapshots and non-destructive restore drills."""

import hashlib
import json
import shutil
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from runtime import InstallationLock


def checksum(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def safe_child(root, relative):
    relative = Path(relative)
    target = (root / relative).resolve()
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or not target.is_relative_to(root.resolve())
    ):
        raise ValueError("Backup paths must stay inside the selected directory.")
    return target


def readonly(path):
    return sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)


def integrity(path):
    connection = readonly(path)
    try:
        rows = connection.execute("PRAGMA integrity_check").fetchall()
        if rows != [("ok",)]:
            raise ValueError("SQLite integrity verification failed.")
    finally:
        connection.close()


def create_snapshot(settings, destination):
    root = settings.database_path.parent.resolve()
    destination = Path(destination).resolve()
    with InstallationLock(root):
        identity = root / "identity.db"
        with closing(readonly(identity)) as db:
            if not db.execute("SELECT 1 FROM users LIMIT 1").fetchone():
                raise ValueError(
                    "Complete owner setup before creating a full snapshot."
                )
            organizations = db.execute(
                "SELECT id,db_path FROM organizations"
            ).fetchall()
        paths = {"identity.db": identity}
        mappings = {}
        for org_id, path in organizations:
            source = Path(path).resolve()
            if not source.is_relative_to(root) or not source.is_file():
                raise ValueError(
                    "A workspace database is missing or outside the configured data directory."
                )
            relative = source.relative_to(root).as_posix()
            paths[relative] = source
            mappings[org_id] = relative
        destination.mkdir(parents=True, exist_ok=False, mode=0o700)
        manifest = {
            "format": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "organization_paths": mappings,
            "files": [],
            "scope": "Identity and workspace databases. Environment/API keys are excluded. Stop the installation before snapshotting. Local file permissions are not encryption.",
        }
        for relative, source in paths.items():
            target = safe_child(destination, relative)
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            source_db = readonly(source)
            target_db = sqlite3.connect(target)
            try:
                source_db.backup(target_db)
            finally:
                source_db.close()
                target_db.close()
            target.chmod(0o600)
            integrity(target)
            manifest["files"].append(
                {
                    "path": relative,
                    "sha256": checksum(target),
                    "bytes": target.stat().st_size,
                }
            )
        manifest_file = destination / "manifest.json"
        manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        manifest_file.chmod(0o600)
        verify_snapshot(destination)
        return manifest


def verify_snapshot(directory):
    directory = Path(directory).resolve()
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("format") != 1 or not 1 <= len(manifest.get("files", [])) <= 10000:
        raise ValueError("Unsupported or empty backup manifest.")
    names = set()
    for item in manifest["files"]:
        path = safe_child(directory, item["path"])
        if (
            item["path"] in names
            or not path.is_file()
            or checksum(path) != item["sha256"]
        ):
            raise ValueError(
                "Backup file is missing, duplicated, or its checksum changed."
            )
        names.add(item["path"])
        integrity(path)
    if "identity.db" not in names or not set(
        manifest["organization_paths"].values()
    ).issubset(names):
        raise ValueError("Backup is missing identity or workspace databases.")
    with closing(readonly(directory / "identity.db")) as db:
        org_ids = {row[0] for row in db.execute("SELECT id FROM organizations")}
    if org_ids != set(manifest["organization_paths"]):
        raise ValueError("Workspace mappings do not match the identity database.")
    return manifest


def restore_snapshot(directory, destination):
    manifest = verify_snapshot(directory)
    directory = Path(directory).resolve()
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError(
            "Restore requires a new destination. Existing installations are never overwritten."
        )
    destination.mkdir(parents=True, mode=0o700)
    with InstallationLock(destination):
        for item in manifest["files"]:
            target = safe_child(destination, item["path"])
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            shutil.copyfile(safe_child(directory, item["path"]), target)
            target.chmod(0o600)
        with sqlite3.connect(destination / "identity.db") as db:
            for org_id, relative in manifest["organization_paths"].items():
                db.execute(
                    "UPDATE organizations SET db_path=? WHERE id=?",
                    (str(safe_child(destination, relative)), org_id),
                )
            db.execute("DELETE FROM sessions")
            if db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='password_resets'"
            ).fetchone():
                db.execute("DELETE FROM password_resets")
        for relative in set(manifest["organization_paths"].values()):
            path = safe_child(destination, relative)
            with sqlite3.connect(path) as db:
                db.execute("UPDATE jobs SET state='interrupted' WHERE state='running'")
            integrity(path)
        integrity(destination / "identity.db")
    return {
        "restored_databases": len(manifest["files"]),
        "sessions_revoked": True,
        "source_modified": False,
    }
