import pytest

from security import SecretBox

PASSWORD = "Test-only-password-2026"


def legacy_factor(hub, user_id):
    """Model an old encrypted identity DB without restoring the removed feature."""
    secret = SecretBox(hub.settings).encrypt("legacy-test-seed", "mfa:" + user_id)
    with hub.connect() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS account_mfa(
                user_id TEXT PRIMARY KEY, secret TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 0, expires_at TEXT,
                last_counter INTEGER NOT NULL DEFAULT -1,
                recovery TEXT NOT NULL DEFAULT '[]');
        """)
        db.execute(
            "INSERT INTO account_mfa(user_id,secret,enabled,recovery) VALUES (?,?,1,?)",
            (user_id, secret, '["legacy-recovery-hash"]'),
        )


def test_password_login_and_change_ignore_old_enrollment_without_losing_sessions(workspace):
    client, _, _, _ = workspace
    hub = client.app.state.hub
    user = client.get("/api/auth/me").json()
    legacy_factor(hub, user["id"])
    # Removing the feature does not invalidate an otherwise valid existing session.
    assert client.get("/api/auth/me").status_code == 200
    client.post("/api/auth/logout")
    login = client.post(
        "/api/auth/login", json={"email": user["email"], "password": PASSWORD}
    )
    assert login.status_code == 200
    client.headers["X-CSRF-Token"] = login.json()["csrf"]
    changed = client.post(
        "/api/auth/password",
        json={"current_password": PASSWORD, "new_password": "Changed-password-2026"},
    )
    assert changed.status_code == 200
    assert changed.json()["other_sessions_revoked"] is True
    client.post("/api/auth/logout")
    assert client.post(
        "/api/auth/login", json={"email": user["email"], "password": PASSWORD}
    ).status_code == 401
    assert client.post(
        "/api/auth/login",
        json={"email": user["email"], "password": "Changed-password-2026"},
    ).status_code == 200


def test_operator_password_reset_remains_single_use_with_old_enrollment(workspace):
    client, _, _, _ = workspace
    hub = client.app.state.hub
    user = client.get("/api/auth/me").json()
    legacy_factor(hub, user["id"])
    reset = hub.issue_password_reset(user["email"])
    body = {"email": user["email"], "password": "Reset-password-only-2026", "token": reset["token"]}
    assert client.post("/api/auth/password-reset", json=body).status_code == 200
    assert client.get("/api/auth/me").status_code == 401
    assert client.post("/api/auth/password-reset", json=body).status_code == 403
    assert client.post(
        "/api/auth/login", json={"email": user["email"], "password": body["password"]}
    ).status_code == 200


@pytest.mark.parametrize("suffix", ["", "/enroll", "/confirm", "/disable", "/recovery-codes"])
def test_removed_factor_endpoints_are_unavailable(workspace, suffix):
    client, _, _, _ = workspace
    response = client.get("/api/auth/mfa") if not suffix else client.post("/api/auth/mfa" + suffix, json={})
    assert response.status_code in (404, 405)


def test_fresh_identity_database_does_not_create_factor_state(workspace):
    client, _, _, _ = workspace
    with client.app.state.hub.connect() as db:
        assert not db.execute("SELECT 1 FROM sqlite_master WHERE name='account_mfa'").fetchone()
