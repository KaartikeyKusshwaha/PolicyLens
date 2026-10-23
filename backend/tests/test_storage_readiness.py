import hashlib
from contextlib import closing
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from config import Settings
from database import connect_database
from main import create_app
from test_workflows import authenticate


@pytest.mark.parametrize("encryption", ["none", "sqlcipher4"])
@pytest.mark.parametrize("failure", ["missing", "wrong_file", "missing_table"])
def test_readiness_probes_uncached_tenant_without_recreating_or_repairing_storage(
    tmp_path, encryption, failure
):
    settings = Settings(
        _env_file=None,
        database_path=tmp_path / "data" / "workspace.db",
        database_encryption=encryption,
        security_key_path=tmp_path / "private" / "key",
    )
    with TestClient(create_app(settings, start_worker=False)) as client:
        authenticate(client)
        other = client.post(
            "/api/auth/workspaces", json={"name": "Uncached readiness tenant"}
        ).json()["id"]
        with client.app.state.hub.connect() as db:
            path = Path(
                db.execute(
                    "SELECT db_path FROM organizations WHERE id=?", (other,)
                ).fetchone()[0]
            )
        assert other not in client.app.state.hub.stores
        assert client.get("/api/ready").json() == {"status": "ready"}
        if failure == "missing":
            path.rename(path.with_suffix(".held"))
        elif failure == "wrong_file":
            path.rename(path.with_suffix(".held"))
            path.write_bytes(b"Unexpected storage contents; never expose this string")
        else:
            with closing(connect_database(path, settings)) as db, db:
                db.execute("DROP TABLE transactions")
        before = (
            hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
        )
        for _ in range(2):
            response = client.get("/api/ready")
            assert response.status_code == 503
            assert response.json() == {"status": "not_ready"}
        assert other not in client.app.state.hub.stores
        if before is None:
            assert not path.exists()
        else:
            assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_readiness_does_not_recreate_missing_identity_database(workspace):
    client, _, _, _ = workspace
    path = client.app.state.hub.path
    held = path.with_suffix(".held")
    path.rename(held)
    try:
        assert client.get("/api/ready").status_code == 503
        assert not path.exists()
    finally:
        held.rename(path)
