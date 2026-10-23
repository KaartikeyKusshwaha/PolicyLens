import pytest
from fastapi.testclient import TestClient

from deploy import checkpoint_backup, deletion_state_backup
from deploy.export_backup import export_snapshot
from deploy.recovery_set import verify
from recovery import create_snapshot
from main import create_app
from test_checkpoint_backup import setup
from test_deletion_execution import prepared, run
from test_product import add_customer
import deletion_execution
from test_deletion_requests import REASON


@pytest.mark.parametrize("newer", ["database", "checkpoint"])
def test_individually_valid_database_and_checkpoint_versions_cannot_claim_consistent_recovery(
    tmp_path, newer
):
    settings, _, _, fingerprint, _ = setup(tmp_path)
    history = checkpoint_backup.export_bundle(settings)
    snapshots = tmp_path / "snapshots"
    snapshots.mkdir()
    create_snapshot(settings, snapshots / "snapshot-20261023T120000Z")
    database = export_snapshot(snapshots, settings)
    assert verify(
        database,
        database_key_file=settings.security_key_path,
        checkpoint_content=history,
        fingerprint=fingerprint,
    )["verified"]
    with TestClient(create_app(settings, start_worker=False)) as client:
        assert (
            client.post(
                "/api/auth/login",
                json={
                    "email": "owner@example.invalid",
                    "password": "Test-only-password-2026",
                },
            ).status_code
            == 200
        )
        client.headers["X-CSRF-Token"] = client.get("/api/auth/me").json()["csrf"]
        add_customer(client, reference="NEWER-RECOVERY-ROW")
    if newer == "database":
        create_snapshot(settings, snapshots / "snapshot-20261023T130000Z")
        database = export_snapshot(snapshots, settings)
    else:
        history = checkpoint_backup.export_bundle(settings)
    with pytest.raises(ValueError):
        verify(
            database,
            database_key_file=settings.security_key_path,
            checkpoint_content=history,
            fingerprint=fingerprint,
        )


def test_deletion_history_rejects_pre_deletion_snapshot_and_accepts_exact_post_deletion_set(
    tmp_path,
):
    settings, user, _, request, _ = prepared(tmp_path)
    snapshots = tmp_path / "snapshots"
    snapshots.mkdir()
    create_snapshot(settings, snapshots / "snapshot-20261023T120000Z")
    before = export_snapshot(snapshots, settings)
    run(settings, user, request)
    history = deletion_state_backup.export_bundle(settings)
    with pytest.raises(ValueError, match="absent from snapshot"):
        verify(
            before,
            database_key_file=settings.security_key_path,
            deletion_content=history,
        )
    create_snapshot(settings, snapshots / "snapshot-20261023T130000Z")
    after = export_snapshot(snapshots, settings)
    assert (
        verify(
            after,
            database_key_file=settings.security_key_path,
            deletion_content=history,
        )["deletion_receipts_checked"]
        == 1
    )
    # Old committed guards legitimately predate later workspace creation.
    with TestClient(create_app(settings, start_worker=False)) as client:
        login = client.post(
            "/api/auth/login",
            json={
                "email": "owner@example.invalid",
                "password": "Test-only-password-2026",
            },
        )
        assert login.status_code == 200
        client.headers["X-CSRF-Token"] = client.get("/api/auth/me").json()["csrf"]
        assert (
            client.post(
                "/api/auth/workspaces", json={"name": "Later retention workspace"}
            ).status_code
            == 201
        )
    create_snapshot(settings, snapshots / "snapshot-20261023T140000Z")
    assert (
        verify(
            export_snapshot(snapshots, settings),
            database_key_file=settings.security_key_path,
            deletion_content=history,
        )["workspaces"]
        == 2
    )


def test_history_workspace_roster_cannot_differ_from_database_snapshot(tmp_path):
    settings, _, _, fingerprint, _ = setup(tmp_path)
    snapshots = tmp_path / "snapshots"
    snapshots.mkdir()
    create_snapshot(settings, snapshots / "snapshot-20261023T120000Z")
    database = export_snapshot(snapshots, settings)
    with TestClient(create_app(settings, start_worker=False)) as client:
        login = client.post(
            "/api/auth/login",
            json={
                "email": "owner@example.invalid",
                "password": "Test-only-password-2026",
            },
        )
        assert login.status_code == 200
        client.headers["X-CSRF-Token"] = client.get("/api/auth/me").json()["csrf"]
        assert (
            client.post(
                "/api/auth/workspaces", json={"name": "Newer roster tenant"}
            ).status_code
            == 201
        )
    history = checkpoint_backup.export_bundle(settings)
    with pytest.raises(ValueError, match="workspace roster"):
        verify(
            database,
            database_key_file=settings.security_key_path,
            checkpoint_content=history,
            fingerprint=fingerprint,
        )


def test_proved_aborted_execution_history_matches_its_undeleted_snapshot(
    tmp_path, monkeypatch
):
    settings, user, _, request, _ = prepared(tmp_path)
    original = deletion_execution.audit

    def fail(*args, **kwargs):
        raise RuntimeError("Injected rollback")

    monkeypatch.setattr(deletion_execution, "audit", fail)
    with pytest.raises(RuntimeError):
        run(settings, user, request)
    monkeypatch.setattr(deletion_execution, "audit", original)
    deletion_execution.reconcile(
        settings, user["org_id"], request["id"], "abort", REASON["reason"]
    )
    history = deletion_state_backup.export_bundle(settings)
    snapshots = tmp_path / "snapshots"
    snapshots.mkdir()
    create_snapshot(settings, snapshots / "snapshot-20261023T120000Z")
    result = verify(
        export_snapshot(snapshots, settings),
        database_key_file=settings.security_key_path,
        deletion_content=history,
    )
    assert result["verified"] and result["deletion_receipts_checked"] == 0
