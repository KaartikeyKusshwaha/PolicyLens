import hashlib
from contextlib import closing

import pytest
from fastapi.testclient import TestClient

from auth import Hub
from config import Settings
from database import connect_database
from main import create_app
from models import PolicyInput
from recovery import compact_encrypted, restore_snapshot, verify_snapshot
from recovery_helpers import guard_arguments
from test_workflows import authenticate, POLICY


def configured(tmp_path):
    return Settings(
        _env_file=None,
        database_path=tmp_path / "source" / "workspace.db",
        security_key_path=tmp_path / "private" / "key",
        database_encryption="sqlcipher4",
    )


def test_rebuild_removes_free_pages_keeps_encrypted_logical_data_and_fts(tmp_path):
    settings = configured(tmp_path)
    with TestClient(create_app(settings, start_worker=False)) as client:
        user = authenticate(client)
        second = client.post(
            "/api/auth/workspaces", json={"name": "Compaction isolation tenant"}
        ).json()["id"]
    hub = Hub(settings)
    original = hub.store(user["org_id"])
    policy = original.save_policy(PolicyInput(**POLICY))
    with original.connect() as db:
        db.execute(
            "CREATE TABLE synthetic_deleted_storage(id INTEGER PRIMARY KEY, payload TEXT)"
        )
        db.executemany(
            "INSERT INTO synthetic_deleted_storage VALUES (?,?)",
            [
                (index, "Synthetic removed storage block. " * 500)
                for index in range(150)
            ],
        )
        db.execute("DELETE FROM synthetic_deleted_storage")
    with original.connect() as db:
        assert db.execute("PRAGMA freelist_count").fetchone()[0] > 0
    originals = {
        path: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in settings.database_path.parent.rglob("*.db")
    }
    output = tmp_path / "compacted"
    manifest = compact_encrypted(settings, output)
    assert manifest["storage_rebuild"]["method"] == "sqlcipher_export"
    assert len(manifest["files"]) == 3
    assert verify_snapshot(output, settings) == manifest
    assert all(
        hashlib.sha256(path.read_bytes()).hexdigest() == digest
        for path, digest in originals.items()
    )
    for item in manifest["files"]:
        assert item["storage_rebuild"]["logical_rows_verified"]
        assert item["storage_rebuild"]["target_free_pages"] == 0
        path = output / item["path"]
        assert not path.read_bytes().startswith(b"SQLite format 3")
        with closing(connect_database(path, settings, readonly=True)) as db:
            assert db.execute("PRAGMA freelist_count").fetchone()[0] == 0
    with closing(
        connect_database(
            output / manifest["organization_paths"][user["org_id"]],
            settings,
            readonly=True,
        )
    ) as db:
        assert (
            db.execute(
                "SELECT policy_id FROM chunks WHERE chunks MATCH 'identity'"
            ).fetchone()[0]
            == policy["id"]
        )
    restored = tmp_path / "restored"
    restore_snapshot(output, restored, settings, **guard_arguments(settings, tmp_path))
    recovered = settings.model_copy(update={"database_path": restored / "workspace.db"})
    recovered_hub = Hub(recovered)
    assert {org["id"] for org in recovered_hub.organizations()} == {
        user["org_id"],
        second,
    }
    assert (
        recovered_hub.store(user["org_id"]).search("identity")[0]["policy_id"]
        == policy["id"]
    )


def test_rebuild_requires_stopped_encrypted_source_and_new_destination(tmp_path):
    settings = configured(tmp_path)
    with TestClient(create_app(settings, start_worker=False)) as client:
        authenticate(client)
        with pytest.raises(RuntimeError, match="already running"):
            compact_encrypted(settings, tmp_path / "online")
    assert not (tmp_path / "online").exists()
    with pytest.raises(ValueError, match="SQLCipher"):
        compact_encrypted(
            settings.model_copy(update={"database_encryption": "none"}),
            tmp_path / "plaintext",
        )
    output = tmp_path / "existing"
    output.mkdir()
    with pytest.raises(FileExistsError):
        compact_encrypted(settings, output)


def test_rebuild_failure_keeps_original_files_and_never_publishes_manifest(
    tmp_path, monkeypatch
):
    import recovery

    settings = configured(tmp_path)
    with TestClient(create_app(settings, start_worker=False)) as client:
        authenticate(client)
    before = {
        path: path.read_bytes() for path in settings.database_path.parent.rglob("*.db")
    }

    def fail(*args, **kwargs):
        raise ValueError("Injected target integrity failure")

    monkeypatch.setattr(recovery, "integrity", fail)
    with pytest.raises(ValueError, match="Injected"):
        compact_encrypted(settings, tmp_path / "failed")
    assert not (tmp_path / "failed" / "manifest.json").exists()
    assert all(path.read_bytes() == content for path, content in before.items())


def test_operator_compaction_command_explicitly_denies_erasure_proof(
    tmp_path, monkeypatch, capsys
):
    import manage
    import sys
    import json

    settings = configured(tmp_path)
    with TestClient(create_app(settings, start_worker=False)) as client:
        authenticate(client)
    monkeypatch.setattr(manage, "Settings", lambda: settings)
    monkeypatch.setattr(
        sys,
        "argv",
        ["manage.py", "compact-encrypted", "--output", str(tmp_path / "cli-output")],
    )
    manage.main()
    report = json.loads(capsys.readouterr().out)
    assert report["verified"] and report["source_modified"] is False
    assert report["physical_erasure_proven"] is False
    assert "does not prove" in report["storage_rebuild"]["scope"]
