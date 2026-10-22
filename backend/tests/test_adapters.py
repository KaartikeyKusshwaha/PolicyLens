import copy
import io
import json
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor

import pytest

import adapters
from operations import canonical
from privacy import pseudonymize
from test_product import add_customer, member, acting_as


def example(customer_id):
    case_id, decision_id = str(uuid.uuid4()), str(uuid.uuid4())
    return {
        "schema_version": "policylens.marble-import.v1",
        "source_instance": "fictional-marble",
        "cases": {
            "data": [
                {
                    "id": case_id,
                    "inbox": {"id": str(uuid.uuid4())},
                    "name": "Fictional closed upstream investigation",
                    "status": "closed",
                    "outcome": "false_positive",
                    "contributors": [],
                    "tags": [],
                    "review_level": None,
                    "created_at": "2026-10-01T00:00:00Z",
                }
            ]
        },
        "decisions": {
            "data": [
                {
                    "id": decision_id,
                    "case": {"id": case_id},
                    "outcome": "review",
                    "review_status": None,
                    "scenario": {
                        "id": str(uuid.uuid4()),
                        "iteration_id": str(uuid.uuid4()),
                        "version": "1",
                        "custom_private_text": "CUSTOM-FIELD-NOT-FOR-MODEL",
                    },
                    "trigger_object": {
                        "object_id": "PRIVATE-TRIGGER-123",
                        "updated_at": "2026-10-01T00:00:00Z",
                        "arbitrary_private_field": "CUSTOM-FIELD-NOT-FOR-MODEL",
                    },
                    "score": 70,
                    "created_at": "2026-10-01T00:00:00Z",
                }
            ]
        },
        "customer_mappings": [
            {"object_type": "case", "source_id": case_id, "customer_id": customer_id}
        ],
    }


def preview(client, bundle):
    response = client.post("/api/adapters/marble/preview", json={"bundle": bundle})
    assert response.status_code == 200, response.text
    return response.json()


def imported(client, bundle):
    result = preview(client, bundle)
    return client.post(
        "/api/adapters/marble/import",
        json={"bundle": bundle, "preview_sha256": result["preview_sha256"]},
    )


def test_import_creates_open_case_and_alert_with_provenance_not_transaction_or_control(
    workspace, tmp_path
):
    client, store, state, settings = workspace
    customer = add_customer(client)
    bundle = example(customer["id"])
    first = imported(client, bundle)
    assert first.status_code == 201, first.text
    assert not first.json()["replayed"]
    cases = client.get("/api/cases").json()
    assert (
        len(cases) == 1 and cases[0]["status"] == "open" and not cases[0]["disposition"]
    )
    pack = client.get("/api/cases/" + cases[0]["id"]).json()
    assert pack["external_source"]["source_status"] == "closed"
    assert pack["external_source"]["source_outcome"] == "false_positive"
    assert pack["alerts"][0]["origin"] == "external_engine"
    assert pack["alerts"][0]["transaction_id"] is None
    assert "CUSTOM-FIELD-NOT-FOR-MODEL" not in canonical(pack["alerts"][0])
    assert client.get("/api/monitor/transactions").json() == []
    assert client.get("/api/rules").json() == []
    assert not state["calls"]
    assert imported(client, bundle).json()["replayed"]
    assert len(client.get("/api/cases").json()) == 1
    settings.checkpoint_directory = tmp_path.parent / (tmp_path.name + "-anchors")
    response = client.get("/api/evidence/sponsor-pack")
    assert response.status_code == 200
    (tmp_path / "marble-sponsor.zip").write_bytes(response.content)
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        full = json.loads(archive.read("evidence.json"))
    assert len(full["records"]["adapter_object"]) == 2
    assert all(
        item["sha256"] == adapters.digest(item["raw"])
        for item in full["records"]["adapter_object"]
    )
    assert "CUSTOM-FIELD-NOT-FOR-MODEL" in canonical(full["records"]["adapter_object"])
    with store.connect() as db:
        assert (
            db.execute(
                "SELECT count(*) FROM audit_chain WHERE action='external_object_imported'"
            ).fetchone()[0]
            == 2
        )


def test_missing_customer_mapping_and_changed_source_or_preview_fail_without_writes(
    workspace,
):
    client, _, _, _ = workspace
    customer = add_customer(client)
    bundle = example(customer["id"])
    missing = copy.deepcopy(bundle)
    missing["customer_mappings"] = []
    planned = preview(client, missing)
    assert (
        not planned["can_import"]
        and "customer_mapping_required" in planned["objects"][0]["errors"]
    )
    assert imported(client, missing).status_code == 409
    assert client.get("/api/cases").json() == []
    planned = preview(client, bundle)
    altered = copy.deepcopy(bundle)
    altered["source_instance"] = "modified-instance"
    assert (
        client.post(
            "/api/adapters/marble/import",
            json={"bundle": altered, "preview_sha256": planned["preview_sha256"]},
        ).status_code
        == 409
    )
    assert imported(client, bundle).status_code == 201
    changed = copy.deepcopy(bundle)
    changed["decisions"]["data"][0]["score"] = 99
    assert "source_identity_changed" in preview(client, changed)["objects"][1]["errors"]
    assert imported(client, changed).status_code == 409
    assert len(client.get("/api/cases").json()) == 1


def test_approve_decision_without_case_creates_only_source_evidence(workspace):
    client, _, _, _ = workspace
    customer = add_customer(client)
    bundle = example(customer["id"])
    bundle["cases"]["data"] = []
    decision = bundle["decisions"]["data"][0]
    decision["case"] = None
    decision["outcome"] = "approve"
    bundle["customer_mappings"] = [
        {
            "object_type": "decision",
            "source_id": decision["id"],
            "customer_id": customer["id"],
        }
    ]
    response = imported(client, bundle)
    assert response.status_code == 201
    assert response.json()["objects"][0]["local_case_id"] is None
    assert client.get("/api/cases").json() == []
    assert client.get("/api/rules").json() == []


def test_new_decision_cannot_attach_to_locally_resolved_case_without_human_reopen(
    workspace,
):
    client, store, _, _ = workspace
    bundle = example(add_customer(client)["id"])
    assert imported(client, bundle).status_code == 201
    native = client.get("/api/cases").json()[0]
    native["status"] = "resolved"
    with store.connect() as db:
        db.execute(
            "UPDATE records SET payload=? WHERE kind='case' AND id=?",
            (canonical(native), native["id"]),
        )
    next_page = copy.deepcopy(bundle)
    next_page["cases"]["data"] = []
    next_page["customer_mappings"] = []
    next_page["decisions"]["data"][0]["id"] = str(uuid.uuid4())
    assert (
        "local_case_requires_human_reopen"
        in preview(client, next_page)["objects"][0]["errors"]
    )
    assert imported(client, next_page).status_code == 409


def test_case_mapping_cannot_change_customer_or_cross_tenant_and_auditor_cannot_import(
    workspace,
):
    client, _, _, _ = workspace
    customer = add_customer(client)
    bundle = example(customer["id"])
    auditor = member(client, "auditor")
    with acting_as(client, auditor):
        assert client.get("/api/adapters").status_code == 200
        assert (
            client.post(
                "/api/adapters/marble/preview", json={"bundle": bundle}
            ).status_code
            == 403
        )
    second = add_customer(client, "SECOND-CUSTOMER")
    bundle["customer_mappings"].append(
        {
            "object_type": "decision",
            "source_id": bundle["decisions"]["data"][0]["id"],
            "customer_id": second["id"],
        }
    )
    assert (
        "case_customer_mapping_conflict"
        in preview(client, bundle)["objects"][1]["errors"]
    )
    other = client.post(
        "/api/auth/workspaces", json={"name": "Other import workspace"}
    ).json()["id"]
    assert client.post(f"/api/auth/workspaces/{other}/switch").status_code == 200
    assert imported(client, bundle).status_code == 409
    assert client.get("/api/cases").json() == []


@pytest.mark.parametrize(
    "mutation", ["partial", "version", "duplicate", "naive_time", "missing_case"]
)
def test_source_contract_and_pagination_boundaries_are_explicit(workspace, mutation):
    client, _, _, _ = workspace
    bundle = example(add_customer(client)["id"])
    if mutation == "partial":
        bundle["cases"]["pagination"] = {"has_more": True, "next_page_id": "cursor"}
    elif mutation == "version":
        bundle["case_api_version"] = "v0"
    elif mutation == "duplicate":
        bundle["decisions"]["data"].append(
            copy.deepcopy(bundle["decisions"]["data"][0])
        )
    elif mutation == "naive_time":
        bundle["decisions"]["data"][0]["created_at"] = "2026-10-01T00:00:00"
    else:
        bundle["cases"]["data"] = []
        bundle["customer_mappings"] = []
        result = preview(client, bundle)
        assert "referenced_source_case_not_imported" in result["objects"][0]["errors"]
        return
    assert (
        client.post("/api/adapters/marble/preview", json={"bundle": bundle}).status_code
        == 422
    )
    if mutation == "partial":
        bundle["acknowledge_partial_pages"] = True
        assert imported(client, bundle).status_code == 201


def test_batch_failure_rolls_back_case_alert_and_provenance(workspace, monkeypatch):
    client, store, _, _ = workspace
    bundle = example(add_customer(client)["id"])
    planned = preview(client, bundle)
    original = adapters.save_record

    def fail_object(db, kind, value):
        if kind == "adapter_object" and value["object_type"] == "decision":
            raise RuntimeError("Synthetic late import failure.")
        return original(db, kind, value)

    with store.connect() as db:
        before = db.execute("SELECT count(*) FROM audit_chain").fetchone()[0]
    monkeypatch.setattr(adapters, "save_record", fail_object)
    with pytest.raises(RuntimeError):
        client.post(
            "/api/adapters/marble/import",
            json={"bundle": bundle, "preview_sha256": planned["preview_sha256"]},
        )
    assert client.get("/api/cases").json() == []
    with store.connect() as db:
        assert db.execute("SELECT count(*) FROM alerts").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM audit_chain").fetchone()[0] == before


def test_parallel_identical_imports_commit_once(workspace):
    client, store, _, _ = workspace
    bundle = example(add_customer(client)["id"])
    prepared = preview(client, bundle)
    user = client.get("/api/auth/me").json()
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(
                adapters.import_bundle,
                store,
                "marble",
                bundle,
                prepared["preview_sha256"],
                user,
            )
            for _ in range(2)
        ]
        results = [future.result(timeout=15) for future in futures]
    assert sorted(result["replayed"] for result in results) == [False, True]
    assert len(client.get("/api/cases").json()) == 1
    with store.connect() as db:
        assert db.execute("SELECT count(*) FROM alerts").fetchone()[0] == 1
        assert (
            db.execute(
                "SELECT count(*) FROM records WHERE kind='adapter_object'"
            ).fetchone()[0]
            == 2
        )


def test_upstream_cases_remain_separate_from_each_other_and_existing_local_case(
    workspace,
):
    client, _, _, _ = workspace
    customer = add_customer(client)
    local = client.post(
        "/api/cases",
        json={
            "customer_id": customer["id"],
            "title": "Existing local investigation",
            "priority": "low",
            "description": "An existing independent review of this customer.",
        },
    ).json()
    bundle = example(customer["id"])
    other = copy.deepcopy(bundle["cases"]["data"][0])
    other["id"] = str(uuid.uuid4())
    bundle["cases"]["data"].append(other)
    bundle["customer_mappings"].append(
        {"object_type": "case", "source_id": other["id"], "customer_id": customer["id"]}
    )
    assert imported(client, bundle).status_code == 201
    cases = client.get("/api/cases").json()
    assert len(cases) == 3
    assert (
        next(case for case in cases if case["id"] == local["id"])["priority"] == "low"
    )


def test_external_identifier_masking_and_size_bound(workspace, monkeypatch):
    client, _, _, _ = workspace
    bundle = example(add_customer(client)["id"])
    assert imported(client, bundle).status_code == 201
    case = client.get("/api/cases").json()[0]
    pack = client.get("/api/cases/" + case["id"]).json()
    masked = pseudonymize(pack, b"k" * 32, "test-scope")
    assert "PRIVATE-TRIGGER-123" not in canonical(masked)
    assert "Fictional closed upstream investigation" not in canonical(masked)
    monkeypatch.setattr(adapters, "MAX_BYTES", 1)
    assert (
        client.post("/api/adapters/marble/preview", json={"bundle": bundle}).status_code
        == 413
    )
