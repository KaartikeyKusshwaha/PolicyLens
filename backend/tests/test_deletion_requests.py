import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

import deletion_requests
from operations import canonical
from test_deletion import approved, preview, store_for
from test_product import add_customer, acting_as, member

REASON = {"reason": "Reviewed the complete inventory and retained-data limitations."}
APPROVAL = {
    **REASON,
    "discovery_reference": "TEST-DISCOVERY-REPORT",
    "discovery_evidence_sha256": "a" * 64,
    "acknowledge_retained_audit": True,
    "acknowledge_physical_and_restore_limits": True,
}


def aged(client):
    approved(client)
    customer = add_customer(client)
    store, _ = store_for(client)
    old = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    value = {**customer, "created_at": old, "updated_at": old}
    with store.connect() as db:
        db.execute(
            "UPDATE records SET created_at=?,updated_at=?,payload=? WHERE id=?",
            (old, old, canonical(value), customer["id"]),
        )
    return customer


def submit(client, customer):
    snapshot = preview(client, customer)
    response = client.post(
        "/api/retention/deletion-requests",
        json={
            "customer_id": customer["id"],
            "inventory_sha256": snapshot["inventory_sha256"],
            **REASON,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def action(client, value, verb, body=None):
    return client.post(
        f"/api/retention/deletion-requests/{value['id']}/{verb}", json=body or REASON
    )


def test_exact_review_is_independent_expiring_and_does_not_delete(workspace):
    client, *_ = workspace
    customer = aged(client)
    reviewer = member(client)
    initial = preview(client, customer)
    request = submit(client, customer)
    assert preview(client, customer)["inventory_sha256"] == initial["inventory_sha256"]
    detail = client.get(f"/api/retention/deletion-requests/{request['id']}").json()
    assert (
        not detail["stale"]
        and not detail["expired"]
        and not detail["execution_available"]
    )
    assert action(client, request, "approve", APPROVAL).status_code == 403
    with acting_as(client, reviewer):
        response = action(client, request, "approve", APPROVAL)
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "approved"
        assert action(client, request, "approve", APPROVAL).status_code == 409
    assert client.get("/api/customers").json()[0]["id"] == customer["id"]
    assert len(client.get("/api/retention").json()["deletion_requests"]) == 1
    assert client.get("/api/audit").json()["verification"]["valid"]


@pytest.mark.parametrize("change", ["customer", "hold", "copy"])
def test_changes_invalidate_submitted_plan(workspace, change):
    client, *_ = workspace
    customer = aged(client)
    reviewer = member(client)
    request = submit(client, customer)
    if change == "customer":
        store, _ = store_for(client)
        with store.connect() as db:
            row = db.execute(
                "SELECT payload FROM records WHERE id=?", (customer["id"],)
            ).fetchone()
            value = {**json.loads(row[0]), "notes": "Changed during review."}
            db.execute(
                "UPDATE records SET payload=? WHERE id=?",
                (canonical(value), customer["id"]),
            )
    elif change == "hold":
        assert (
            client.post(
                "/api/retention/holds",
                json={
                    "scope": "workspace",
                    "reason": "New hold during deletion review.",
                    "authority_reference": "TEST-STALE",
                },
            ).status_code
            == 201
        )
    else:
        assert client.get("/api/audit/export").status_code == 200
    with acting_as(client, reviewer):
        response = action(client, request, "approve", APPROVAL)
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "deletion_request_stale"
    assert client.get(f"/api/retention/deletion-requests/{request['id']}").json()[
        "stale"
    ]


def test_pending_requests_cancel_reject_and_prevent_duplicate(workspace):
    client, *_ = workspace
    customer = aged(client)
    reviewer = member(client)
    request = submit(client, customer)
    snapshot = preview(client, customer)
    body = {
        "customer_id": customer["id"],
        "inventory_sha256": snapshot["inventory_sha256"],
        **REASON,
    }
    assert client.post("/api/retention/deletion-requests", json=body).status_code == 409
    assert action(client, request, "reject").status_code == 403
    with acting_as(client, reviewer):
        assert action(client, request, "cancel").status_code == 403
        assert action(client, request, "reject").status_code == 200
    second = submit(client, customer)
    assert action(client, second, "cancel").status_code == 200
    assert action(client, second, "cancel").status_code == 409


def test_expiry_blocks_approval_but_allows_cancellation(workspace):
    client, *_ = workspace
    customer = aged(client)
    reviewer = member(client)
    request = submit(client, customer)
    store, _ = store_for(client)
    with store.connect() as db:
        request["expires_at"] = (
            datetime.now(timezone.utc) - timedelta(seconds=1)
        ).isoformat()
        db.execute(
            "UPDATE records SET payload=? WHERE id=?",
            (canonical(request), request["id"]),
        )
    with acting_as(client, reviewer):
        assert (
            action(client, request, "approve", APPROVAL).json()["detail"]["code"]
            == "deletion_request_expired"
        )
    assert client.get(f"/api/retention/deletion-requests/{request['id']}").json()[
        "expired"
    ]
    assert action(client, request, "cancel").status_code == 200


def test_remaining_blockers_and_limits_cannot_be_overridden(workspace):
    client, *_ = workspace
    approved(client)
    customer = add_customer(client)
    reviewer = member(client)
    request = submit(client, customer)
    with acting_as(client, reviewer):
        assert (
            action(client, request, "approve", APPROVAL).json()["detail"]["code"]
            == "deletion_request_blocked"
        )
    assert action(client, request, "cancel").status_code == 200
    store, _ = store_for(client)
    old = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    with store.connect() as db:
        db.execute(
            "UPDATE records SET created_at=?,updated_at=?,payload=? WHERE id=?",
            (
                old,
                old,
                canonical({**customer, "created_at": old, "updated_at": old}),
                customer["id"],
            ),
        )
    request = submit(client, customer)
    with acting_as(client, reviewer):
        assert (
            action(
                client,
                request,
                "approve",
                {**APPROVAL, "acknowledge_retained_audit": False},
            ).status_code
            == 422
        )
        assert (
            action(
                client,
                request,
                "approve",
                {**APPROVAL, "acknowledge_retained_audit": "true"},
            ).status_code
            == 422
        )


def test_submit_refuses_stale_preview_and_unbounded_snapshot(workspace, monkeypatch):
    client, *_ = workspace
    customer = aged(client)
    body = {"customer_id": customer["id"], "inventory_sha256": "0" * 64, **REASON}
    assert client.post("/api/retention/deletion-requests", json=body).status_code == 409
    monkeypatch.setattr(deletion_requests, "MAX_REQUEST_BYTES", 1)
    body["inventory_sha256"] = preview(client, customer)["inventory_sha256"]
    assert client.post("/api/retention/deletion-requests", json=body).status_code == 422
    assert client.get("/api/retention").json()["deletion_requests"] == []


def test_role_tenant_and_transaction_rollback(workspace, monkeypatch):
    client, *_ = workspace
    customer = aged(client)
    analyst = member(client, "analyst")
    auditor = member(client, "auditor")
    snapshot = preview(client, customer)
    body = {
        "customer_id": customer["id"],
        "inventory_sha256": snapshot["inventory_sha256"],
        **REASON,
    }
    for identity in (analyst, auditor):
        with acting_as(client, identity):
            assert (
                client.post("/api/retention/deletion-requests", json=body).status_code
                == 403
            )
    store, org = store_for(client)
    user = client.get("/api/auth/me").json()
    original = deletion_requests.audit

    def fail(*args):
        raise RuntimeError("Injected audit failure")

    monkeypatch.setattr(deletion_requests, "audit", fail)
    with pytest.raises(RuntimeError, match="Injected"):
        deletion_requests.create(
            store, org, deletion_requests.RequestInput(**body), user
        )
    monkeypatch.setattr(deletion_requests, "audit", original)
    assert client.get("/api/retention").json()["deletion_requests"] == []
    request = submit(client, customer)
    other = client.post(
        "/api/auth/workspaces", json={"name": "Isolated deletion review"}
    ).json()["id"]
    assert client.post(f"/api/auth/workspaces/{other}/switch").status_code == 200
    assert (
        client.get(f"/api/retention/deletion-requests/{request['id']}").status_code
        == 404
    )


def test_concurrent_review_has_one_winner(workspace):
    client, *_ = workspace
    customer = aged(client)
    reviewer = member(client)
    request = submit(client, customer)
    store, org = store_for(client)

    def approve(_):
        try:
            return deletion_requests.approve(
                store,
                org,
                request["id"],
                deletion_requests.ApprovalInput(**APPROVAL),
                reviewer["user"],
            )["status"]
        except HTTPException as exc:
            return exc.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(approve, range(2)))
    assert results.count("approved") == 1 and results.count(409) == 1


def test_request_capacity_refusal_preserves_existing_review_history(
    workspace, monkeypatch
):
    client, *_ = workspace
    customer = aged(client)
    request = submit(client, customer)
    assert action(client, request, "cancel").status_code == 200
    monkeypatch.setattr(deletion_requests, "MAX_REQUESTS", 1)
    snapshot = preview(client, customer)
    assert (
        client.post(
            "/api/retention/deletion-requests",
            json={
                "customer_id": customer["id"],
                "inventory_sha256": snapshot["inventory_sha256"],
                **REASON,
            },
        ).status_code
        == 422
    )
    assert (
        client.get("/api/retention").json()["deletion_requests"][0]["status"]
        == "cancelled"
    )


def test_encrypted_restore_retains_review_and_revalidates_inventory(tmp_path):
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
        authenticate(client)
        customer = aged(client)
        request = submit(client, customer)
    create_snapshot(settings, tmp_path / "snapshot")
    restore_snapshot(tmp_path / "snapshot", tmp_path / "restored", settings)
    recovered = settings.model_copy(
        update={"database_path": tmp_path / "restored" / "workspace.db"}
    )
    with TestClient(create_app(recovered, start_worker=False)) as client:
        response = client.post(
            "/api/auth/login",
            json={
                "email": "owner@example.invalid",
                "password": "Test-only-password-2026",
            },
        )
        assert response.status_code == 200
        value = client.get(f"/api/retention/deletion-requests/{request['id']}").json()
        assert value["request"]["id"] == request["id"]
        assert value["request"]["status"] == "requested"
        assert not value["stale"] and not value["execution_available"]


def test_signed_pack_retains_pinned_request_and_export_invalidates_its_review(
    workspace, tmp_path
):
    from test_evidence import setup_pack, unpack
    from verify_evidence_pack import verify_pack

    client, _, manager, org = setup_pack(workspace, tmp_path)
    customer = aged(client)
    request = submit(client, customer)
    response = client.get("/api/evidence/sponsor-pack")
    assert response.status_code == 200, response.text
    assert verify_pack(response.content, manager.status(org)["fingerprint"])["valid"]
    files = unpack(response.content)
    evidence = json.loads(files["evidence.json"])
    assert (
        evidence["records"]["deletion_request"][0]["inventory_sha256"]
        == request["inventory_sha256"]
    )
    assert (
        evidence["records"]["deletion_request"][0]["snapshot"]["candidates"]
        == request["snapshot"]["candidates"]
    )
    (tmp_path / "deletion-request-report.pdf").write_bytes(files["report.pdf"])
    # Export creates a new workspace copy; the prior request must require review
    # of that changed custody inventory rather than silently preserving approval.
    assert client.get(f"/api/retention/deletion-requests/{request['id']}").json()[
        "stale"
    ]
