import pytest

from legacy_access_helpers import key


@pytest.mark.parametrize("method,path", [
    ("GET", "/api/agent-tools"),
    ("GET", "/api/agent-keys"),
    ("POST", "/api/toolkit/call/search_policy"),
    ("GET", "/api/adapters"),
    ("POST", "/api/adapters/marble/preview"),
    ("POST", "/api/control-code/preview"),
    ("GET", "/api/evidence/scorecards/reference"),
    ("GET", "/api/customers/nonexistent/graph"),
])
def test_removed_product_endpoints_are_not_registered(workspace, method, path):
    client, *_ = workspace
    assert client.request(method, path).status_code in (404, 405)
    assert path not in client.get("/openapi.json").json().get("paths", {})


def test_existing_agent_credentials_cannot_access_remaining_product(workspace):
    client, *_ = workspace
    credential = key(client)
    assert client.get("/api/policies", headers={"Authorization": "Bearer " + credential["token"]}).status_code == 401
    assert client.get("/api/policies").status_code == 200
