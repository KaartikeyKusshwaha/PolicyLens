import hashlib
import secrets
import sqlite3
from pathlib import Path
from contextlib import closing

import pytest
from recovery_helpers import guard_arguments
from fastapi.testclient import TestClient

from config import Settings
from database import DB_ERRORS, connect_database, descriptor
from main import create_app
from recovery import (
    create_snapshot,
    migrate_encryption,
    restore_snapshot,
    verify_snapshot,
)
from security import SecretBox
from test_password_auth import legacy_factor
from store import Store
from test_product import add_customer, add_policy
from test_workflows import authenticate


def configured(tmp_path, **values):
    return Settings(
        _env_file=None,
        database_path=tmp_path / "data" / "workspace.db",
        security_key_path=tmp_path / "private" / "installation.key",
        database_encryption="sqlcipher4",
        **values,
    )


def test_encrypted_app_identity_workspaces_fts_and_workspace_backup(tmp_path):
    settings = configured(tmp_path)
    with TestClient(create_app(settings, start_worker=False)) as client:
        identity = authenticate(client)
        policy = add_policy(client)
        add_customer(client, name="Fictional encrypted customer marker")
        assert client.app.state.store.search("identity")[0]["policy_id"] == policy["id"]
        status = client.get("/api/health").json()["database_encryption"]
        assert status["verified"] and status["scheme"] == "sqlcipher4"
        assert status["key_fingerprint"] == descriptor(settings)["key_fingerprint"]
        original = identity["org_id"]
        other = client.post(
            "/api/auth/workspaces", json={"name": "Encrypted second workspace"}
        ).json()["id"]
        assert client.post(f"/api/auth/workspaces/{other}/switch").status_code == 200
        assert client.get("/api/customers").json() == []
        assert client.post(f"/api/auth/workspaces/{original}/switch").status_code == 200
        backup = client.post("/api/backups")
        assert backup.status_code == 201, backup.text
        assert backup.json()["database_encryption"]["scheme"] == "sqlcipher4"
        downloaded = client.get(backup.json()["download_url"])
        path = tmp_path / "downloaded-cipher-backup.db"
        path.write_bytes(downloaded.content)
        assert not downloaded.content.startswith(b"SQLite format 3")
        db = connect_database(path, settings, readonly=True)
        try:
            assert db.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
            assert db.execute("PRAGMA cipher_integrity_check").fetchall() == []
            assert db.execute("SELECT count(*) FROM policies").fetchone()[0] == 1
        finally:
            db.close()
    for database in settings.database_path.parent.rglob("*.db"):
        content = database.read_bytes()
        assert not content.startswith(b"SQLite format 3")
        assert b"owner@example.invalid" not in content
        assert b"Fictional encrypted customer marker" not in content
        with sqlite3.connect(database) as plain:
            with pytest.raises(sqlite3.DatabaseError):
                plain.execute("SELECT count(*) FROM sqlite_master").fetchone()
    with TestClient(create_app(settings, start_worker=False)) as restarted:
        response = restarted.post(
            "/api/auth/login",
            json={
                "email": "owner@example.invalid",
                "password": "Test-only-password-2026",
            },
        )
        assert response.status_code == 200
        restarted.headers["X-CSRF-Token"] = response.json()["csrf"]
        assert (
            restarted.post(f"/api/auth/workspaces/{original}/switch").status_code == 200
        )
        assert restarted.get("/api/policies").json()[0]["id"] == policy["id"]


def test_missing_key_is_not_regenerated_even_when_another_database_is_new(tmp_path):
    settings = configured(tmp_path)
    Store(settings.database_path, settings)
    held = settings.security_key_path.with_suffix(".held")
    settings.security_key_path.rename(held)
    before = hashlib.sha256(settings.database_path.read_bytes()).hexdigest()
    with pytest.raises(RuntimeError, match="key is unavailable"):
        Store(settings.database_path, settings)
    with pytest.raises(RuntimeError, match="key is unavailable"):
        Store(settings.database_path.parent / "another.db", settings)
    assert not settings.security_key_path.exists()
    assert not (settings.database_path.parent / "another.db").exists()
    assert hashlib.sha256(settings.database_path.read_bytes()).hexdigest() == before


def test_wrong_key_and_plaintext_configuration_never_fall_back(tmp_path):
    settings = configured(tmp_path)
    Store(settings.database_path, settings)
    before = settings.database_path.read_bytes()
    settings.security_key_path.write_bytes(secrets.token_bytes(32))
    with pytest.raises(DB_ERRORS):
        Store(settings.database_path, settings)
    with pytest.raises(sqlite3.DatabaseError):
        Store(settings.database_path)
    assert settings.database_path.read_bytes() == before


def test_existing_plaintext_is_not_rewritten_when_encryption_is_selected(tmp_path):
    settings = configured(tmp_path)
    Store(settings.database_path)
    before = settings.database_path.read_bytes()
    settings.security_key_path.parent.mkdir(parents=True)
    settings.security_key_path.write_bytes(secrets.token_bytes(32))
    settings.security_key_path.chmod(0o600)
    with pytest.raises(DB_ERRORS):
        Store(settings.database_path, settings)
    assert settings.database_path.read_bytes() == before


def test_public_encrypted_startup_requires_preprovisioned_key(tmp_path):
    settings = configured(tmp_path, deployment_mode="public", cookie_secure=True)
    with pytest.raises(RuntimeError, match="key is unavailable"):
        Store(settings.database_path, settings)
    assert not settings.database_path.exists()
    settings.security_key_path.parent.mkdir(parents=True)
    settings.security_key_path.write_bytes(secrets.token_bytes(32))
    settings.security_key_path.chmod(0o600)
    store = Store(settings.database_path, settings)
    with store.connect() as db:
        assert db.execute("PRAGMA cipher_status").fetchone()[0] == "1"


def test_readiness_fails_after_key_loss(tmp_path):
    settings = configured(tmp_path)
    with TestClient(create_app(settings, start_worker=False)) as client:
        authenticate(client)
        assert client.get("/api/ready").status_code == 200
        settings.security_key_path.rename(
            Path(str(settings.security_key_path) + ".held")
        )
        assert client.get("/api/ready").status_code == 503


def test_encrypted_full_snapshot_restore_preserves_tenants_and_fts(tmp_path):
    settings = configured(tmp_path)
    with TestClient(create_app(settings, start_worker=False)) as client:
        identity = authenticate(client)
        policy = add_policy(client)
        add_customer(client, name="Fictional encrypted recovery customer")
        client.app.state.hub.issue_password_reset("owner@example.invalid")
        second = client.post(
            "/api/auth/workspaces", json={"name": "Second encrypted recovery tenant"}
        ).json()["id"]
        assert client.post(f"/api/auth/workspaces/{second}/switch").status_code == 200
        add_customer(client, name="Second fictional recovery customer")
    backup = tmp_path / "snapshot"
    manifest = create_snapshot(settings, backup)
    assert len(manifest["files"]) == 3
    assert manifest["database_encryption"] == descriptor(settings)
    assert verify_snapshot(backup, settings) == manifest
    for item in manifest["files"]:
        content = (backup / item["path"]).read_bytes()
        assert not content.startswith(b"SQLite format 3")
        assert b"Fictional encrypted recovery customer" not in content
    source_hashes = {
        item["path"]: (backup / item["path"]).read_bytes() for item in manifest["files"]
    }
    restored = tmp_path / "restored"
    assert restore_snapshot(
        backup, restored, settings, **guard_arguments(settings, tmp_path)
    )["sessions_revoked"]
    with closing(
        connect_database(restored / "identity.db", settings, readonly=True)
    ) as db:
        assert db.execute("SELECT count(*) FROM sessions").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM password_resets").fetchone()[0] == 0
        paths = dict(db.execute("SELECT id,db_path FROM organizations"))
    assert set(paths) == {identity["org_id"], second}
    for path in paths.values():
        assert Path(path).is_relative_to(restored)
        with closing(connect_database(path, settings, readonly=True)) as db:
            assert (
                db.execute(
                    "SELECT count(*) FROM records WHERE kind='customer'"
                ).fetchone()[0]
                == 1
            )
    assert (
        Store(Path(paths[identity["org_id"]]), settings).search("identity")[0][
            "policy_id"
        ]
        == policy["id"]
    )
    restored_settings = settings.model_copy(
        update={"database_path": restored / settings.database_path.name}
    )
    with TestClient(create_app(restored_settings, start_worker=False)) as client:
        signed_in = client.post(
            "/api/auth/login",
            json={
                "email": "owner@example.invalid",
                "password": "Test-only-password-2026",
            },
        )
        assert signed_in.status_code == 200
        assert len(client.get("/api/auth/workspaces").json()) == 2
    assert all(
        (backup / name).read_bytes() == content
        for name, content in source_hashes.items()
    )


def test_encrypted_snapshot_rejects_wrong_mode_key_and_corrupt_page(tmp_path):
    settings = configured(tmp_path)
    with TestClient(create_app(settings, start_worker=False)) as client:
        authenticate(client)
    backup = tmp_path / "snapshot"
    manifest = create_snapshot(settings, backup)
    with pytest.raises(ValueError, match="encryption configuration"):
        verify_snapshot(backup)
    wrong_key = tmp_path / "wrong.key"
    wrong_key.write_bytes(secrets.token_bytes(32))
    wrong_key.chmod(0o600)
    wrong_settings = settings.model_copy(update={"security_key_path": wrong_key})
    with pytest.raises(ValueError, match="installation key"):
        restore_snapshot(backup, tmp_path / "must-not-exist", wrong_settings)
    assert not (tmp_path / "must-not-exist").exists()
    target = backup / manifest["files"][-1]["path"]
    content = bytearray(target.read_bytes())
    content[len(content) // 2] ^= 1
    target.write_bytes(content)
    with pytest.raises(ValueError, match="checksum"):
        verify_snapshot(backup, settings)


def test_plaintext_migration_preserves_source_identity_fts_and_recovery(tmp_path):
    plain = configured(tmp_path).model_copy(update={"database_encryption": "none"})
    with TestClient(create_app(plain, start_worker=False)) as client:
        identity = authenticate(client)
        policy = add_policy(client)
        add_customer(client, name="Fictional migration customer marker")
        second = client.post(
            "/api/auth/workspaces", json={"name": "Migration tenant two"}
        ).json()["id"]
        # Historic encrypted material and signing derivations still need the same key.
        protected = SecretBox(plain).encrypt(
            "fictional-existing-secret", "migration-test"
        )
        legacy_factor(client.app.state.hub, identity["id"])
    originals = {
        path: path.read_bytes() for path in plain.database_path.parent.rglob("*.db")
    }
    key_before = plain.security_key_path.read_bytes()
    snapshot = tmp_path / "migration-snapshot"
    plain.security_key_path.write_bytes(secrets.token_bytes(32))
    with pytest.raises(RuntimeError, match="Encrypted secret could not be verified"):
        migrate_encryption(plain, snapshot)
    assert not snapshot.exists()
    plain.security_key_path.write_bytes(key_before)
    result = migrate_encryption(plain, snapshot)
    encrypted_settings = plain.model_copy(update={"database_encryption": "sqlcipher4"})
    assert result["database_encryption"] == descriptor(encrypted_settings)
    assert len(result["files"]) == 3
    assert all(path.read_bytes() == content for path, content in originals.items())
    assert plain.security_key_path.read_bytes() == key_before
    assert (
        SecretBox(encrypted_settings).decrypt(protected, "migration-test")
        == "fictional-existing-secret"
    )
    for item in result["files"]:
        content = (snapshot / item["path"]).read_bytes()
        assert not content.startswith(b"SQLite format 3")
        assert b"Fictional migration customer marker" not in content
    restored = tmp_path / "encrypted-installation"
    restore_snapshot(
        snapshot, restored, encrypted_settings, **guard_arguments(plain, tmp_path)
    )
    restarted_settings = encrypted_settings.model_copy(
        update={"database_path": restored / plain.database_path.name}
    )
    with TestClient(create_app(restarted_settings, start_worker=False)) as client:
        response = client.post(
            "/api/auth/login",
            json={
                "email": "owner@example.invalid",
                "password": "Test-only-password-2026",
            },
        )
        assert response.status_code == 200
        client.headers["X-CSRF-Token"] = response.json()["csrf"]
        assert client.get("/api/auth/mfa").status_code == 404
        assert {w["id"] for w in client.get("/api/auth/workspaces").json()} == {
            identity["org_id"],
            second,
        }
        assert (
            client.post(f"/api/auth/workspaces/{identity['org_id']}/switch").status_code
            == 200
        )
        assert (
            client.get("/api/customers").json()[0]["name"]
            == "Fictional migration customer marker"
        )
        assert (
            client.app.state.hub.store(identity["org_id"]).search("identity")[0][
                "policy_id"
            ]
            == policy["id"]
        )
    create_snapshot(restarted_settings, tmp_path / "post-migration-backup")
    assert verify_snapshot(tmp_path / "post-migration-backup", restarted_settings)[
        "database_encryption"
    ] == descriptor(encrypted_settings)
    with pytest.raises(FileExistsError):
        migrate_encryption(plain, snapshot)


def test_migration_requires_original_key_and_stopped_source(tmp_path):
    plain = configured(tmp_path).model_copy(update={"database_encryption": "none"})
    destination = tmp_path / "not-created"
    with TestClient(create_app(plain, start_worker=False)) as client:
        authenticate(client)
        with pytest.raises(RuntimeError, match="key is unavailable"):
            migrate_encryption(plain, destination)
        SecretBox(plain).key(create=True)
        with pytest.raises(RuntimeError, match="already running"):
            migrate_encryption(plain, destination)
    assert not destination.exists()
    with pytest.raises(ValueError, match="plaintext source"):
        migrate_encryption(
            plain.model_copy(update={"database_encryption": "sqlcipher4"}), destination
        )
