import pytest

from operations import Operations
from test_adapters import example, imported
from test_control_tuning import setup
from test_product import acting_as, member
from test_toolkit import key


def test_alert_feed_pages_native_and_external_records_without_losing_origin(workspace):
    client, *_ = workspace
    _, customer, _ = setup(client)
    user = client.get("/api/auth/me").json()
    store = client.app.state.hub.store(user["org_id"])
    external = imported(client, example(customer["id"]))
    assert external.status_code == 201, external.text
    first = client.get("/api/alerts?limit=2&offset=0")
    assert first.status_code == 200
    assert first.json()["has_more"] and first.json()["limit"] == 2
    second = client.get("/api/alerts?limit=2&offset=2").json()
    rows = first.json()["alerts"] + second["alerts"]
    assert len(rows) == len({row["id"] for row in rows}) == 3
    assert any(
        row.get("origin") == "external_engine"
        and row["external_source"]["provider"] == "marble"
        for row in rows
    )
    assert any(row.get("origin") != "external_engine" for row in rows)
    assert not second["has_more"]
    assert client.get("/api/alerts?offset=100000").json()["alerts"] == []
    assert Operations(store).verify_audit()["valid"]


def test_alert_feed_is_tenant_local_read_only_and_not_a_bearer_route(workspace):
    client, *_ = workspace
    setup(client)
    auditor = member(client, "auditor")
    with acting_as(client, auditor):
        assert client.get("/api/alerts").status_code == 200
        assert client.post("/api/alerts", json={"status": "approved"}).status_code in (
            403,
            405,
        )
    credential = key(client, scopes=["list_alerts"])
    assert (
        client.get(
            "/api/alerts", headers={"Authorization": "Bearer " + credential["token"]}
        ).status_code
        == 403
    )
    other = client.post(
        "/api/auth/workspaces", json={"name": "Isolated alert feed"}
    ).json()["id"]
    assert client.post(f"/api/auth/workspaces/{other}/switch").status_code == 200
    assert client.get("/api/alerts").json()["alerts"] == []


@pytest.mark.parametrize(
    "query", ["limit=0", "limit=201", "offset=-1", "offset=100001"]
)
def test_alert_feed_refuses_unbounded_or_invalid_pages(workspace, query):
    client, *_ = workspace
    assert client.get("/api/alerts?" + query).status_code == 422
