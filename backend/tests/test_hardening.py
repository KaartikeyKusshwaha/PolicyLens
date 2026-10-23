import json
import sqlite3
import asyncio
import time
from contextlib import suppress

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from config import Settings
from main import create_app
from recovery import create_snapshot, restore_snapshot, verify_snapshot
from runtime import InstallationLock
from test_workflows import authenticate
from test_workflows import prepare
from test_product import add_customer


def test_installation_lock_prevents_second_process_and_online_backup(
    workspace, tmp_path
):
    _, _, _, settings = workspace
    with pytest.raises(RuntimeError, match="already running"):
        with InstallationLock(settings.database_path.parent):
            pass
    with pytest.raises(RuntimeError, match="already running"):
        create_snapshot(settings, tmp_path / "backup")
    assert not (tmp_path / "backup").exists()


def test_security_headers_and_cross_scheme_csrf(workspace):
    client, _, _, _ = workspace
    headers = client.get("/").headers
    assert "script-src 'self'" in headers["content-security-policy"]
    assert "frame-ancestors 'none'" in headers["content-security-policy"]
    assert "camera=()" in headers["permissions-policy"]
    assert client.get("/api/auth/me").headers["cache-control"] == "no-store"
    response = client.post("/api/auth/logout", headers={"Origin": "https://testserver"})
    assert response.status_code == 403
    assert client.get("/api/auth/me").status_code == 200


def test_chunked_body_limit_is_enforced_before_mutation(workspace):
    client, _, _, _ = workspace

    def body():
        for _ in range(7):
            yield b" " * 1_000_000

    response = client.post(
        "/api/customers", content=body(), headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 413
    assert client.get("/api/customers").json() == []


@pytest.mark.parametrize("hosts", ["*", "*.example.com", "https://example.com", ""])
def test_hostname_configuration_rejects_unsafe_values(hosts):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, allowed_hosts=hosts)


def test_public_deployment_requires_secure_cookies_and_hides_docs(tmp_path):
    with pytest.raises(ValidationError, match="COOKIE_SECURE"):
        Settings(_env_file=None, deployment_mode="public", cookie_secure=False)
    settings = Settings(
        _env_file=None,
        database_path=tmp_path / "public.db",
        deployment_mode="public",
        cookie_secure=True,
    )
    with TestClient(
        create_app(settings, start_worker=False), base_url="https://testserver"
    ) as client:
        authenticate(client)
        assert client.get("/api/auth/me").status_code == 200
        for path in ("/docs", "/redoc", "/openapi.json"):
            assert client.get(path).status_code == 404
        assert (
            "max-age=31536000" in client.get("/").headers["strict-transport-security"]
        )
        assert (
            "Secure"
            in client.post(
                "/api/auth/login",
                json={
                    "email": "owner@example.invalid",
                    "password": "Test-only-password-2026",
                },
            ).headers["set-cookie"]
        )

        assert client.get("http://testserver/").status_code == 403
        assert client.get("http://testserver/api/ready").status_code == 200


def test_full_snapshot_restores_all_workspaces_and_revokes_sessions(tmp_path):
    settings = Settings(_env_file=None, database_path=tmp_path / "original" / "main.db")
    with TestClient(create_app(settings, start_worker=False)) as client:
        authenticate(client)
        owner_org = client.get("/api/auth/me").json()["org_id"]
        client.app.state.hub.issue_password_reset("owner@example.invalid")
        added = client.post(
            "/api/customers",
            json={
                "external_id": "RECOVERY-1",
                "name": "Fictional Recovery Customer",
                "country": "IN",
            },
        )
        assert added.status_code == 201
        second = client.post(
            "/api/auth/workspaces", json={"name": "Second recovery workspace"}
        ).json()
        assert (
            client.post("/api/auth/workspaces/" + second["id"] + "/switch").status_code
            == 200
        )
        assert (
            client.post(
                "/api/customers",
                json={
                    "external_id": "RECOVERY-2",
                    "name": "Another Fictional Customer",
                    "country": "GB",
                },
            ).status_code
            == 201
        )
    backup = tmp_path / "snapshot"
    manifest = create_snapshot(settings, backup)
    assert len(manifest["files"]) == 3
    assert verify_snapshot(backup)["format"] == 1
    from recovery_helpers import guard_arguments

    result = restore_snapshot(
        backup, tmp_path / "restored", settings, **guard_arguments(settings, tmp_path)
    )
    assert result["sessions_revoked"]
    with sqlite3.connect(tmp_path / "restored" / "identity.db") as db:
        assert db.execute("SELECT count(*) FROM sessions").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM password_resets").fetchone()[0] == 0
        rows = db.execute("SELECT id,db_path FROM organizations").fetchall()
    assert len(rows) == 2
    for _, path in rows:
        assert str(tmp_path / "restored") in path
        with sqlite3.connect(path) as db:
            assert (
                db.execute(
                    "SELECT count(*) FROM records WHERE kind='customer'"
                ).fetchone()[0]
                == 1
            )
    restored_settings = Settings(
        _env_file=None, database_path=tmp_path / "restored" / "main.db"
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
        assert owner_org in {w["id"] for w in client.get("/api/auth/workspaces").json()}
    with pytest.raises(ValueError, match="never overwritten"):
        restore_snapshot(backup, tmp_path / "original")
    path = backup / manifest["files"][-1]["path"]
    with path.open("ab") as file:
        file.write(b"changed")
    with pytest.raises(ValueError, match="checksum"):
        verify_snapshot(backup)


def test_backup_rejects_directory_traversal(tmp_path):
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    (snapshot / "manifest.json").write_text(
        json.dumps(
            {
                "format": 1,
                "organization_paths": {},
                "files": [{"path": "../outside.db", "sha256": "bad"}],
            }
        )
    )
    with pytest.raises(ValueError, match="inside"):
        verify_snapshot(snapshot)


def test_cached_workspace_missing_storage_fails_without_creating_empty_file(workspace):
    client, _, _, settings = workspace
    path = settings.database_path
    moved = path.with_suffix(".temporarily-moved")
    path.rename(moved)
    try:
        response = client.get("/api/customers")
        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "workspace_storage_missing"
        assert not path.exists()
    finally:
        moved.rename(path)


def test_readiness_detects_a_stopped_background_worker(tmp_path):
    settings = Settings(_env_file=None, database_path=tmp_path / "worker.db")
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/ready").status_code == 200

        async def stop_worker():
            worker = client.app.state.worker
            worker.cancel()
            with suppress(asyncio.CancelledError):
                await worker

        client.portal.call(stop_worker)
        assert client.get("/api/ready").status_code == 503
        assert client.get("/api/ready").json() == {"status": "not_ready"}


def test_background_worker_consumes_queued_job_and_records_verified_steps(workspace):
    client, _, _, _ = prepare(workspace)
    customer = add_customer(client)
    queued = client.post(
        "/api/agents/jobs", json={"kind": "screening", "target_id": customer["id"]}
    )
    assert queued.status_code == 202
    worker = client.portal.start_task_soon(client.app.state.engine.loop)
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            result = client.get("/api/agents/jobs/" + queued.json()["id"]).json()
            if result["state"] not in ("queued", "running"):
                break
            time.sleep(0.05)
        assert result["state"] == "completed", result
        assert result["payload"]["model_attempts"] == 1
        assert {step["step"] for step in result["steps"]} == {
            "collect_evidence",
            "sanctions_screening",
            "model_identity",
            "draft_analysis",
            "verify_evidence",
        }
    finally:
        worker.cancel()
