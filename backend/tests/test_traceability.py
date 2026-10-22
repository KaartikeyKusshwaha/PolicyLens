import copy
import io
import json
import zipfile

from operations import canonical
from test_product import (
    add_policy,
    rule,
    member,
    approve,
    acting_as,
    execute_job,
    add_customer,
    txn,
)
from test_workflows import POLICY
import traceability


def analyze(client, policy):
    response = client.post(
        "/api/agents/jobs", json={"kind": "policy_analyst", "target_id": policy["id"]}
    )
    assert response.status_code == 202, response.text
    job = execute_job(client, response.json()["id"])
    assert job["state"] == "completed", job
    return job


def link(client, obligation, control, linked=True):
    return client.put(
        f"/api/traceability/obligations/{obligation['id']}/links",
        json={
            "control_id": control["id"],
            "linked": linked,
            "notes": "Human assessment of this policy-control mapping.",
        },
    )


def test_matrix_does_not_infer_coverage_and_shows_simulations_alerts_evidence(
    workspace,
):
    client, store, _, _ = workspace
    policy = add_policy(client)
    control = rule(client, policy)
    before = client.get("/api/traceability").json()
    assert before["policies_without_current_analysis"][0]["id"] == policy["id"]
    analyze(client, policy)
    obligation = client.get("/api/traceability").json()["obligations"][0]
    assert obligation["citation"]["quote"] in POLICY["content"]
    assert obligation["controls"] == [] and "no_linked_control" in obligation["gaps"]
    assert link(client, obligation, control).status_code == 200
    mapped = client.get("/api/traceability").json()["obligations"][0]
    assert mapped["status"] == "needs_review" and "no_active_control" in mapped["gaps"]
    reviewer = member(client)
    approve(client, reviewer, control)
    customer = add_customer(client)
    client.post("/api/monitor/transactions", json=txn(customer))
    case = client.get("/api/cases").json()[0]
    ops = client.app.state.engine.hub.store(client.get("/api/auth/me").json()["org_id"])
    from operations import Operations

    Operations(ops).save(
        "case_evidence",
        {
            "case_id": case["id"],
            "source": "synthetic-source",
            "proof": "Synthetic retained evidence.",
        },
        "test-actor",
    )
    mapped = client.get("/api/traceability").json()["obligations"][0]
    assert mapped["status"] == "linked_active_control"
    assert "active_control_without_recorded_simulation" in mapped["gaps"]
    assert mapped["controls"][0]["alert_count"] == 1
    assert (
        mapped["controls"][0]["evidence"][0]["proof"] == "Synthetic retained evidence."
    )
    assert client.post(f"/api/rules/{control['id']}/backtest").status_code == 200
    mapped = client.get("/api/traceability").json()["obligations"][0]
    assert mapped["gaps"] == []
    assert mapped["controls"][0]["latest_simulation"]["tested"] == 1
    assert link(client, obligation, control, False).status_code == 200
    assert client.get("/api/traceability").json()["obligations"][0]["controls"] == []
    with store.connect() as db:
        assert (
            db.execute(
                "SELECT count(*) FROM audit_chain WHERE action='obligation_control_unlinked'"
            ).fetchone()[0]
            == 1
        )


def test_new_analysis_never_silently_reuses_previous_mapping(workspace):
    client, store, _, _ = workspace
    policy = add_policy(client)
    control = rule(client, policy)
    first = analyze(client, policy)
    # Two obligations from the same completed analysis must both be displayed.
    payload = first["payload"]
    extra = copy.deepcopy(payload["result"]["obligations"][0])
    extra["obligation"] = "A second independently reviewed synthetic obligation."
    payload["result"]["obligations"].append(extra)
    with store.connect() as db:
        db.execute(
            "UPDATE jobs SET payload=? WHERE id=?", (canonical(payload), first["id"])
        )
    old = client.get("/api/traceability").json()["obligations"]
    assert len(old) == 2
    assert link(client, old[0], control).status_code == 200
    second = analyze(client, policy)
    current = client.get("/api/traceability").json()["obligations"]
    assert len(current) == 1 and current[0]["analysis_job_id"] == second["id"]
    assert current[0]["controls"] == []
    assert link(client, old[0], control).status_code == 404


def test_policy_update_flags_historical_mapping_and_refuses_wrong_policy_links(
    workspace,
):
    client, _, _, _ = workspace
    policy = add_policy(client)
    control = rule(client, policy)
    analyze(client, policy)
    obligation = client.get("/api/traceability").json()["obligations"][0]
    other = add_policy(client)
    assert link(client, obligation, rule(client, other)).status_code == 409
    assert link(client, obligation, control).status_code == 200
    assert (
        client.put(
            f"/api/policies/{policy['id']}", json={**POLICY, "version": "2.0"}
        ).status_code
        == 200
    )
    matrix = client.get("/api/traceability").json()
    assert "historical_policy_version" in matrix["obligations"][0]["gaps"]
    assert matrix["obligations"][0]["status"] == "needs_review"
    assert any(
        p["id"] == policy["id"] for p in matrix["policies_without_current_analysis"]
    )
    assert link(client, obligation, control).status_code == 409
    assert link(client, obligation, control, False).status_code == 200


def test_auditor_and_other_tenant_cannot_modify_original_mapping(workspace):
    client, _, _, _ = workspace
    policy = add_policy(client)
    control = rule(client, policy)
    analyze(client, policy)
    obligation = client.get("/api/traceability").json()["obligations"][0]
    auditor = member(client, "auditor")
    with acting_as(client, auditor):
        assert client.get("/api/traceability").status_code == 200
        assert link(client, obligation, control).status_code == 403
    other = client.post(
        "/api/auth/workspaces", json={"name": "Other trace tenant"}
    ).json()["id"]
    assert client.post(f"/api/auth/workspaces/{other}/switch").status_code == 200
    assert client.get("/api/traceability").json()["obligations"] == []
    assert link(client, obligation, control).status_code == 404


def test_human_mappings_and_simulations_are_in_signed_evidence_pack(
    workspace, tmp_path
):
    client, _, _, settings = workspace
    settings.checkpoint_directory = tmp_path.parent / (tmp_path.name + "-anchors")
    policy = add_policy(client)
    control = rule(client, policy)
    analyze(client, policy)
    obligation = client.get("/api/traceability").json()["obligations"][0]
    assert link(client, obligation, control).status_code == 200
    assert client.post(f"/api/rules/{control['id']}/backtest").status_code == 200
    response = client.get("/api/evidence/sponsor-pack")
    assert response.status_code == 200, response.text
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        data = json.loads(archive.read("evidence.json"))
    assert data["records"]["traceability_link"][0]["obligation_id"] == obligation["id"]
    assert data["records"]["backtest"][0]["rule_id"] == control["id"]


def test_partial_analysis_and_source_row_bound_remain_explicit(workspace, monkeypatch):
    client, store, _, _ = workspace
    policy = add_policy(client)
    job = analyze(client, policy)
    payload = job["payload"]
    payload["result"]["coverage"] = {"complete": False, "included_characters": 50}
    with store.connect() as db:
        db.execute(
            "UPDATE jobs SET payload=? WHERE id=?", (canonical(payload), job["id"])
        )
    result = client.get("/api/traceability").json()
    assert "partial_policy_analysis" in result["obligations"][0]["gaps"]
    monkeypatch.setattr(traceability, "MAX_ROWS", 0)
    response = client.get("/api/traceability")
    assert (
        response.status_code == 413
        and response.json()["detail"]["code"] == "traceability_limit"
    )
