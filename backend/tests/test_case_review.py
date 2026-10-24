from test_product import add_customer, add_policy, approve, member, rule, txn
from test_workflows import prepare


def test_automatic_review_updates_and_export_matches_without_model_or_decisions(
    workspace,
):
    client, store, state, _ = prepare(workspace)
    customer = add_customer(client)
    policy = add_policy(client)
    reviewer = member(client)
    control = rule(client, policy)
    approve(client, reviewer, control)
    first = client.post(
        "/api/monitor/transactions", json=txn(customer, amount="150.10")
    )
    assert first.status_code == 201, first.text
    case_id = first.json()["alerts"][0]["case_id"]
    calls = len(state["calls"])
    pack = client.get("/api/cases/" + case_id).json()
    review = pack["review"]
    assert review["totals_by_currency"] == {"USD": "150.10"}
    assert review["alert_count"] == 1
    assert review["policies"][0]["available"]
    assert review["policies"][0]["excerpt"] == policy["content"][:1200]
    assert review["missing_evidence"]
    second = client.post(
        "/api/monitor/transactions", json=txn(customer, "PAY-002", amount="0.20")
    )
    assert second.status_code == 201, second.text
    latest = client.get("/api/cases/" + case_id).json()
    assert latest["review"]["totals_by_currency"] == {"USD": "150.30"}
    assert latest["review"]["transaction_count"] == 2
    assert latest["status"] == "open"
    exported = client.get("/api/cases/" + case_id + "/export").json()
    assert exported["review"]["totals_by_currency"] == {"USD": "150.30"}
    assert exported["review"]["signals"] == latest["review"]["signals"]
    assert len(state["calls"]) == calls
    with store.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0


def test_review_keeps_currencies_separate_and_discloses_sample_boundary(workspace):
    client, _, _, _ = prepare(workspace)
    customer = add_customer(client)
    case = client.post(
        "/api/cases",
        json={
            "customer_id": customer["id"],
            "title": "Sample boundary review",
            "description": "Review fictional payments for test purposes.",
            "priority": "medium",
        },
    ).json()
    for index in range(201):
        response = client.post(
            "/api/monitor/transactions",
            json=txn(
                customer,
                f"PAY-{index}",
                amount="0.10",
                currency="USD" if index % 2 else "EUR",
            ),
        )
        assert response.status_code == 201, response.text
    review = client.get("/api/cases/" + case["id"]).json()["review"]
    assert review["transaction_count"] == 200
    assert review["total_customer_transactions"] == 201
    assert set(review["totals_by_currency"]) == {"EUR", "USD"}
    assert any("latest 200" in text for text in review["limitations"])
    assert "No sanctions source snapshots" in " ".join(review["missing_evidence"])
