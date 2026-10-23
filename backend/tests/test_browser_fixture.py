import json
import sys
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from evaluation.browser_fixture import no_outbound, prepare, settings_for  # noqa: E402
from main import create_app  # noqa: E402


def test_fixture_survives_restart_with_roles_counts_and_no_secret_manifest(tmp_path):
    directory = tmp_path / "fixture"
    manifest = prepare(directory)
    credentials = json.loads((directory / "private" / "accounts.json").read_text())
    assert len(credentials) == 3
    assert all(row["password"] not in json.dumps(manifest) for row in credentials)
    assert (directory / "data" / "identity.db").read_bytes()[
        :16
    ] != b"SQLite format 3\x00"
    with TestClient(
        create_app(
            settings_for(directory),
            httpx.MockTransport(no_outbound),
            start_worker=False,
        )
    ) as client:
        for identity in credentials:
            login = client.post(
                "/api/auth/login",
                json={
                    "email": identity["email"],
                    "password": identity["password"],
                },
            )
            assert login.status_code == 200
            assert login.json()["role"] == identity["role"]
            assert len(client.get("/api/cases").json()) == 3
            assert len(client.get("/api/monitor/transactions").json()) == 6
        assert client.get("/api/ready").status_code == 200
    original = (directory / "fixture.json").read_bytes()
    with pytest.raises(FileExistsError):
        prepare(directory)
    assert (directory / "fixture.json").read_bytes() == original


def test_fixture_refuses_existing_directory_without_touching_contents(tmp_path):
    sentinel = tmp_path / "existing.txt"
    sentinel.write_text("preserve")
    with pytest.raises(FileExistsError):
        prepare(tmp_path)
    assert sentinel.read_text() == "preserve"
    assert not (tmp_path / "private").exists()
