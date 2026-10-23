import json
from datetime import datetime, timedelta, timezone

import pytest

import deletion
from operations import canonical, uid
from store import now
from test_product import acting_as, add_customer, member, txn
from test_retention import REVIEW, draft


def approved(client):
    reviewer = member(client)
    policy = draft(client, customer_days=1, resolved_case_days=1, terminal_job_days=1)
    with acting_as(client, reviewer):
        response = client.post(
            f"/api/retention/policies/{policy['id']}/approve", json=REVIEW
        )
        assert response.status_code == 200
    return policy


def store_for(client):
    identity = client.get("/api/auth/me").json()
    return client.app.state.hub.store(identity["org_id"]), identity["org_id"]


def preview(client, customer):
    response = client.post(
        "/api/retention/deletion-preview", json={"customer_id": customer["id"]}
    )
    assert response.status_code == 200, response.text
    return response.json()


def codes(value):
    return {item["code"] for item in value["blockers"]}


def test_preview_is_readonly_exact_and_bound_to_customer_policy_rows(workspace):
    client, *_ = workspace
    policy = approved(client)
    customer = add_customer(client)
    other = add_customer(client, reference="OTHER", name="Unrelated fictional company")
    assert (
        client.post("/api/monitor/transactions", json=txn(customer)).status_code == 201
    )
    store, org = store_for(client)
    with store.connect() as db:
        audit_before = db.execute("SELECT count(*) FROM audit_chain").fetchone()[0]
    first = preview(client, customer)
    second = preview(client, customer)
    assert first["inventory_sha256"] == second["inventory_sha256"]
    assert first["policy_id"] == policy["id"] and first["workspace_id"] == org
    assert {item["table"] for item in first["candidates"]} == {
        "records",
        "transactions",
    }
    assert not any(item["record_id"] == other["id"] for item in first["candidates"])
    assert "retention_period_not_elapsed" in codes(first)
    assert "external_copy_reconciliation_required" in codes(first)
    assert not first["execution_available"]
    with store.connect() as db:
        assert (
            db.execute("SELECT count(*) FROM audit_chain").fetchone()[0] == audit_before
        )
        assert db.execute("SELECT count(*) FROM transactions").fetchone()[0] == 1
        row = db.execute(
            "SELECT payload FROM records WHERE id=?", (customer["id"],)
        ).fetchone()
        updated = {**json.loads(row[0]), "notes": "Changed after the preview."}
        db.execute(
            "UPDATE records SET payload=? WHERE id=?",
            (canonical(updated), customer["id"]),
        )
    assert preview(client, customer)["inventory_sha256"] != first["inventory_sha256"]


def test_linked_cases_tasks_alerts_jobs_steps_and_holds_are_inventoried(workspace):
    client, *_ = workspace
    approved(client)
    customer = add_customer(client)
    case = client.post(
        "/api/cases",
        json={
            "customer_id": customer["id"],
            "title": "Synthetic deletion case",
            "description": "Synthetic relationship inventory.",
        },
    ).json()
    assert (
        client.post(
            f"/api/cases/{case['id']}/actions",
            json={"action": "task", "notes": "Complete the fictional review task."},
        ).status_code
        == 200
    )
    job = client.post(
        "/api/agents/jobs", json={"kind": "investigation", "target_id": case["id"]}
    ).json()
    store, _ = store_for(client)
    client.app.state.engine.step(
        store, job["id"], "test_retained_step", {"customer": customer, "case": case}
    )
    with store.connect() as db:
        db.execute(
            "INSERT INTO alerts VALUES (?,?,?,?,?)",
            (
                "inventory-alert",
                "inventory-dedupe",
                case["id"],
                now(),
                canonical({"case_id": case["id"]}),
            ),
        )
    hold = client.post(
        "/api/retention/holds",
        json={
            "scope": "case",
            "target_id": case["id"],
            "reason": "Preserve the fictional linked case.",
            "authority_reference": "TEST-INVENTORY",
        },
    ).json()
    assert (
        client.post(
            f"/api/retention/holds/{hold['id']}/request-release", json=REVIEW
        ).status_code
        == 200
    )
    value = preview(client, customer)
    assert {"open_case", "open_task", "nonterminal_agent_run", "legal_hold"} <= codes(
        value
    )
    assert {"records", "alerts", "jobs", "job_steps"} <= {
        item["table"] for item in value["candidates"]
    }
    assert value["blocking_holds"][0]["status"] == "release_requested"
    assert {"case", "case_note", "task", "customer"} <= {
        item["kind"] for item in value["candidates"]
    }


def test_no_policy_and_workspace_customer_holds_are_visible(workspace):
    client, *_ = workspace
    customer = add_customer(client)
    for scope in ("workspace", "customer"):
        assert (
            client.post(
                "/api/retention/holds",
                json={
                    "scope": scope,
                    "target_id": customer["id"] if scope == "customer" else "",
                    "reason": "Preserve the synthetic customer.",
                    "authority_reference": "TEST-HOLD",
                },
            ).status_code
            == 201
        )
    value = preview(client, customer)
    assert "approved_retention_policy_required" in codes(value)
    assert len(value["blocking_holds"]) == 2
    assert all(
        item["kind"] == "retention_hold" for item in value["retained_governance"]
    )


def test_shared_receipts_free_text_and_legacy_assessments_are_not_deletion_authority(
    workspace,
):
    client, *_ = workspace
    approved(client)
    customer = add_customer(client, name="Fictional shared reference marker")
    store, _ = store_for(client)
    with store.connect() as db:
        for kind in ("adapter_import", "backtest", "future_record_kind"):
            value = {
                "id": uid(),
                "summary": f"Shared context for {customer['name']}",
                "objects": [{"customer_id": customer["id"]}],
            }
            db.execute(
                "INSERT INTO records VALUES (?,?,?,?,?)",
                (kind, value["id"], now(), now(), canonical(value)),
            )
        db.execute(
            "INSERT INTO decisions VALUES (?,?,?,?)",
            (
                "legacy-assessment",
                "legacy-transaction",
                now(),
                canonical({"transaction": {"sender": customer["name"]}}),
            ),
        )
    value = preview(client, customer)
    assert "unresolved_shared_or_text_references" in codes(value)
    assert {item["kind"] for item in value["unresolved_references"]} == {
        "adapter_import",
        "backtest",
        "future_record_kind",
        "decisions",
    }
    assert len(value["candidates"]) == 1
    assert "may contain customer names" in value["retained_audit"]["scope"]


def test_preview_age_uses_latest_record_activity_not_customer_creation_only(workspace):
    client, *_ = workspace
    approved(client)
    customer = add_customer(client)
    store, org = store_for(client)
    old = (datetime.now(timezone.utc) - timedelta(days=20)).isoformat()
    with store.connect() as db:
        value = {**customer, "created_at": old, "updated_at": old}
        db.execute(
            "UPDATE records SET created_at=?,updated_at=?,payload=? WHERE id=?",
            (old, old, canonical(value), customer["id"]),
        )
    first = preview(client, customer)
    assert "retention_period_not_elapsed" not in codes(first)
    assert (
        client.post(
            "/api/monitor/transactions", json=txn(customer, occurred_at=old)
        ).status_code
        == 201
    )
    second = preview(client, customer)
    assert "retention_period_not_elapsed" in codes(second)
    assert second["inventory_sha256"] != first["inventory_sha256"]
    with store.connect() as db:
        future = deletion.plan(
            db,
            org,
            customer["id"],
            current=datetime.now(timezone.utc) + timedelta(days=3),
        )
    assert "retention_period_not_elapsed" not in codes(future)
    assert future["inventory_sha256"] == second["inventory_sha256"]


@pytest.mark.parametrize(
    "fault",
    [
        "row_bound",
        "byte_bound",
        "work_bound",
        "unknown_table",
        "invalid_json",
        "naive_timestamp",
        "date_overflow",
    ],
)
def test_preview_refuses_partial_unknown_or_invalid_storage(
    workspace, monkeypatch, fault
):
    client, *_ = workspace
    approved(client)
    customer = add_customer(client)
    store, _ = store_for(client)
    if fault == "row_bound":
        monkeypatch.setattr(deletion, "MAX_ROWS", 1)
    elif fault == "byte_bound":
        monkeypatch.setattr(deletion, "MAX_BYTES", 10)
    elif fault == "work_bound":
        monkeypatch.setattr(deletion, "MAX_REFERENCE_WORK", 1)
    else:
        with store.connect() as db:
            if fault == "unknown_table":
                db.execute("CREATE TABLE unclassified_copy(id TEXT,private_data TEXT)")
            elif fault == "invalid_json":
                db.execute(
                    "INSERT INTO events VALUES (?,?,?,?)",
                    (uid(), now(), "bad-record", "not-json"),
                )
            else:
                value = {
                    **customer,
                    "updated_at": "9999-12-31T23:59:59+00:00"
                    if fault == "date_overflow"
                    else "2026-10-20T00:00:00",
                }
                db.execute(
                    "UPDATE records SET payload=? WHERE id=?",
                    (canonical(value), customer["id"]),
                )
    response = client.post(
        "/api/retention/deletion-preview", json={"customer_id": customer["id"]}
    )
    assert response.status_code == 422, response.text


def test_preview_role_tenant_and_csrf_boundaries(workspace):
    client, *_ = workspace
    customer = add_customer(client)
    analyst, auditor = member(client, "analyst"), member(client, "auditor")
    with acting_as(client, analyst):
        assert (
            client.post(
                "/api/retention/deletion-preview", json={"customer_id": customer["id"]}
            ).status_code
            == 403
        )
    with acting_as(client, auditor):
        assert (
            client.get(
                f"/api/retention/deletion-preview?customer_id={customer['id']}"
            ).status_code
            == 200
        )
        # Auditor sessions have a blanket read-only mutation gate, even for a
        # semantically read-only POST preview. The GET endpoint handles access.
        assert (
            client.post(
                "/api/retention/deletion-preview", json={"customer_id": customer["id"]}
            ).status_code
            == 403
        )
    csrf = client.headers.pop("X-CSRF-Token")
    assert (
        client.post(
            "/api/retention/deletion-preview", json={"customer_id": customer["id"]}
        ).status_code
        == 403
    )
    client.headers["X-CSRF-Token"] = csrf
    other = client.post(
        "/api/auth/workspaces", json={"name": "Other inventory tenant"}
    ).json()["id"]
    assert client.post(f"/api/auth/workspaces/{other}/switch").status_code == 200
    assert (
        client.post(
            "/api/retention/deletion-preview", json={"customer_id": customer["id"]}
        ).status_code
        == 404
    )


def test_preview_hash_changes_when_hold_or_policy_changes(workspace):
    client, *_ = workspace
    policy = approved(client)
    customer = add_customer(client)
    first = preview(client, customer)
    assert (
        client.post(
            "/api/retention/holds",
            json={
                "scope": "workspace",
                "reason": "Preserve synthetic deletion context.",
                "authority_reference": "PREVIEW-HASH",
            },
        ).status_code
        == 201
    )
    second = preview(client, customer)
    assert second["inventory_sha256"] != first["inventory_sha256"]
    reviewer = member(client, "admin")
    replacement = draft(client, parent_id=policy["id"], customer_days=2)
    with acting_as(client, reviewer):
        assert (
            client.post(
                f"/api/retention/policies/{replacement['id']}/approve", json=REVIEW
            ).status_code
            == 200
        )
    third = preview(client, customer)
    assert third["inventory_sha256"] != second["inventory_sha256"]


def test_conflicting_owned_references_and_missing_resolution_age_block_preview(
    workspace,
):
    client, *_ = workspace
    approved(client)
    customer = add_customer(client)
    store, _ = store_for(client)
    with store.connect() as db:
        case_id = uid()
        value = {
            "id": case_id,
            "customer_id": customer["id"],
            "status": "resolved",
            "created_at": now(),
        }
        db.execute(
            "INSERT INTO records VALUES (?,?,?,?,?)",
            ("case", case_id, now(), now(), canonical(value)),
        )
        value = {
            "id": uid(),
            "case_id": case_id,
            "customer_id": "another-customer",
            "created_at": now(),
        }
        db.execute(
            "INSERT INTO records VALUES (?,?,?,?,?)",
            ("case_evidence", value["id"], now(), now(), canonical(value)),
        )
    assert {
        "inconsistent_customer_reference",
        "resolved_case_timestamp_missing",
    } <= codes(preview(client, customer))


def test_preview_is_one_read_snapshot_even_if_customer_changes_during_inventory(
    workspace, monkeypatch
):
    client, *_ = workspace
    approved(client)
    customer = add_customer(client)
    first = preview(client, customer)
    store, _ = store_for(client)
    original = deletion.read_inventory

    def concurrent_writer(db):
        result = original(db)
        with store.connect() as writer:
            value = {**customer, "notes": "Concurrent writer changed the customer."}
            writer.execute(
                "UPDATE records SET payload=? WHERE id=?",
                (canonical(value), customer["id"]),
            )
        return result

    monkeypatch.setattr(deletion, "read_inventory", concurrent_writer)
    assert preview(client, customer)["inventory_sha256"] == first["inventory_sha256"]
    monkeypatch.setattr(deletion, "read_inventory", original)
    assert preview(client, customer)["inventory_sha256"] != first["inventory_sha256"]


def test_encrypted_customer_preview_uses_selected_driver_and_same_scope(tmp_path):
    from fastapi.testclient import TestClient
    from config import Settings
    from main import create_app
    from test_workflows import authenticate

    settings = Settings(
        _env_file=None,
        database_path=tmp_path / "data" / "workspace.db",
        database_encryption="sqlcipher4",
        security_key_path=tmp_path / "private" / "installation.key",
    )
    with TestClient(create_app(settings, start_worker=False)) as client:
        authenticate(client)
        approved(client)
        customer = add_customer(client)
        value = preview(client, customer)
        assert value["candidates"][0]["record_id"] == customer["id"]
        assert "retention_period_not_elapsed" in codes(value)
        assert not value["execution_available"]
