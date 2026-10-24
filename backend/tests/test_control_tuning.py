from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json

import pytest
from fastapi import HTTPException

import control_tuning as tuning
from operations import Operations, canonical
from product_models import RuleAction
from test_product import add_customer, add_policy, approve, acting_as, member, rule, txn



def setup(client, kind="amount", threshold="100"):
    reviewer = member(client)
    parent = approve(
        client,
        reviewer,
        rule(client, add_policy(client), kind=kind, threshold=threshold),
    )
    customer = add_customer(client)
    for index, amount in enumerate(("50", "150", "250")):
        response = client.post(
            "/api/monitor/transactions",
            json=txn(customer, "tuning-" + str(index), amount=amount),
        )
        assert response.status_code == 201, response.text
    return parent, customer, reviewer


def body(parent, **changes):
    return {
        "control_id": parent["id"],
        "candidate_thresholds": ["200", "300"],
        "target_match_count": 1,
        "rationale": "Compare internal operational workload against the stated review capacity.",
        **changes,
    }


def preview(client, data):
    response = client.post("/api/control-tuning/preview", json=data)
    assert response.status_code == 200, response.text
    return response.json()


def propose(client, data):
    simulated = preview(client, data)
    request = {**simulated["request"], "preview_sha256": simulated["preview_sha256"]}
    response = client.post("/api/control-tuning/draft", json=request)
    assert response.status_code == 201, response.text
    return response.json(), request


def store_for(client):
    user = client.get("/api/auth/me").json()
    return client.app.state.hub.store(user["org_id"]), user


def test_amount_search_drafts_only_and_independent_activation_preserves_replay(
    workspace,
):
    client, *_ = workspace
    parent, _, reviewer = setup(client)
    store, user = store_for(client)
    alert_response = client.get("/api/alerts")
    assert alert_response.status_code == 200
    before_alerts = alert_response.json()
    result, request = propose(client, body(parent))
    pinned = result["receipt"]["preview"]
    assert pinned["before"]["match_count"] == 2
    assert pinned["selected"]["threshold"] == "200"
    assert pinned["selected"]["match_count"] == 1
    assert len(pinned["removed_match_ids"]) == 1 and not pinned["added_match_ids"]
    assert client.get("/api/alerts").json() == before_alerts
    draft = result["control"]
    assert draft["status"] == "draft" and draft["replaces_id"] == parent["id"]
    assert draft["created_by"] == user["id"]
    assert client.get("/api/rules/" + parent["id"]).json()["status"] == "active"
    denied = client.post(
        "/api/rules/" + draft["id"] + "/actions",
        json={
            "action": "approve",
            "notes": "Attempting to approve my own tuning proposal.",
        },
    )
    assert denied.status_code == 403
    activated = approve(client, reviewer, draft)
    assert activated["threshold"] == "200" and activated["status"] == "active"
    assert client.get("/api/rules/" + parent["id"]).json()["status"] == "superseded"
    replayed = client.post("/api/control-tuning/draft", json=request).json()
    assert replayed["replayed"] and replayed["control"]["id"] == draft["id"]
    assert len(Operations(store).list("control_tuning")) == 1
    assert Operations(store).verify_audit()["valid"]


@pytest.mark.parametrize(
    "kind,threshold,candidates",
    [("velocity", "2", ["1", "3"]), ("aggregate", "100", ["200", "500"])],
)
def test_candidate_results_match_production_backtest_with_ties_currency_and_late_rows(
    workspace, kind, threshold, candidates
):
    client, *_ = workspace
    parent, customer, _ = setup(client, kind, threshold)
    stamp = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    for index, currency in enumerate(("USD", "EUR", "USD")):
        response = client.post(
            "/api/monitor/transactions",
            json=txn(
                customer,
                "late-" + str(index),
                currency=currency,
                amount="75",
                occurred_at=stamp,
            ),
        )
        assert response.status_code == 201, response.text
    simulated = preview(client, body(parent, candidate_thresholds=candidates))
    for candidate in simulated["candidates"]:
        data = tuning.configuration(parent).model_copy(
            update={"threshold": Decimal(candidate["threshold"])}
        )
        store, user = store_for(client)
        manual = Operations(store).save_rule(data, user, parent["id"])
        checked = Operations(store).backtest(manual["id"])
        assert set(candidate["match_transaction_ids"]) == {
            item["transaction_id"] for item in checked["matches"]
        }
    assert simulated["tested"] == 6


@pytest.mark.parametrize("change", ["transaction", "customer", "policy", "parent"])
def test_stale_preview_never_creates_a_draft(workspace, change):
    client, *_ = workspace
    parent, customer, _ = setup(client)
    data = body(parent)
    checked = preview(client, data)
    store, user = store_for(client)
    if change == "transaction":
        client.post(
            "/api/monitor/transactions",
            json=txn(customer, "new-transaction", amount="500"),
        )
    elif change == "customer":
        Operations(store).save(
            "customer",
            {**customer, "notes": "Updated customer context after simulation."},
            user["id"],
            customer["id"],
        )
    elif change == "policy":
        with store.connect() as db:
            db.execute(
                "UPDATE policies SET content=content || ' Changed content.' WHERE id=?",
                (parent["policy_id"],),
            )
    else:
        Operations(store).rule_action(
            parent["id"],
            RuleAction(
                action="disable", notes="Disabled after reviewing policy context."
            ),
            user,
        )
    response = client.post(
        "/api/control-tuning/draft",
        json={**data, "preview_sha256": checked["preview_sha256"]},
    )
    assert response.status_code == 409, response.text
    assert len(client.get("/api/rules").json()) == 1
    assert Operations(store).list("control_tuning") == []


def test_changed_evidence_at_approval_preserves_draft_and_parent(workspace):
    client, *_ = workspace
    parent, customer, reviewer = setup(client)
    result, _ = propose(client, body(parent))
    client.post(
        "/api/monitor/transactions",
        json=txn(customer, "arrived-before-review", amount="500"),
    )
    with acting_as(client, reviewer):
        response = client.post(
            "/api/rules/" + result["control"]["id"] + "/actions",
            json={
                "action": "approve",
                "notes": "Attempting review after new transaction evidence.",
            },
        )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "tuning_evidence_changed"
    assert client.get("/api/rules/" + parent["id"]).json()["status"] == "active"
    assert (
        client.get("/api/rules/" + result["control"]["id"]).json()["status"] == "draft"
    )


def test_tuning_draft_tampering_and_audit_failure_roll_back(workspace, monkeypatch):
    client, *_ = workspace
    parent, _, reviewer = setup(client)
    store, _ = store_for(client)
    data = body(parent)
    checked = preview(client, data)

    def fail(*_args, **_kwargs):
        raise RuntimeError("Injected audit failure")

    with monkeypatch.context() as patch:
        patch.setattr(tuning, "audit", fail)
        with pytest.raises(RuntimeError, match="Injected"):
            client.post(
                "/api/control-tuning/draft",
                json={**data, "preview_sha256": checked["preview_sha256"]},
            )
    assert len(client.get("/api/rules").json()) == 1
    assert Operations(store).list("control_tuning") == []
    result, _ = propose(client, data)
    altered = {**result["control"], "threshold": "999"}
    with store.connect() as db:
        db.execute(
            "UPDATE records SET payload=? WHERE id=?",
            (canonical(altered), altered["id"]),
        )
    with acting_as(client, reviewer):
        response = client.post(
            "/api/rules/" + altered["id"] + "/actions",
            json={
                "action": "approve",
                "notes": "Reviewing a tampered simulation configuration.",
            },
        )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "tuning_draft_changed"


def test_concurrent_submissions_create_one_draft_and_one_replay(workspace):
    client, *_ = workspace
    parent, _, _ = setup(client)
    data = body(parent)
    checked = preview(client, data)
    request = tuning.DraftInput(**data, preview_sha256=checked["preview_sha256"])
    store, user = store_for(client)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: tuning.draft(store, request, user), range(2)))
    assert sorted(item["replayed"] for item in results) == [False, True]
    assert len({item["control"]["id"] for item in results}) == 1
    assert len(Operations(store).list("rule")) == 2


def test_concurrent_independent_approvals_have_one_winner(workspace):
    client, *_ = workspace
    parent, _, reviewer = setup(client)
    result, _ = propose(client, body(parent))
    store, _ = store_for(client)

    def activate(_):
        try:
            return Operations(store).rule_action(
                result["control"]["id"],
                RuleAction(
                    action="approve",
                    notes="Independently reviewed pinned tuning comparison.",
                ),
                reviewer["user"],
            )["status"]
        except HTTPException as error:
            return error.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(activate, range(2)))
    assert results.count("active") == 1 and results.count(409) == 1


def test_editing_a_tuning_draft_still_replaces_the_active_ancestor(workspace):
    client, *_ = workspace
    parent, _, reviewer = setup(client)
    proposed, _ = propose(client, body(parent))
    data = tuning.configuration(proposed["control"]).model_dump(mode="json")
    data["threshold"] = "225"
    edited = client.put("/api/rules/" + proposed["control"]["id"], json=data)
    assert edited.status_code == 201, edited.text
    assert edited.json()["replaces_id"] == parent["id"]
    assert edited.json()["edited_draft_id"] == proposed["control"]["id"]
    assert "tuning_receipt_id" not in edited.json()
    # This is an explicit manual edit; the old simulation is not misattributed.
    assert approve(client, reviewer, edited.json())["status"] == "active"
    assert client.get("/api/rules/" + parent["id"]).json()["status"] == "superseded"
    assert (
        len(
            [
                item
                for item in client.get("/api/rules").json()
                if item["status"] == "active"
            ]
        )
        == 1
    )
    with acting_as(client, reviewer):
        refused = client.post(
            "/api/rules/" + proposed["control"]["id"] + "/actions",
            json={
                "action": "approve",
                "notes": "A sibling draft already replaced the active ancestor.",
            },
        )
    assert refused.status_code == 409


def test_cyclic_replacement_history_cannot_create_another_draft(workspace):
    client, *_ = workspace
    parent, _, _ = setup(client)
    proposed, _ = propose(client, body(parent))
    value = proposed["control"]
    store, _ = store_for(client)
    value["replaces_id"] = value["id"]
    with store.connect() as db:
        db.execute(
            "UPDATE records SET payload=? WHERE id=?", (canonical(value), value["id"])
        )
    response = client.put(
        "/api/rules/" + value["id"],
        json=tuning.configuration(value).model_dump(mode="json"),
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "control_lineage"


def test_indexed_transaction_disagreement_is_not_a_valid_simulation(workspace):
    client, *_ = workspace
    parent, _, _ = setup(client)
    store, _ = store_for(client)
    with store.connect() as db:
        db.execute("UPDATE transactions SET amount_minor=amount_minor+1")
    response = client.post("/api/control-tuning/preview", json=body(parent))
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "tuning_evidence_invalid"


def test_cross_workspace_receipt_and_parent_are_not_disclosed(workspace):
    client, *_ = workspace
    parent, _, _ = setup(client)
    result, _ = propose(client, body(parent))
    other = client.post(
        "/api/auth/workspaces", json={"name": "Other tuning tenant"}
    ).json()["id"]
    assert client.post(f"/api/auth/workspaces/{other}/switch").status_code == 200
    assert (
        client.get("/api/control-tuning/" + result["receipt"]["id"]).status_code == 404
    )
    assert (
        client.post("/api/control-tuning/preview", json=body(parent)).status_code == 404
    )




@pytest.mark.parametrize(
    "changes",
    [
        {"candidate_thresholds": ["NaN"]},
        {"candidate_thresholds": ["Infinity"]},
        {"candidate_thresholds": ["1.001"]},
        {"candidate_thresholds": ["200", "200.0"]},
        {"candidate_thresholds": ["100"]},
        {"target_match_count": True},
        {"candidate_thresholds": ["200"] * 9},
        {"status": "active"},
    ],
)
def test_invalid_searches_cannot_inject_authority_or_unbounded_numbers(
    workspace, changes
):
    client, *_ = workspace
    parent, _, _ = setup(client)
    response = client.post("/api/control-tuning/preview", json=body(parent, **changes))
    assert response.status_code == 422, response.text


def test_signed_sponsor_pack_retains_before_after_and_request_provenance(
    workspace, tmp_path
):
    from test_evidence import setup_pack, unpack
    from verify_evidence_pack import verify_pack

    client, _, manager, org = setup_pack(workspace, tmp_path)
    parent, _, _ = setup(client)
    result, _ = propose(client, body(parent))
    response = client.get("/api/evidence/sponsor-pack")
    assert response.status_code == 200, response.text
    assert verify_pack(response.content, manager.status(org)["fingerprint"])["valid"]
    files = unpack(response.content)
    data = json.loads(files["evidence.json"])
    receipt = data["records"]["control_tuning"][0]
    assert receipt["id"] == result["receipt"]["id"]
    assert receipt["preview"]["before"]["match_count"] == 2
    assert receipt["preview"]["selected"]["match_count"] == 1
    assert receipt["preview"]["request"]["rationale"] == body(parent)["rationale"]
    (tmp_path / "tuning-report.pdf").write_bytes(files["report.pdf"])


def test_encrypted_restore_preserves_proposal_and_independent_review(tmp_path):
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
        parent, _, _ = setup(client)
        result, _ = propose(client, body(parent))
    create_snapshot(settings, tmp_path / "snapshot")
    from recovery_helpers import guard_arguments

    restore_snapshot(
        tmp_path / "snapshot",
        tmp_path / "restored",
        settings,
        **guard_arguments(settings, tmp_path),
    )
    recovered = settings.model_copy(
        update={"database_path": tmp_path / "restored" / "workspace.db"}
    )
    with TestClient(create_app(recovered, start_worker=False)) as client:
        login = client.post(
            "/api/auth/login",
            json={
                "email": "reviewer@example.invalid",
                "password": "Test-only-password-2026",
            },
        )
        assert login.status_code == 200, login.text
        client.headers["X-CSRF-Token"] = login.json()["csrf"]
        retained = client.get("/api/control-tuning/" + result["receipt"]["id"])
        assert retained.status_code == 200
        assert retained.json()["receipt"] == result["receipt"]
        response = client.post(
            "/api/rules/" + result["control"]["id"] + "/actions",
            json={
                "action": "approve",
                "notes": "Independently reviewed recovered simulation and pinned evidence.",
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "active"


def test_empty_unsupported_and_fractional_count_searches_are_refused(workspace):
    client, *_ = workspace
    reviewer = member(client)
    policy = add_policy(client)
    parent = approve(client, reviewer, rule(client, policy))
    assert (
        client.post("/api/control-tuning/preview", json=body(parent)).status_code == 422
    )
    unsupported = approve(
        client, reviewer, rule(client, policy, kind="corridor", countries=["GB"])
    )
    assert (
        client.post("/api/control-tuning/preview", json=body(unsupported)).status_code
        == 422
    )
    draft = rule(client, policy)
    assert (
        client.post("/api/control-tuning/preview", json=body(draft)).status_code == 409
    )
    customer = add_customer(client)
    client.post("/api/monitor/transactions", json=txn(customer))
    velocity = approve(
        client, reviewer, rule(client, policy, kind="velocity", threshold="2")
    )
    assert (
        client.post(
            "/api/control-tuning/preview",
            json=body(velocity, candidate_thresholds=["2.5"]),
        ).status_code
        == 422
    )


def test_byte_and_rolling_work_bounds_fail_without_sampling(workspace, monkeypatch):
    client, *_ = workspace
    parent, _, reviewer = setup(client)
    with monkeypatch.context() as patch:
        patch.setattr(tuning, "MAX_INPUT_BYTES", 1)
        assert (
            client.post("/api/control-tuning/preview", json=body(parent)).status_code
            == 422
        )
    velocity = approve(
        client,
        reviewer,
        rule(client, {"id": parent["policy_id"]}, kind="velocity", threshold="2"),
    )
    monkeypatch.setattr(tuning, "MAX_ROLLING_WORK", 1)
    response = client.post(
        "/api/control-tuning/preview", json=body(velocity, candidate_thresholds=["3"])
    )
    assert response.status_code == 422
    store, _ = store_for(client)
    assert Operations(store).list("control_tuning") == []


def test_capacity_and_roles_fail_without_partial_drafts(workspace, monkeypatch):
    client, *_ = workspace
    parent, _, _ = setup(client)
    data = body(parent)
    auditor = member(client, "auditor")
    with acting_as(client, auditor):
        assert client.post("/api/control-tuning/preview", json=data).status_code == 403
    with monkeypatch.context() as patch:
        patch.setattr(tuning, "MAX_TRANSACTIONS", 2)
        assert client.post("/api/control-tuning/preview", json=data).status_code == 422
    checked = preview(client, data)
    monkeypatch.setattr(tuning, "MAX_RECEIPTS", 0)
    assert (
        client.post(
            "/api/control-tuning/draft",
            json={**data, "preview_sha256": checked["preview_sha256"]},
        ).status_code
        == 422
    )
    store, _ = store_for(client)
    assert Operations(store).list("control_tuning") == []
