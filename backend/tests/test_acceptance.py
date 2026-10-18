import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from test_product import acting_as, approve, execute_job, member, rule

PACK = Path(__file__).resolve().parents[2] / "examples" / "fintech-pilot"


def test_generated_fintech_pack_from_ingestion_to_independent_review(workspace):
    client, _, _, _ = workspace
    policy_input = {
        "title": "SAMPLE cross-border operations policy",
        "topic": "aml",
        "version": "1.0",
        "content": (PACK / "policy.txt").read_text(encoding="utf-8"),
    }
    response = client.post("/api/policies", json=policy_input)
    assert response.status_code == 201, response.text
    policy = response.json()
    assert client.post("/api/sources/ofac/sync").status_code == 200
    customers = {}
    for data in json.loads((PACK / "customers.json").read_text()):
        response = client.post("/api/customers", json=data)
        assert response.status_code == 201, response.text
        customers[data["external_id"]] = response.json()
    reviewer = member(client, "reviewer")
    analyst = member(client, "analyst")
    controls = [
        rule(client, policy, kind="amount", threshold="5000"),
        rule(client, policy, kind="velocity", threshold="3", window_hours=1),
        rule(client, policy, kind="aggregate", threshold="8000"),
        rule(client, policy, kind="kyc"),
    ]
    for control in controls:
        assert (
            client.post(
                "/api/rules/" + control["id"] + "/actions",
                json={
                    "action": "approve",
                    "notes": "Attempting own approval must fail.",
                },
            ).status_code
            == 403
        )
        approve(client, reviewer, control)
    timestamp = datetime.now(timezone.utc)
    transactions = []
    alerts = []
    for scenario in json.loads((PACK / "transactions.json").read_text()):
        customer = customers[scenario.pop("customer_reference")]
        minutes = scenario.pop("minutes_ago")
        data = {
            **scenario,
            "customer_id": customer["id"],
            "occurred_at": (timestamp - timedelta(minutes=minutes)).isoformat(),
        }
        response = client.post("/api/monitor/transactions", json=data)
        assert response.status_code == 201, response.text
        alerts.extend(response.json()["alerts"])
        transactions.append(data)
    assert len(alerts) == 6
    assert len(client.get("/api/monitor/transactions").json()) == 6
    assert len(client.get("/api/cases").json()) == 3
    replay = client.post("/api/monitor/transactions", json=transactions[2])
    assert replay.json()["duplicate"]
    before = sum(case["alert_count"] for case in client.get("/api/cases").json())
    simulation = client.post("/api/rules/" + controls[2]["id"] + "/backtest")
    assert simulation.status_code == 200, simulation.text
    assert simulation.json()["match_count"] == 1
    assert (
        sum(case["alert_count"] for case in client.get("/api/cases").json()) == before
    )
    case = next(
        c
        for c in client.get("/api/cases").json()
        if c["customer_id"] == customers["SAMPLE-C001"]["id"]
    )
    path = "/api/cases/" + case["id"] + "/actions"
    assert (
        client.post(
            path,
            json={
                "action": "assign",
                "assignee_id": analyst["user"]["id"],
                "notes": "Assign the fictional acceptance investigator.",
            },
        ).status_code
        == 200
    )
    with acting_as(client, analyst):
        assert (
            client.post(
                path,
                json={
                    "action": "start",
                    "notes": "Investigate the supplied fictional payment evidence.",
                },
            ).status_code
            == 200
        )
        assert (
            client.post(
                path,
                json={
                    "action": "task",
                    "notes": "Collect the fictional invoice and identity evidence.",
                },
            ).status_code
            == 200
        )
        assert (
            client.post(
                path,
                json={
                    "action": "resolve",
                    "disposition": "insufficient_evidence",
                    "notes": "The investigator cannot approve their own work.",
                },
            ).status_code
            == 403
        )
    task = client.get("/api/cases/" + case["id"]).json()["tasks"][0]
    assert client.post("/api/tasks/" + task["id"] + "/complete").status_code == 200
    job = client.post(
        "/api/agents/jobs", json={"kind": "investigation", "target_id": case["id"]}
    ).json()
    completed = execute_job(client, job["id"])
    assert completed["state"] == "completed", completed
    assert completed["payload"]["result"]["citations"]
    assert client.get("/api/cases/" + case["id"]).json()["status"] != "resolved"
    with acting_as(client, reviewer):
        assert (
            client.post(
                path,
                json={
                    "action": "resolve",
                    "disposition": "insufficient_evidence",
                    "notes": "Independent test review: insufficient evidence; this is not approval of a real payment.",
                },
            ).status_code
            == 200
        )
    pack = client.get("/api/cases/" + case["id"] + "/export").json()
    assert pack["resolved_by"] == reviewer["user"]["id"]
    assert pack["audit_checkpoint"]["valid"]
    updated = client.put(
        "/api/policies/" + policy["id"],
        json={
            **policy_input,
            "version": "2.0",
            "content": policy_input["content"]
            + "\nSAMPLE revision: record supporting invoice evidence before final review.",
        },
    )
    assert updated.status_code == 200
    change = client.get("/api/policy-changes").json()[0]
    with acting_as(client, reviewer):
        approval = client.post(
            "/api/policy-changes/" + change["id"] + "/actions",
            json={
                "action": "approve",
                "notes": "Approve applicability review for the fictional customer population.",
            },
        )
        assert approval.status_code == 200, approval.text
        assert approval.json()["review_tasks_created"] == 3
