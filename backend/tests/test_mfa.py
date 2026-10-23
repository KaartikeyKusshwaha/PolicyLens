import base64
import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import HTTPException

from auth import Credentials

from security import SecretBox, matching_counter, totp

PASSWORD = "Test-only-password-2026"


@pytest.mark.parametrize(
    "stamp,expected",
    [
        (59, "94287082"),
        (1111111109, "07081804"),
        (1111111111, "14050471"),
        (1234567890, "89005924"),
        (2000000000, "69279037"),
        (20000000000, "65353130"),
    ],
)
def test_rfc6238_sha1_vectors(stamp, expected):
    secret = base64.b32encode(b"12345678901234567890").decode()
    assert totp(secret, stamp // 30, 8) == expected


@pytest.fixture
def clock(monkeypatch):
    stamp = [1800000000]
    original = matching_counter
    monkeypatch.setattr(
        "mfa.matching_counter",
        lambda secret, code, last=-1: original(secret, code, last, stamp=stamp[0]),
    )
    return stamp


def accept(client, response):
    assert response.status_code == 200, response.text
    client.headers["X-CSRF-Token"] = response.json()["user"]["csrf"]
    return response.json()


def enable(client, clock):
    response = client.post("/api/auth/mfa/enroll", json={"password": PASSWORD})
    assert response.status_code == 200, response.text
    enrollment = response.json()
    code = totp(enrollment["secret"], clock[0] // 30)
    result = accept(
        client,
        client.post("/api/auth/mfa/confirm", json={"password": PASSWORD, "code": code}),
    )
    return enrollment, result


def login(client, factor="", password=PASSWORD):
    return client.post(
        "/api/auth/login",
        json={
            "email": "owner@example.invalid",
            "password": password,
            "second_factor": factor,
        },
    )


def test_mfa_enrollment_login_replay_and_revoked_sessions(workspace, clock):
    client, _, _, settings = workspace
    old_cookie = type(client.cookies)(client.cookies)
    old_csrf = client.headers["X-CSRF-Token"]
    enrollment, result = enable(client, clock)
    assert len(result["recovery_codes"]) == 10
    assert client.get("/api/auth/mfa").json() == {
        "enabled": True,
        "recovery_codes_remaining": 10,
    }
    assert login(client).status_code == 401
    assert login(client, totp(enrollment["secret"], clock[0] // 30)).status_code == 401
    clock[0] += 30
    response = login(client, totp(enrollment["secret"], clock[0] // 30))
    assert response.status_code == 200
    client.headers["X-CSRF-Token"] = response.json()["csrf"]
    hub = client.app.state.hub
    with hub.connect() as db:
        row = db.execute("SELECT * FROM account_mfa").fetchone()
        assert enrollment["secret"] not in row["secret"]
        assert all(code not in row["recovery"] for code in result["recovery_codes"])
        assert "mfa_enabled" in [
            r[0] for r in db.execute("SELECT action FROM security_events")
        ]
    assert settings.database_path.parent.joinpath(".security-key").stat().st_size == 32
    client.cookies.clear()
    client.cookies.update(old_cookie)
    client.headers["X-CSRF-Token"] = old_csrf
    assert client.get("/api/auth/me").status_code == 401


def test_recovery_codes_are_single_use_and_rotation_invalidates_old(workspace, clock):
    client, _, _, _ = workspace
    _, result = enable(client, clock)
    codes = result["recovery_codes"]
    assert login(client, codes[0]).status_code == 200
    assert login(client, codes[0]).status_code == 401
    response = login(client, codes[1])
    client.headers["X-CSRF-Token"] = response.json()["csrf"]
    changed = accept(
        client,
        client.post(
            "/api/auth/mfa/recovery-codes",
            json={"password": PASSWORD, "code": codes[2]},
        ),
    )
    assert login(client, codes[3]).status_code == 401
    assert login(client, changed["recovery_codes"][0]).status_code == 200


def test_factor_management_requires_csrf_password_and_factor(workspace, clock):
    client, _, _, _ = workspace
    _, result = enable(client, clock)
    codes = result["recovery_codes"]
    assert (
        client.post("/api/auth/mfa/disable", json={"password": PASSWORD}).status_code
        == 401
    )
    assert (
        client.post(
            "/api/auth/mfa/disable",
            json={"password": "Wrong-password-2026", "code": codes[0]},
        ).status_code
        == 401
    )
    csrf = client.headers.pop("X-CSRF-Token")
    assert (
        client.post(
            "/api/auth/mfa/disable", json={"password": PASSWORD, "code": codes[0]}
        ).status_code
        == 403
    )
    client.headers["X-CSRF-Token"] = csrf
    accept(
        client,
        client.post(
            "/api/auth/mfa/disable", json={"password": PASSWORD, "code": codes[0]}
        ),
    )
    assert not client.get("/api/auth/mfa").json()["enabled"]
    assert login(client).status_code == 200


def test_enrollment_expiry_and_existing_factor_not_overwritten(workspace, clock):
    client, _, _, _ = workspace
    response = client.post("/api/auth/mfa/enroll", json={"password": PASSWORD})
    secret = response.json()["secret"]
    with client.app.state.hub.connect() as db:
        db.execute("UPDATE account_mfa SET expires_at='2000-01-01T00:00:00+00:00'")
    assert (
        client.post(
            "/api/auth/mfa/confirm",
            json={"password": PASSWORD, "code": totp(secret, clock[0] // 30)},
        ).status_code
        == 409
    )
    enable(client, clock)
    assert (
        client.post("/api/auth/mfa/enroll", json={"password": PASSWORD}).status_code
        == 409
    )


def test_password_reset_preserves_second_factor(workspace, clock):
    client, _, _, _ = workspace
    _, result = enable(client, clock)
    reset = client.app.state.hub.issue_password_reset("owner@example.invalid")
    password = "Replacement-password-2026"
    assert (
        client.post(
            "/api/auth/password-reset",
            json={
                "email": "owner@example.invalid",
                "password": password,
                "token": reset["token"],
            },
        ).status_code
        == 200
    )
    assert login(client, password=password).status_code == 401
    assert login(client, result["recovery_codes"][0], password).status_code == 200


def test_existing_account_cannot_bypass_factor_through_invitation(workspace, clock):
    client, _, _, _ = workspace
    _, result = enable(client, clock)
    invitation = client.post(
        "/api/team/invites", json={"email": "owner@example.invalid", "role": "analyst"}
    ).json()
    data = {
        "email": "owner@example.invalid",
        "name": "Owner",
        "password": PASSWORD,
        "token": invitation["token"],
    }
    assert client.post("/api/auth/join", json=data).status_code == 401
    data["second_factor"] = result["recovery_codes"][0]
    assert client.post("/api/auth/join", json=data).status_code == 201


def test_password_change_demands_factor_and_old_recovery_cannot_replay(
    workspace, clock
):
    client, _, _, _ = workspace
    _, result = enable(client, clock)
    body = {"current_password": PASSWORD, "new_password": "Another-password-2026"}
    assert client.post("/api/auth/password", json=body).status_code == 401
    body["second_factor"] = result["recovery_codes"][0]
    assert client.post("/api/auth/password", json=body).status_code == 200
    assert login(client, body["second_factor"], body["new_password"]).status_code == 401


def test_missing_encryption_key_fails_closed_and_does_not_regenerate(workspace, clock):
    client, _, _, settings = workspace
    enable(client, clock)
    key = settings.database_path.parent / ".security-key"
    key.rename(key.with_suffix(".saved"))
    with pytest.raises(RuntimeError, match="encryption key is unavailable"):
        login(client, "123456")
    assert not key.exists()


def test_secret_encryption_rejects_tampering_and_cross_user_rebinding(workspace):
    _, _, _, settings = workspace
    box = SecretBox(settings)
    encrypted = box.encrypt("sensitive seed", "mfa:user-1")
    assert box.decrypt(encrypted, "mfa:user-1") == "sensitive seed"
    with pytest.raises(RuntimeError, match="could not be verified"):
        box.decrypt(encrypted, "mfa:user-2")
    with pytest.raises(RuntimeError, match="could not be verified"):
        box.decrypt(
            base64.urlsafe_b64encode(b"invalid encrypted secret").decode(), "mfa:user-1"
        )


def test_totp_window_rejects_future_outside_window_and_malformed_codes():
    secret = base64.b32encode(b"12345678901234567890").decode()
    stamp = 1800000000
    counter = stamp // 30
    assert matching_counter(secret, totp(secret, counter), stamp=stamp) == counter
    assert matching_counter(secret, totp(secret, counter), counter, stamp) is None
    assert matching_counter(secret, totp(secret, counter + 2), stamp=stamp) is None
    assert matching_counter(secret, "12345a", stamp=stamp) is None


def test_public_secret_key_must_be_provisioned_explicitly(workspace, tmp_path):
    _, _, _, settings = workspace
    target = tmp_path / "unprovisioned-key"
    public = settings.model_copy(
        update={"deployment_mode": "public", "security_key_path": target}
    )
    with pytest.raises(RuntimeError, match="encryption key is unavailable"):
        SecretBox(public).encrypt("seed", "mfa:user")
    assert not target.exists()


def test_failed_factor_attempts_are_rate_limited_per_account(workspace, clock):
    client, _, _, _ = workspace
    enable(client, clock)
    statuses = [login(client, "invalid").status_code for _ in range(13)]
    assert statuses[-1] == 429
    assert set(statuses) <= {401, 429}


def test_security_events_do_not_contain_secrets(workspace, clock):
    client, _, _, _ = workspace
    enrollment, result = enable(client, clock)
    with client.app.state.hub.connect() as db:
        records = json.dumps(
            [dict(row) for row in db.execute("SELECT * FROM security_events")]
        )
    assert enrollment["secret"] not in records
    assert PASSWORD not in records
    assert all(code not in records for code in result["recovery_codes"])


def test_concurrent_totp_replay_can_create_only_one_session(workspace, clock):
    client, _, _, _ = workspace
    enrollment, _ = enable(client, clock)
    clock[0] += 30
    credentials = Credentials(
        email="owner@example.invalid",
        password=PASSWORD,
        second_factor=totp(enrollment["secret"], clock[0] // 30),
    )
    hub = client.app.state.hub

    def attempt(_):
        try:
            hub.login(credentials)
            return 200
        except HTTPException as failure:
            return failure.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(attempt, range(2))) == [200, 401]
