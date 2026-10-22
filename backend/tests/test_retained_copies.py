from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

import retained_copies
from test_deletion import approved, preview, codes, store_for
from test_product import acting_as, add_customer, member
from test_retention import REVIEW, draft


def copy_input(**overrides):
    return {
        "category": "backup",
        "scope": "workspace",
        "custodian": "Fictional backup operator",
        "location_reference": "TEST-CUSTODY-REFERENCE",
        "content_sha256": "a" * 64,
        "copy_created_at": (
            datetime.now(timezone.utc) - timedelta(days=1000)
        ).isoformat(),
        "preserve_until": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
        "reason": "Register this fictional backup copy for retention review.",
        **overrides,
    }


def register(client, **overrides):
    response = client.post("/api/retention/copies", json=copy_input(**overrides))
    assert response.status_code == 201, response.text
    return response.json()


def step(client, copy, action, **body):
    return client.post(
        f"/api/retention/copies/{copy['id']}/{action}", json={**REVIEW, **body}
    )


def test_copy_removal_requires_authorization_report_and_independent_confirmation(
    workspace,
):
    client, *_ = workspace
    approved(client)
    checker = member(client, "admin")
    copy = register(client)
    assert copy["status"] == "retained"
    assert (
        step(
            client,
            copy,
            "report-removal",
            evidence_reference="TEST-REPORT",
            evidence_sha256="b" * 64,
        ).status_code
        == 409
    )
    assert step(client, copy, "request-removal").status_code == 200
    assert step(client, copy, "approve-removal").status_code == 403
    with acting_as(client, checker):
        assert step(client, copy, "approve-removal").status_code == 200
        assert step(client, copy, "confirm-removal").status_code == 409
    report = step(
        client,
        copy,
        "report-removal",
        evidence_reference="TEST-REPORT",
        evidence_sha256="b" * 64,
    )
    assert report.status_code == 200 and report.json()["status"] == "removal_reported"
    assert step(client, copy, "confirm-removal").status_code == 403
    with acting_as(client, checker):
        result = step(client, copy, "confirm-removal")
        assert result.status_code == 200
        assert result.json()["status"] == "removal_confirmed"
        assert len(result.json()["history"]) == 5
        assert result.json()["evidence_sha256"] == "b" * 64
    assert step(client, copy, "request-removal").status_code == 409
    assert step(client, copy, "cancel-removal").status_code == 409
    assert client.get("/api/audit").json()["verification"]["valid"]


@pytest.mark.parametrize("scope", ["workspace", "customer", "case"])
def test_customer_case_and_pending_release_holds_block_copy_removal(workspace, scope):
    client, *_ = workspace
    approved(client)
    customer = add_customer(client)
    case = client.post(
        "/api/cases",
        json={
            "customer_id": customer["id"],
            "title": "Fictional copy review case",
            "description": "Hold scope check.",
        },
    ).json()
    target_id = (
        customer["id"] if scope == "customer" else case["id"] if scope == "case" else ""
    )
    copy = register(client, scope=scope, target_id=target_id)
    # A customer hold also applies to this customer's case and to workspace copies.
    hold = client.post(
        "/api/retention/holds",
        json={
            "scope": "customer",
            "target_id": customer["id"],
            "reason": "Preserve fictional copied evidence.",
            "authority_reference": "COPY-HOLD",
        },
    ).json()
    assert step(client, copy, "request-removal").status_code == 409
    assert (
        client.post(
            f"/api/retention/holds/{hold['id']}/request-release", json=REVIEW
        ).status_code
        == 200
    )
    assert step(client, copy, "request-removal").status_code == 409


def test_case_hold_blocks_customer_copy_and_unrelated_customer_is_not_held(workspace):
    client, *_ = workspace
    approved(client)
    customer = add_customer(client)
    other = add_customer(
        client, reference="OTHER-COPY", name="Unrelated fictional customer"
    )
    case = client.post(
        "/api/cases",
        json={
            "customer_id": customer["id"],
            "title": "Copy hold relationship",
            "description": "Synthetic hold relation.",
        },
    ).json()
    copy = register(client, scope="customer", target_id=customer["id"])
    other_copy = register(client, scope="customer", target_id=other["id"])
    assert (
        client.post(
            "/api/retention/holds",
            json={
                "scope": "case",
                "target_id": case["id"],
                "reason": "Preserve fictional case evidence.",
                "authority_reference": "CASE-COPY-HOLD",
            },
        ).status_code
        == 201
    )
    assert step(client, copy, "request-removal").status_code == 409
    assert step(client, other_copy, "request-removal").status_code == 200


def test_hold_added_after_authorization_blocks_removal_report(workspace):
    client, *_ = workspace
    approved(client)
    checker = member(client, "admin")
    copy = register(client)
    assert step(client, copy, "request-removal").status_code == 200
    with acting_as(client, checker):
        assert step(client, copy, "approve-removal").status_code == 200
    assert (
        client.post(
            "/api/retention/holds",
            json={
                "scope": "workspace",
                "reason": "New hold after removal authorization.",
                "authority_reference": "LATE-HOLD",
            },
        ).status_code
        == 201
    )
    assert (
        step(
            client,
            copy,
            "report-removal",
            evidence_reference="TEST",
            evidence_sha256="c" * 64,
        ).status_code
        == 409
    )
    assert step(client, copy, "cancel-removal").status_code == 200
    assert client.get("/api/retention").json()["copies"][0]["status"] == "retained"


def test_new_policy_invalidates_authorization_and_cancel_preserves_history(workspace):
    client, *_ = workspace
    original_policy = approved(client)
    checker = member(client, "admin")
    copy = register(client)
    assert step(client, copy, "request-removal").status_code == 200
    with acting_as(client, checker):
        assert step(client, copy, "approve-removal").status_code == 200
    replacement = draft(client, parent_id=original_policy["id"], backup_days=100)
    with acting_as(client, checker):
        assert (
            client.post(
                f"/api/retention/policies/{replacement['id']}/approve", json=REVIEW
            ).status_code
            == 200
        )
    assert (
        step(
            client,
            copy,
            "report-removal",
            evidence_reference="TEST",
            evidence_sha256="c" * 64,
        ).status_code
        == 409
    )
    cancelled = step(client, copy, "cancel-removal")
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "retained"
    assert cancelled.json()["history"][1]["policy_id"] == original_policy["id"]
    assert "removal_approved_by" not in cancelled.json()
    assert (
        step(client, copy, "request-removal").json()["removal_policy_id"]
        == replacement["id"]
    )


def test_minimum_policy_and_declared_preservation_dates_cannot_be_shortened(workspace):
    client, *_ = workspace
    approved(client)
    recent = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    response = client.post(
        "/api/retention/copies",
        json=copy_input(
            copy_created_at=recent,
            preserve_until=datetime.now(timezone.utc).isoformat(),
        ),
    )
    assert response.status_code == 422
    future = (datetime.now(timezone.utc) + timedelta(days=100)).isoformat()
    copy = register(client, copy_created_at=recent, preserve_until=future)
    assert step(client, copy, "request-removal").status_code == 409
    # Pack exports contain audit and multiple business sections; max period applies.
    response = client.post(
        "/api/retention/copies",
        json=copy_input(
            category="evidence_export",
            copy_created_at=(
                datetime.now(timezone.utc) - timedelta(days=100)
            ).isoformat(),
        ),
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    "changes",
    [
        {"scope": "workspace", "target_id": "not-empty"},
        {"scope": "customer"},
        {"content_sha256": "bad"},
        {"copy_created_at": "2026-10-01T00:00:00"},
        {"preserve_until": "2000-01-01T00:00:00Z"},
        {"status": "removal_confirmed"},
        {"copy_created_at": 0},
        {"preserve_until": 1890000000},
    ],
)
def test_copy_input_rejects_unbound_dates_scope_and_authoritative_fields(
    workspace, changes
):
    client, *_ = workspace
    approved(client)
    assert (
        client.post("/api/retention/copies", json=copy_input(**changes)).status_code
        == 422
    )


def test_copy_scope_roles_tenants_and_unknown_targets(workspace):
    client, *_ = workspace
    assert client.post("/api/retention/copies", json=copy_input()).status_code == 409
    approved(client)
    copy = register(client)
    assert (
        client.post(
            "/api/retention/copies", json=copy_input(scope="case", target_id="missing")
        ).status_code
        == 404
    )
    for role in ("analyst", "auditor"):
        identity = member(client, role)
        with acting_as(client, identity):
            assert (
                client.post("/api/retention/copies", json=copy_input()).status_code
                == 403
            )
            assert step(client, copy, "request-removal").status_code == 403
    other = client.post(
        "/api/auth/workspaces", json={"name": "Isolated copy registry"}
    ).json()["id"]
    assert client.post(f"/api/auth/workspaces/{other}/switch").status_code == 200
    assert client.get("/api/retention").json()["copies"] == []
    assert step(client, copy, "request-removal").status_code == 404


def test_copy_registry_changes_bind_customer_deletion_inventory(workspace):
    client, *_ = workspace
    approved(client)
    customer = add_customer(client)
    initial = preview(client, customer)
    copy = register(client)
    registered = preview(client, customer)
    assert registered["inventory_sha256"] != initial["inventory_sha256"]
    assert "registered_copy_outstanding" in codes(registered)
    assert registered["external_copies"][0]["id"] == copy["id"]
    assert step(client, copy, "request-removal").status_code == 200
    assert (
        preview(client, customer)["inventory_sha256"] != registered["inventory_sha256"]
    )


def test_copy_transitions_roll_back_when_audit_fails(workspace, monkeypatch):
    client, *_ = workspace
    approved(client)
    store, _ = store_for(client)
    user = client.get("/api/auth/me").json()

    def fail(*args):
        raise RuntimeError("Injected copy audit failure")

    monkeypatch.setattr(retained_copies, "audit", fail)
    with pytest.raises(RuntimeError, match="Injected"):
        retained_copies.register(store, retained_copies.CopyInput(**copy_input()), user)
    assert client.get("/api/retention").json()["copies"] == []


def test_concurrent_copy_authorizations_have_one_winner(workspace):
    client, *_ = workspace
    approved(client)
    checker = member(client, "admin")
    copy = register(client)
    assert step(client, copy, "request-removal").status_code == 200
    store, _ = store_for(client)

    def approve_once(_):
        try:
            return retained_copies.approve_removal(
                store, copy["id"], retained_copies.CopyReview(**REVIEW), checker["user"]
            )["status"]
        except HTTPException as exc:
            return exc.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        result = list(pool.map(approve_once, range(2)))
    assert result.count("removal_authorized") == 1 and result.count(409) == 1


def test_hold_before_report_confirmation_keeps_copy_outstanding(workspace):
    client, *_ = workspace
    approved(client)
    checker = member(client, "admin")
    copy = register(client)
    assert step(client, copy, "request-removal").status_code == 200
    with acting_as(client, checker):
        assert step(client, copy, "approve-removal").status_code == 200
    assert (
        step(
            client,
            copy,
            "report-removal",
            evidence_reference="TEST-REPORT",
            evidence_sha256="b" * 64,
        ).status_code
        == 200
    )
    hold = client.post(
        "/api/retention/holds",
        json={
            "scope": "workspace",
            "reason": "Preserve copies pending independent report review.",
            "authority_reference": "CONFIRM-HOLD",
        },
    )
    assert hold.status_code == 201
    with acting_as(client, checker):
        assert step(client, copy, "confirm-removal").status_code == 409
    assert (
        client.get("/api/retention").json()["copies"][0]["status"] == "removal_reported"
    )


def test_copy_registry_and_history_bounds_fail_closed(workspace, monkeypatch):
    client, *_ = workspace
    approved(client)
    copy = register(client)
    monkeypatch.setattr(retained_copies, "MAX_COPIES", 1)
    assert (
        client.post(
            "/api/retention/copies", json=copy_input(location_reference="ANOTHER-COPY")
        ).status_code
        == 422
    )
    monkeypatch.setattr(retained_copies, "MAX_HISTORY", 1)
    assert step(client, copy, "request-removal").status_code == 422
    assert client.get("/api/retention").json()["copies"][0]["status"] == "retained"


def test_reported_removal_survives_policy_change_and_independent_rereview(workspace):
    client, *_ = workspace
    original = approved(client)
    checker = member(client, "admin")
    copy = register(client)
    assert step(client, copy, "request-removal").status_code == 200
    with acting_as(client, checker):
        assert step(client, copy, "approve-removal").status_code == 200
    assert (
        step(
            client,
            copy,
            "report-removal",
            evidence_reference="RETAINED-REPORT",
            evidence_sha256="c" * 64,
        ).status_code
        == 200
    )
    replacement = draft(client, parent_id=original["id"], backup_days=100)
    with acting_as(client, checker):
        assert (
            client.post(
                f"/api/retention/policies/{replacement['id']}/approve", json=REVIEW
            ).status_code
            == 200
        )
        assert step(client, copy, "confirm-removal").status_code == 409
    assert step(client, copy, "cancel-removal").status_code == 409
    assert step(client, copy, "review-reported-removal").status_code == 403
    with acting_as(client, checker):
        reviewed = step(client, copy, "review-reported-removal")
        assert reviewed.status_code == 200
        assert reviewed.json()["status"] == "removal_reported"
        assert reviewed.json()["evidence_reference"] == "RETAINED-REPORT"
        assert step(client, copy, "confirm-removal").status_code == 200


def test_customer_copy_hold_discovery_bound_does_not_omit_cases(workspace, monkeypatch):
    client, *_ = workspace
    approved(client)
    customer = add_customer(client)
    assert (
        client.post(
            "/api/cases",
            json={
                "customer_id": customer["id"],
                "title": "Case discovery bound",
                "description": "Synthetic scope capacity check.",
            },
        ).status_code
        == 201
    )
    copy = register(client, scope="customer", target_id=customer["id"])
    monkeypatch.setattr(retained_copies, "MAX_SCOPE_CASES", 0)
    assert step(client, copy, "request-removal").status_code == 422
