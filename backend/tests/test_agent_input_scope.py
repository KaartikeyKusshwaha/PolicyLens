from decimal import Decimal

import pytest

from agents import transaction_input_scope
from intelligence import Intelligence
from test_product import add_customer, execute_job, txn
from test_workflows import prepare


def test_sample_arithmetic_is_exact_and_never_combines_currencies():
    summary = transaction_input_scope(
        {
            "transactions": [
                {"amount": "0.10", "currency": "USD"},
                {"amount": "0.20", "currency": "USD"},
                {"amount": "900719925474099.01", "currency": "EUR"},
            ],
            "transaction_scope": "Latest three retained records, not full history.",
        }
    )
    assert summary["record_count"] == 3
    assert summary["totals_by_currency"] == {
        "EUR": "900719925474099.01",
        "USD": "0.30",
    }
    assert summary["scope"] == "Latest three retained records, not full history."
    with pytest.raises(ValueError):
        transaction_input_scope(
            {
                "transactions": [{"amount": "NaN", "currency": "USD"}],
                "transaction_scope": "Invalid retained data.",
            }
        )


def test_scope_pins_final_model_sample_after_context_reduction(workspace, monkeypatch):
    client, _, _, _ = prepare(workspace)
    customer = add_customer(client)
    for index in range(50):
        response = client.post(
            "/api/monitor/transactions",
            json=txn(
                customer,
                reference=f"SAMPLE-{index}",
                amount="0.10",
                currency="USD" if index % 2 else "EUR",
                description="Synthetic bounded-context evidence. " * 23,
            ),
        )
        assert response.status_code == 201, response.text
    captured = {}
    original = Intelligence.complete

    async def complete(provider, schema, context):
        captured["transactions"] = context["transactions"]
        return await original(provider, schema, context)

    monkeypatch.setattr(Intelligence, "complete", complete)
    queued = client.post(
        "/api/agents/jobs", json={"kind": "screening", "target_id": customer["id"]}
    )
    assert queued.status_code == 202, queued.text
    done = execute_job(client, queued.json()["id"])
    assert done["state"] == "completed", done
    steps = {step["step"]: step["output"] for step in done["steps"]}
    assert len(steps["collect_evidence"]["transactions"]) == 50
    assert len(captured["transactions"]) == 10
    scope = done["payload"]["result"]["model_input_scope"]
    assert scope == steps["model_input_scope"]
    assert scope["record_count"] == 10
    assert "Latest 10" in scope["scope"]
    expected = {}
    for row in captured["transactions"]:
        expected[row["currency"]] = expected.get(row["currency"], Decimal(0)) + Decimal(
            row["amount"]
        )
    assert scope["totals_by_currency"] == {
        currency: format(total, "f") for currency, total in expected.items()
    }
    # Later customer activity cannot rewrite the retained model sample.
    assert client.post(
        "/api/monitor/transactions", json=txn(customer, reference="LATER", amount="999")
    ).status_code == 201
    retained = client.get("/api/agents/jobs/" + done["id"]).json()
    assert retained["payload"]["result"]["model_input_scope"] == scope
    assert retained["payload"]["model_attempts"] == 1
