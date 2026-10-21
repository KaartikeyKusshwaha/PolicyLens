from datetime import datetime, timedelta, timezone

import httpx
import pytest

from auth import digest, password_matches


EMAIL = "owner@example.invalid"
NEW_PASSWORD = "New-private-test-password-2026"


def test_private_reset_is_one_use_revokes_sessions_and_preserves_workspace(workspace):
    client, store, _, _ = workspace
    hub = client.app.state.hub
    original_cookie = httpx.Cookies(client.cookies)
    reset = hub.issue_password_reset(EMAIL)
    with hub.connect() as db:
        stored = db.execute("SELECT token_hash FROM password_resets").fetchone()[0]
    assert stored == digest(reset["token"]) and stored != reset["token"]
    assert (
        client.post(
            "/api/auth/login",
            json={"email": EMAIL, "password": "Test-only-password-2026"},
        ).status_code
        == 200
    )
    data = {"email": EMAIL, "token": reset["token"], "password": NEW_PASSWORD}
    response = client.post("/api/auth/password-reset", json=data)
    assert response.json() == {"password_reset": True, "sessions_revoked": True}
    client.cookies.update(original_cookie)
    assert client.get("/api/auth/me").status_code == 401
    assert client.post("/api/auth/password-reset", json=data).status_code == 403
    assert (
        client.post(
            "/api/auth/login",
            json={"email": EMAIL, "password": "Test-only-password-2026"},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/auth/login", json={"email": EMAIL, "password": NEW_PASSWORD}
        ).status_code
        == 200
    )
    with hub.connect() as db:
        assert db.execute("SELECT count(*) FROM password_resets").fetchone()[0] == 0
        encoded = db.execute(
            "SELECT password FROM users WHERE email=?", (EMAIL,)
        ).fetchone()[0]
    assert encoded != NEW_PASSWORD and password_matches(NEW_PASSWORD, encoded)
    assert store.policies() == []


@pytest.mark.parametrize(
    "failure", ["unknown_token", "wrong_email", "expired", "superseded", "cross_origin"]
)
def test_reset_rejects_invalid_scope_and_keeps_old_login(workspace, failure):
    client, _, _, _ = workspace
    hub = client.app.state.hub
    reset = hub.issue_password_reset(EMAIL)
    data = {"email": EMAIL, "token": reset["token"], "password": NEW_PASSWORD}
    headers = {}
    if failure == "unknown_token":
        data["token"] = "unknown-token-" * 5
    elif failure == "wrong_email":
        data["email"] = "other@example.invalid"
    elif failure == "expired":
        with hub.connect() as db:
            db.execute(
                "UPDATE password_resets SET expires_at=?",
                ((datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(),),
            )
    elif failure == "superseded":
        hub.issue_password_reset(EMAIL)
    else:
        headers["Origin"] = "https://different.example"
    assert (
        client.post("/api/auth/password-reset", json=data, headers=headers).status_code
        == 403
    )
    assert client.get("/api/auth/me").status_code == 200
    assert (
        client.post(
            "/api/auth/login",
            json={"email": EMAIL, "password": "Test-only-password-2026"},
        ).status_code
        == 200
    )


def test_reset_throttle_and_no_public_token_issuance(workspace):
    client, _, _, _ = workspace
    reset = client.app.state.hub.issue_password_reset(EMAIL)
    data = {"email": EMAIL, "token": "invalid-" * 8, "password": NEW_PASSWORD}
    for _ in range(12):
        assert client.post("/api/auth/password-reset", json=data).status_code == 403
    data["token"] = reset["token"]
    assert client.post("/api/auth/password-reset", json=data).status_code == 429
    assert client.post(
        "/api/auth/password-reset/issue", json={"email": EMAIL}
    ).status_code in (404, 405)
