"""Offline whole-installation snapshots and non-destructive restore drills."""

import hashlib
import json
import shutil
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from runtime import InstallationLock
from database import connect_database, database_key, descriptor, encrypted
from security import SecretBox
from sqlcipher3 import dbapi2 as cipher


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


def readonly(path, settings=None):
    return connect_database(path, settings, readonly=True)


def integrity(path, settings=None):
    connection = readonly(path, settings)
    try:
        rows = connection.execute("PRAGMA integrity_check").fetchall()
        if rows != [("ok",)]:
            raise ValueError("SQLite integrity verification failed.")
        if (
            encrypted(settings)
            and connection.execute("PRAGMA cipher_integrity_check").fetchall()
        ):
            raise ValueError("SQLCipher page authentication verification failed.")
    finally:
        connection.close()


def create_snapshot(settings, destination):
    return _create_snapshot(settings, destination, settings)


def migrate_encryption(settings, destination):
    """Export a stopped plaintext installation into a NEW encrypted snapshot."""
    if encrypted(settings):
        raise ValueError(
            "Encryption migration requires a plaintext source configuration."
        )
    # Preserve existing MFA/signing identity. Never generate a replacement master.
    box = SecretBox(settings)
    box.key()
    target_settings = settings.model_copy(
        update={
            "database_encryption": "sqlcipher4",
            "security_key_path": box.path.resolve(),
        }
    )
    return _create_snapshot(settings, destination, target_settings)


def _create_snapshot(settings, destination, target_settings):
    root = settings.database_path.parent.resolve()
    destination = Path(destination).resolve()
    with InstallationLock(root):
        identity = root / "identity.db"
        with closing(readonly(identity, settings)) as db:
            if not db.execute("SELECT 1 FROM users LIMIT 1").fetchone():
                raise ValueError(
                    "Complete owner setup before creating a full snapshot."
                )
            organizations = db.execute(
                "SELECT id,db_path FROM organizations"
            ).fetchall()
            if (
                not encrypted(settings)
                and encrypted(target_settings)
                and db.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='account_mfa'"
                ).fetchone()
            ):
                for user_id, secret in db.execute(
                    "SELECT user_id,secret FROM account_mfa"
                ):
                    SecretBox(target_settings).decrypt(secret, "mfa:" + user_id)
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
            "database_encryption": descriptor(target_settings),
            "files": [],
            "scope": "Identity and workspace databases. Environment/API keys and the installation encryption key are excluded. Stop the installation before snapshotting. Preserve the original installation key separately. Local file permissions are not encryption.",
        }
        for relative, source in paths.items():
            target = safe_child(destination, relative)
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if not encrypted(settings) and encrypted(target_settings):
                # SQLCipher's backup API cannot copy a plaintext handle into a
                # keyed database. Its supported export rebuilds all schema/data,
                # including FTS, into the separately keyed attached database.
                key_hex = database_key(target_settings).hex()
                with closing(
                    cipher.connect(source.as_uri() + "?mode=ro", uri=True)
                ) as db:
                    db.execute("PRAGMA temp_store=MEMORY")
                    db.execute("PRAGMA cipher_memory_security=ON")
                    db.execute(
                        "ATTACH DATABASE ? AS encrypted KEY \"x'" + key_hex + "'\"",
                        (str(target),),
                    )
                    db.execute("SELECT sqlcipher_export('encrypted')").fetchone()
                    db.execute("DETACH DATABASE encrypted")
            else:
                source_db = readonly(source, settings)
                target_db = connect_database(target, target_settings)
                try:
                    source_db.backup(target_db)
                    target_db.execute("PRAGMA journal_mode=DELETE").fetchone()
                finally:
                    source_db.close()
                    target_db.close()
            target.chmod(0o600)
            integrity(target, target_settings)
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
        verify_snapshot(destination, target_settings)
        return manifest


def verify_snapshot(directory, settings=None):
    directory = Path(directory).resolve()
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("format") != 1 or not 1 <= len(manifest.get("files", [])) <= 10000:
        raise ValueError("Unsupported or empty backup manifest.")
    if manifest.get("database_encryption", {"scheme": "none"}) != descriptor(settings):
        raise ValueError(
            "Backup encryption configuration or installation key does not match."
        )
    names = set()
    for item in manifest["files"]:
        path = safe_child(directory, item["path"])
        if (
            item["path"] in names
            or not path.is_file()
            or checksum(path) != item["sha256"]
            or ("bytes" in item and path.stat().st_size != item["bytes"])
        ):
            raise ValueError(
                "Backup file is missing, duplicated, or its checksum changed."
            )
        names.add(item["path"])
        integrity(path, settings)
    if "identity.db" not in names or not set(
        manifest["organization_paths"].values()
    ).issubset(names):
        raise ValueError("Backup is missing identity or workspace databases.")
    with closing(readonly(directory / "identity.db", settings)) as db:
        org_ids = {row[0] for row in db.execute("SELECT id FROM organizations")}
    if org_ids != set(manifest["organization_paths"]):
        raise ValueError("Workspace mappings do not match the identity database.")
    return manifest


def restore_snapshot(
    directory,
    destination,
    settings=None,
    *,
    deletion_guard_path=None,
    trusted_guard_sha256=None,
):
    manifest = verify_snapshot(directory, settings)
    directory = Path(directory).resolve()
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError(
            "Restore requires a new destination. Existing installations are never overwritten."
        )
    from deletion_guard import check_snapshot, read_guard

    if deletion_guard_path is None and trusted_guard_sha256 is None:
        raise ValueError(
            "A current independently pinned deletion guard is required for every restore, including pre-deletion snapshots"
        )
    if (deletion_guard_path is None) != (trusted_guard_sha256 is None):
        raise ValueError(
            "Supply both the deletion guard and its independently retained current SHA-256"
        )
    if settings is None:
        raise ValueError(
            "Original installation settings and signing key are required to authenticate the deletion guard"
        )
    guard = read_guard(deletion_guard_path, trusted_guard_sha256, settings)
    check_snapshot(directory, manifest, settings, guard)
    destination.mkdir(parents=True, mode=0o700)
    with InstallationLock(destination):
        for item in manifest["files"]:
            target = safe_child(destination, item["path"])
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            shutil.copyfile(safe_child(directory, item["path"]), target)
            target.chmod(0o600)
        # Bind actual copied bytes before rebasing any identity paths. The input
        # can change between initial verification and copying.
        for item in manifest["files"]:
            target = safe_child(destination, item["path"])
            if checksum(target) != item["sha256"] or (
                "bytes" in item and target.stat().st_size != item["bytes"]
            ):
                raise ValueError(
                    "Copied snapshot changed during restore; destination is incomplete and must not be started"
                )
        check_snapshot(destination, manifest, settings, guard)
        with closing(connect_database(destination / "identity.db", settings)) as db, db:
            for org_id, relative in manifest["organization_paths"].items():
                db.execute(
                    "UPDATE organizations SET db_path=? WHERE id=?",
                    (str(safe_child(destination, relative)), org_id),
                )
            db.execute("DELETE FROM sessions")
            if db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='account_mfa'"
            ).fetchone():
                db.execute("DELETE FROM account_mfa WHERE enabled=0")
                db.execute("UPDATE account_mfa SET recovery='[]'")
            if db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='agent_keys'"
            ).fetchone():
                db.execute("UPDATE agent_keys SET revoked=1")
                db.execute("DELETE FROM agent_requests")
            if db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='password_resets'"
            ).fetchone():
                db.execute("DELETE FROM password_resets")
        for relative in set(manifest["organization_paths"].values()):
            path = safe_child(destination, relative)
            with closing(connect_database(path, settings)) as db, db:
                db.execute("UPDATE jobs SET state='interrupted' WHERE state='running'")
            integrity(path, settings)
        integrity(destination / "identity.db", settings)
    return {
        "restored_databases": len(manifest["files"]),
        "sessions_revoked": True,
        "source_modified": False,
        "deletion_guard_verified": True,
        "deletion_guard_receipts": len(guard["receipts"]),
        "deletion_protection": "Checked against the supplied independently pinned current guard.",
    }
