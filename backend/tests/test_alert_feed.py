import pytest

from test_control_tuning import setup
from test_product import acting_as, member
from legacy_access_helpers import key




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
        == 401
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
