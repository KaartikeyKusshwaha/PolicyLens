import json
from datetime import datetime, timedelta, timezone

import pytest

from intelligence import Intelligence, source_freshness
from fastapi import HTTPException
from operations import Operations
from test_product import acting_as, member
from test_toolkit import key
import work_digest


def test_digest_complete_counts_preview_and_no_side_effects(workspace):
    client, store, state, _ = workspace
    ops = Operations(store)
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    for i in range(23):
        ops.save("case", {"title": str(i), "status": "open", "due_at": past}, "test")
    ops.save("case", {"status": "resolved", "due_at": past}, "test")
    ops.save("case", {"status": "open", "due_at": "bad"}, "test")
    ops.save("case", {"status": "open", "due_at": "2020-01-01"}, "test")
    ops.save("rule", {"status": "draft"}, "test")
    ops.save("rule", {"status": "active"}, "test")
    ops.save("policy_change", {"status": "pending_review"}, "test")
    with store.connect() as db:
        before = db.execute("SELECT count(*) FROM audit_chain").fetchone()[0]
    response = client.get("/api/evidence/digest")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["queues"]["open_cases"]["count"] == 25
    assert data["queues"]["overdue_cases"]["count"] == 23
    assert len(data["queues"]["overdue_cases"]["items"]) == 20
    assert data["queues"]["overdue_cases"]["has_more"]
    assert data["queues"]["control_drafts"]["count"] == 1
    assert data["queues"]["policy_changes"]["count"] == 1
    assert data["invalid_due_dates"] == 2
    assert data["source_warnings"] == 1 and data["model_calls"] == 0
    assert not state["calls"]
    with store.connect() as db:
        assert db.execute("SELECT count(*) FROM audit_chain").fetchone()[0] == before
        assert db.execute("SELECT count(*) FROM jobs").fetchone()[0] == 0


def test_digest_freshness_refresh_disabled_sources_and_rolling_window(workspace):
    client, store, _, _ = workspace
    ops = Operations(store)
    ops.save("preferences", {"enabled_sources": ["ofac"]}, "test")
    current = datetime.now(timezone.utc)
    store.save_source(
        "ofac", {"fetched_at": current.isoformat(), "entries": [], "sha256": "test"}
    )
    with store.connect() as db:
        for i, hours in enumerate((1, 25, -1)):
            stamp = (current - timedelta(hours=hours)).isoformat()
            db.execute(
                "INSERT INTO alerts VALUES (?,?,?,?,?)",
                (str(i), str(i), None, stamp, "{}"),
            )
            db.execute(
                "INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?)",
                (str(i), "case", "test", "failed", stamp, stamp, "test", "{}"),
            )
    data = client.get("/api/evidence/digest").json()
    assert len(data["sources"]) == 1 and data["source_warnings"] == 0
    assert data["failed_runs"] == data["recent_alerts"] == 1
    store.save_source(
        "ofac", {"fetched_at": (current - timedelta(days=4)).isoformat(), "entries": []}
    )
    assert client.get("/api/evidence/digest").json()["source_warnings"] == 1


@pytest.mark.parametrize(
    "fetched", ["invalid", "2026-01-01", "9999-12-31T00:00:00+00:00", None]
)
def test_unusable_or_future_source_time_cannot_be_ready(fetched):
    assert source_freshness({"fetched_at": fetched}, 24) == "stale"


def test_digest_capacity_refuses_partial_and_malformed_records(workspace, monkeypatch):
    client, store, _, _ = workspace
    ops = Operations(store)
    ops.save("case", {"status": "open"}, "test")
    monkeypatch.setattr(work_digest, "MAX_RECORDS", 0)
    refused = client.get("/api/evidence/digest")
    assert refused.status_code == 409 and "queues" not in refused.json()
    monkeypatch.setattr(work_digest, "MAX_RECORDS", 10000)
    monkeypatch.setattr(work_digest, "MAX_BYTES", 1)
    assert client.get("/api/evidence/digest").status_code == 409
    monkeypatch.setattr(work_digest, "MAX_BYTES", 8 * 1024 * 1024)
    with store.connect() as db:
        db.execute(
            "UPDATE records SET payload=? WHERE kind='case'", (json.dumps(["invalid"]),)
        )
    assert client.get("/api/evidence/digest").status_code == 409


def test_digest_tenant_scope_human_roles_and_bearer_refusal(workspace):
    client, store, _, _ = workspace
    Operations(store).save("case", {"status": "open"}, "test")
    for role in ("analyst", "reviewer", "auditor"):
        identity = member(client, role)
        with acting_as(client, identity):
            assert (
                client.get("/api/evidence/digest").json()["queues"]["open_cases"][
                    "count"
                ]
                == 1
            )
    credential = key(client, scopes=["search_policy"])
    assert (
        client.get(
            "/api/evidence/digest",
            headers={"Authorization": "Bearer " + credential["token"]},
        ).status_code
        == 403
    )
    created = client.post("/api/auth/workspaces", json={"name": "Other workspace"})
    assert created.status_code == 201, created.text
    assert (
        client.post(
            "/api/auth/workspaces/" + created.json()["id"] + "/switch"
        ).status_code
        == 200
    )
    assert (
        client.get("/api/evidence/digest").json()["queues"]["open_cases"]["count"] == 0
    )


def test_digest_holds_one_read_snapshot_during_concurrent_change(
    workspace, monkeypatch
):
    client, store, _, _ = workspace
    ops = Operations(store)
    case = ops.save("case", {"status": "open"}, "test")
    original = work_digest.source_freshness

    def change_after_snapshot(*args):
        ops.save("case", {"status": "resolved"}, "test", case["id"])
        with store.connect() as db:
            db.execute(
                "INSERT INTO alerts VALUES ('concurrent','concurrent',?,?,'{}')",
                (case["id"], datetime.now(timezone.utc).isoformat()),
            )
        return original(*args)

    monkeypatch.setattr(work_digest, "source_freshness", change_after_snapshot)
    data = client.get("/api/evidence/digest").json()
    assert data["queues"]["open_cases"]["count"] == 1
    assert data["recent_alerts"] == 0
    monkeypatch.setattr(work_digest, "source_freshness", original)
    refreshed = client.get("/api/evidence/digest").json()
    assert refreshed["queues"]["open_cases"]["count"] == 0
    assert refreshed["recent_alerts"] == 1


def test_future_source_timestamp_blocks_screening_as_well_as_digest(workspace):
    client, store, _, settings = workspace
    store.save_source(
        "ofac", {"fetched_at": "9999-01-01T00:00:00+00:00", "entries": []}
    )
    assert client.get("/api/sources").json()["ofac"]["status"] == "stale"
    assert client.get("/api/evidence/digest").json()["source_warnings"] == 1
    with pytest.raises(HTTPException) as exc:
        Intelligence(settings, store, None).screen_names(
            {"customer": "Example Customer"}
        )
    assert exc.value.status_code == 409
