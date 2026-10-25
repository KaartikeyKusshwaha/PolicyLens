from test_product import add_customer


def registration(email="new-owner@example.invalid", **overrides):
    return {
        "email": email,
        "password": "Fictional-account-password-2026",
        "name": "New Owner",
        "workspace": "Bluewater Compliance",
        **overrides,
    }


def test_signup_creates_named_isolated_workspace_and_cannot_claim_existing_team(
    workspace,
):
    client, _, _, _ = workspace
    original = client.get("/api/auth/me").json()
    customer = add_customer(client)
    client.post("/api/auth/logout")
    result = client.post("/api/auth/register", json=registration())
    assert result.status_code == 201, result.text
    identity = result.json()
    client.headers["X-CSRF-Token"] = identity["csrf"]
    assert identity["workspace"] == "Bluewater Compliance"
    assert identity["role"] == "admin"
    assert identity["org_id"] != original["org_id"]
    assert client.get("/api/customers").json() == []
    assert client.get("/api/policies").json() == []
    assert client.get("/api/customers/" + customer["id"]).status_code == 404
    assert (
        client.post(
            "/api/auth/workspaces/" + original["org_id"] + "/switch"
        ).status_code
        == 403
    )
    team = client.get("/api/team").json()
    assert len(team) == 1 and team[0]["email"] == identity["email"]
    client.post("/api/auth/logout")
    assert client.post("/api/auth/register", json=registration()).status_code == 409
    result = client.post(
        "/api/auth/login",
        json={k: v for k, v in registration().items() if k in ("email", "password")},
    )
    assert result.status_code == 200 and result.json()["org_id"] == identity["org_id"]


def test_signup_rejects_blank_names_unknown_fields_and_cross_origin(workspace):
    client, _, _, _ = workspace
    assert (
        client.post(
            "/api/auth/register", json=registration(workspace="   ")
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/auth/register", json=registration(role="admin", org_id="existing")
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/auth/register",
            json=registration(),
            headers={"Origin": "https://other.invalid"},
        ).status_code
        == 403
    )
    assert client.get("/api/auth/status").json()["registration"] == "public"


def test_signup_is_rate_limited(workspace):
    client, _, _, _ = workspace
    for _ in range(12):
        assert client.post(
            "/api/auth/register", json=registration(email="owner@example.invalid")
        ).status_code in (201, 409)
    assert (
        client.post(
            "/api/auth/register", json=registration(email="other@example.invalid")
        ).status_code
        == 429
    )


def test_login_returns_to_last_selected_workspace(workspace):
    client, _, _, _ = workspace
    original = client.get("/api/auth/me").json()
    second = client.post(
        "/api/auth/workspaces", json={"name": "Second operating workspace"}
    ).json()
    client.post("/api/auth/workspaces/" + second["id"] + "/switch")
    client.post("/api/auth/logout")
    from test_product import PASSWORD

    identity = client.post(
        "/api/auth/login", json={"email": original["email"], "password": PASSWORD}
    )
    assert identity.status_code == 200
    assert identity.json()["org_id"] == second["id"]
