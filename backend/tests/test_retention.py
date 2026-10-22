import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import HTTPException

import retention
from test_product import acting_as, add_customer, member

REVIEW = {
    "reason": "Reviewed against the organization's documented retention decision."
}


def configuration(**overrides):
    return {
        "title": "Fictional pilot retention",
        "rationale": "Synthetic test policy, not a statutory retention recommendation.",
        "customer_days": 365,
        "resolved_case_days": 400,
        "terminal_job_days": 30,
        "backup_days": 45,
        "audit_minimum_days": 730,
        "external_copy_procedure": "Operator inventories all snapshots, exported packs and downstream copies before scheduling removal.",
        **overrides,
    }


def draft(client, **overrides):
    response = client.post("/api/retention/policies", json=configuration(**overrides))
    assert response.status_code == 201, response.text
    return response.json()


def test_policy_independent_approval_versioning_and_stale_drafts(workspace):
    client, *_ = workspace
    reviewer = member(client)
    first = draft(client)
    stale = draft(client, title="Parallel first policy draft")
    assert client.get("/api/retention").json()["active_policy"] is None
    assert (
        client.post(
            f"/api/retention/policies/{first['id']}/approve", json=REVIEW
        ).status_code
        == 403
    )
    with acting_as(client, reviewer):
        approved = client.post(
            f"/api/retention/policies/{first['id']}/approve", json=REVIEW
        )
        assert approved.status_code == 200
        assert approved.json()["configuration_sha256"] == first["configuration_sha256"]
        assert (
            client.post(
                f"/api/retention/policies/{stale['id']}/approve", json=REVIEW
            ).status_code
            == 409
        )
    assert (
        client.post("/api/retention/policies", json=configuration()).status_code == 409
    )
    replacement = draft(client, parent_id=first["id"], customer_days=500)
    with acting_as(client, reviewer):
        assert (
            client.post(
                f"/api/retention/policies/{replacement['id']}/approve", json=REVIEW
            ).status_code
            == 200
        )
        assert (
            client.post(
                f"/api/retention/policies/{replacement['id']}/approve", json=REVIEW
            ).status_code
            == 409
        )
    overview = client.get("/api/retention").json()
    assert overview["active_policy"]["id"] == replacement["id"]
    assert (
        next(p for p in overview["policies"] if p["id"] == first["id"])["status"]
        == "superseded"
    )
    assert not overview["deletion_enabled"]
    assert client.get("/api/audit").json()["verification"]["valid"]


def test_holds_apply_immediately_and_during_independent_release_review(workspace):
    client, *_ = workspace
    reviewer = member(client)
    customer = add_customer(client)
    hold = client.post(
        "/api/retention/holds",
        json={
            "scope": "customer",
            "target_id": customer["id"],
            "reason": "Preserve records during fictional investigation.",
            "authority_reference": "TEST-HOLD-1",
        },
    )
    assert hold.status_code == 201
    hold_id = hold.json()["id"]
    store = client.app.state.hub.store(client.get("/api/auth/me").json()["org_id"])
    with store.connect() as db:
        assert len(retention.blocking_holds(db, customer["id"])) == 1
        assert retention.blocking_holds(db, "another-customer") == []
    assert (
        client.post(
            f"/api/retention/holds/{hold_id}/request-release", json=REVIEW
        ).status_code
        == 200
    )
    with store.connect() as db:
        assert (
            retention.blocking_holds(db, customer["id"])[0]["status"]
            == "release_requested"
        )
    assert (
        client.post(
            f"/api/retention/holds/{hold_id}/approve-release", json=REVIEW
        ).status_code
        == 403
    )
    with acting_as(client, reviewer):
        assert (
            client.post(
                f"/api/retention/holds/{hold_id}/approve-release", json=REVIEW
            ).status_code
            == 200
        )
    with store.connect() as db:
        assert retention.blocking_holds(db, customer["id"]) == []
    assert (
        client.post(
            f"/api/retention/holds/{hold_id}/request-release", json=REVIEW
        ).status_code
        == 409
    )
    assert client.get("/api/audit").json()["verification"]["valid"]


def test_hold_scope_validation_and_workspace_case_blocking(workspace):
    client, *_ = workspace
    customer = add_customer(client)
    case = client.post(
        "/api/cases",
        json={
            "customer_id": customer["id"],
            "title": "Fictional retention case",
            "description": "Synthetic hold scope fixture.",
        },
    ).json()
    base = {
        "reason": "Preserve synthetic records for this test.",
        "authority_reference": "TEST-2",
    }
    assert (
        client.post(
            "/api/retention/holds",
            json={**base, "scope": "case", "target_id": "missing"},
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/retention/holds",
            json={**base, "scope": "workspace", "target_id": customer["id"]},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/retention/holds", json={**base, "scope": "customer"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/retention/holds",
            json={**base, "scope": "case", "target_id": case["id"]},
        ).status_code
        == 201
    )
    store = client.app.state.hub.store(client.get("/api/auth/me").json()["org_id"])
    with store.connect() as db:
        assert len(retention.blocking_holds(db, customer["id"], [case["id"]])) == 1
        assert retention.blocking_holds(db, customer["id"]) == []
    assert (
        client.post(
            "/api/retention/holds", json={**base, "scope": "workspace"}
        ).status_code
        == 201
    )
    with store.connect() as db:
        assert len(retention.blocking_holds(db, "any-customer")) == 1


def test_retention_isolation_and_roles(workspace):
    client, *_ = workspace
    reviewer, analyst, auditor = (
        member(client),
        member(client, "analyst"),
        member(client, "auditor"),
    )
    first = draft(client)
    with acting_as(client, analyst):
        assert client.get("/api/retention").status_code == 403
        assert (
            client.post("/api/retention/policies", json=configuration()).status_code
            == 403
        )
        assert (
            client.post(
                "/api/retention/holds",
                json={
                    "scope": "workspace",
                    "reason": "Synthetic legal hold reason.",
                    "authority_reference": "TEST",
                },
            ).status_code
            == 403
        )
    with acting_as(client, auditor):
        assert client.get("/api/retention").status_code == 200
        assert (
            client.post(
                f"/api/retention/policies/{first['id']}/approve", json=REVIEW
            ).status_code
            == 403
        )
    with acting_as(client, reviewer):
        assert (
            client.post("/api/retention/policies", json=configuration()).status_code
            == 403
        )
    other = client.post(
        "/api/auth/workspaces", json={"name": "Isolated retention tenant"}
    ).json()["id"]
    assert client.post(f"/api/auth/workspaces/{other}/switch").status_code == 200
    assert client.get("/api/retention").json()["policies"] == []
    assert (
        client.post(
            f"/api/retention/policies/{first['id']}/approve", json=REVIEW
        ).status_code
        == 404
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"customer_days": 0},
        {"backup_days": True},
        {"terminal_job_days": 1.5},
        {"audit_minimum_days": 36501},
        {"status": "active"},
        {"external_copy_procedure": ""},
    ],
)
def test_policy_rejects_invalid_or_authoritative_input(workspace, changes):
    client, *_ = workspace
    assert (
        client.post(
            "/api/retention/policies", json=configuration(**changes)
        ).status_code
        == 422
    )


def test_concurrent_policy_approval_has_one_winner_and_no_partial_supersession(
    workspace,
):
    client, *_ = workspace
    reviewer = member(client)
    a, b = draft(client), draft(client)
    store = client.app.state.hub.store(client.get("/api/auth/me").json()["org_id"])

    def approve(value):
        try:
            return retention.approve_policy(
                store, value["id"], retention.Review(**REVIEW), reviewer["user"]
            )["id"]
        except HTTPException as exc:
            return exc.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(approve, [a, b]))
    assert results.count(409) == 1
    with store.connect() as db:
        policies = retention.records(db, "retention_policy")
        assert sum(p["status"] == "active" for p in policies) == 1
        assert sum(p["status"] == "draft" for p in policies) == 1
        events = [
            json.loads(row[0])
            for row in db.execute(
                "SELECT data FROM audit_chain WHERE action='retention_policy_approved'"
            )
        ]
        assert len(events) == 1


def test_retention_transaction_rolls_back_on_audit_failure(workspace, monkeypatch):
    client, *_ = workspace
    original = retention.audit

    def fail(*args):
        raise RuntimeError("Injected audit failure")

    monkeypatch.setattr(retention, "audit", fail)
    user = client.get("/api/auth/me").json()
    store = client.app.state.hub.store(user["org_id"])
    with pytest.raises(RuntimeError, match="Injected"):
        retention.draft_policy(
            store, retention.RetentionPolicy(**configuration()), user
        )
    monkeypatch.setattr(retention, "audit", original)
    assert client.get("/api/retention").json()["policies"] == []


def test_retention_bounds_fail_without_silently_omitting_history(
    workspace, monkeypatch
):
    client, *_ = workspace
    draft(client)
    monkeypatch.setattr(retention, "MAX_GOVERNANCE_RECORDS", 1)
    assert (
        client.post("/api/retention/policies", json=configuration()).status_code == 422
    )
    assert len(client.get("/api/retention").json()["policies"]) == 1


def test_encrypted_recovery_preserves_active_policies_and_pending_holds(tmp_path):
    from datetime import datetime, timedelta, timezone
    from fastapi.testclient import TestClient
    from config import Settings
    from main import create_app
    from recovery import create_snapshot, restore_snapshot
    from test_workflows import authenticate

    settings = Settings(
        _env_file=None,
        database_path=tmp_path / "source" / "workspace.db",
        database_encryption="sqlcipher4",
        security_key_path=tmp_path / "private" / "installation.key",
    )
    with TestClient(create_app(settings, start_worker=False)) as client:
        identity = authenticate(client)
        reviewer = member(client)
        policy = draft(client)
        with acting_as(client, reviewer):
            assert (
                client.post(
                    f"/api/retention/policies/{policy['id']}/approve", json=REVIEW
                ).status_code
                == 200
            )
        response = client.post(
            "/api/retention/holds",
            json={
                "scope": "workspace",
                "reason": "Preserve synthetic recovery records.",
                "authority_reference": "RECOVERY-TEST",
            },
        )
        assert response.status_code == 201
        copy = client.post(
            "/api/retention/copies",
            json={
                "category": "backup",
                "scope": "workspace",
                "custodian": "Fictional recovery custodian",
                "location_reference": "RECOVERY-CUSTODY-TEST",
                "content_sha256": "a" * 64,
                "copy_created_at": (
                    datetime.now(timezone.utc) - timedelta(days=1000)
                ).isoformat(),
                "preserve_until": (
                    datetime.now(timezone.utc) - timedelta(days=1)
                ).isoformat(),
                "reason": "Retain custody metadata through the encrypted recovery drill.",
            },
        )
        assert copy.status_code == 201
        hold_id = response.json()["id"]
        assert (
            client.post(
                f"/api/retention/holds/{hold_id}/request-release", json=REVIEW
            ).status_code
            == 200
        )
    snapshot, restored = tmp_path / "snapshot", tmp_path / "restored"
    create_snapshot(settings, snapshot)
    restore_snapshot(snapshot, restored, settings)
    recovered_settings = settings.model_copy(
        update={"database_path": restored / "workspace.db"}
    )
    with TestClient(create_app(recovered_settings, start_worker=False)) as client:
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
        value = client.get("/api/retention").json()
        assert value["active_policy"]["id"] == policy["id"]
        assert value["holds"][0]["status"] == "release_requested"
        assert value["copies"][0]["id"] == copy.json()["id"]
        assert value["copies"][0]["status"] == "retained"
        with client.app.state.hub.store(identity["org_id"]).connect() as db:
            assert retention.blocking_holds(db)[0]["id"] == hold_id
