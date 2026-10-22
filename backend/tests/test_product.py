import hashlib
import hmac
import json
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest

from intelligence import parse_public_feed
from test_workflows import POLICY, prepare

PASSWORD = "Test-only-password-2026"


def add_customer(client, reference="CUST-001", **values):
    response = client.post(
        "/api/customers",
        json={
            "external_id": reference,
            "name": "Example Customer",
            "country": "IN",
            **values,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def add_policy(client):
    response = client.post("/api/policies", json=POLICY)
    assert response.status_code == 201, response.text
    return response.json()


def member(client, role="reviewer"):
    email = role + "@example.invalid"
    response = client.post("/api/team/invites", json={"email": email, "role": role})
    assert response.status_code == 201, response.text
    cookie = type(client.cookies)(client.cookies)
    csrf = client.headers["X-CSRF-Token"]
    invitation = response.json()
    response = client.post(
        "/api/auth/join",
        json={
            "email": email,
            "password": PASSWORD,
            "name": "Test " + role.title(),
            "token": invitation["token"],
        },
    )
    assert response.status_code == 201, response.text
    user = response.json()
    result = {
        "user": user,
        "cookies": type(client.cookies)(client.cookies),
        "csrf": user["csrf"],
        "invitation": invitation,
    }
    client.cookies.clear()
    client.cookies.update(cookie)
    client.headers["X-CSRF-Token"] = csrf
    return result


@contextmanager
def acting_as(client, identity):
    cookies = type(client.cookies)(client.cookies)
    csrf = client.headers["X-CSRF-Token"]
    client.cookies.clear()
    client.cookies.update(identity["cookies"])
    client.headers["X-CSRF-Token"] = identity["csrf"]
    try:
        yield
    finally:
        client.cookies.clear()
        client.cookies.update(cookies)
        client.headers["X-CSRF-Token"] = csrf


def rule(client, policy, kind="amount", **overrides):
    response = client.post(
        "/api/rules",
        json={
            "title": "Test internal control",
            "kind": kind,
            "policy_id": policy["id"],
            "currency": "USD",
            "threshold": "100.00",
            "window_hours": 24,
            "countries": [],
            "priority": "high",
            "description": "An illustrative internal control for software testing.",
            **overrides,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def approve(client, reviewer, control):
    with acting_as(client, reviewer):
        response = client.post(
            "/api/rules/" + control["id"] + "/actions",
            json={
                "action": "approve",
                "notes": "Reviewed the test policy and control conditions.",
            },
        )
        assert response.status_code == 200, response.text
    return response.json()


def txn(customer, reference="PAY-001", **overrides):
    return {
        "external_id": reference,
        "customer_id": customer["id"],
        "amount": "150.00",
        "currency": "USD",
        "counterparty": "Example Trading Company",
        "counterparty_country": "GB",
        "description": "Illustrative software test payment.",
        **overrides,
    }


def execute_job(client, job_id):
    store = client.app.state.hub.store(client.get("/api/auth/me").json()["org_id"])
    job = client.app.state.engine.claim(store)
    assert job and job["id"] == job_id
    client.portal.call(
        client.app.state.engine.execute,
        client.get("/api/auth/me").json()["org_id"],
        job,
    )
    return client.get("/api/agents/jobs/" + job_id).json()


def test_authentication_csrf_and_session_storage(workspace):
    client, _, _, _ = workspace
    token = client.cookies.get("policylens_session")
    with client.app.state.hub.connect() as db:
        stored = db.execute("SELECT password FROM users LIMIT 1").fetchone()[0]
        session = db.execute("SELECT id FROM sessions LIMIT 1").fetchone()[0]
    assert PASSWORD not in stored and ":" in stored
    assert session != token
    csrf = client.headers.pop("X-CSRF-Token")
    assert client.post("/api/customers", json={"name": "Test"}).status_code == 403
    client.headers["X-CSRF-Token"] = csrf
    assert (
        client.post(
            "/api/customers",
            json={"name": "Test"},
            headers={"Origin": "https://evil.invalid"},
        ).status_code
        == 403
    )
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/customers").status_code == 401
    assert client.get("/api/health").json() == {
        "status": "ok",
        "version": "3.0.0",
        "storage": "sqlite_fts5",
    }


def test_invitation_is_email_bound_single_use_and_auditor_read_only(workspace):
    client, _, _, _ = workspace
    identity = member(client, "auditor")
    invite = identity["invitation"]
    assert (
        client.post(
            "/api/auth/join",
            json={
                "email": "auditor@example.invalid",
                "password": PASSWORD,
                "name": "Auditor",
                "token": invite["token"],
            },
        ).status_code
        == 403
    )
    with acting_as(client, identity):
        assert client.get("/api/audit").status_code == 200
        assert client.get("/api/customers").status_code == 200
        assert (
            client.post(
                "/api/customers",
                json={"external_id": "B", "name": "Forbidden", "country": "GB"},
            ).status_code
            == 403
        )
        assert client.get("/api/integrations").status_code == 403
        assert client.post("/api/backups").status_code == 403


def test_tenant_isolation_including_agent_targets_and_source_snapshots(workspace):
    client, store, _, _ = prepare(workspace)
    customer = add_customer(client)
    policy = store.policies()[0]
    case = client.post(
        "/api/cases",
        json={
            "customer_id": customer["id"],
            "title": "Original customer case",
            "description": "Review this test customer relationship.",
        },
    ).json()
    org = client.get("/api/auth/me").json()["org_id"]
    other = client.post(
        "/api/auth/workspaces", json={"name": "Separate tenant"}
    ).json()["id"]
    assert client.post("/api/auth/workspaces/" + other + "/switch").status_code == 200
    assert client.get("/api/customers").json() == []
    assert client.get("/api/policies").json() == []
    assert client.get("/api/customers/" + customer["id"]).status_code == 404
    assert client.get("/api/cases/" + case["id"]).status_code == 404
    assert client.get("/api/sources").json()["ofac"]["status"] == "not_synced"
    assert (
        client.post(
            "/api/agents/jobs", json={"kind": "investigation", "target_id": case["id"]}
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/rules",
            json={
                "title": "Cross-tenant control",
                "kind": "kyc",
                "policy_id": policy["id"],
                "description": "This policy belongs to another workspace.",
            },
        ).status_code
        == 422
    )
    add_customer(client, reference=customer["external_id"])
    assert client.post("/api/auth/workspaces/" + org + "/switch").status_code == 200
    assert client.get("/api/customers").json()[0]["id"] == customer["id"]


def test_control_approval_monitoring_and_idempotency(workspace):
    client, _, _, _ = workspace
    customer = add_customer(client)
    policy = add_policy(client)
    reviewer = member(client)
    control = rule(client, policy)
    assert (
        client.post(
            "/api/rules/" + control["id"] + "/actions",
            json={
                "action": "approve",
                "notes": "Attempted approval of my own control.",
            },
        ).status_code
        == 403
    )
    approve(client, reviewer, control)
    data = txn(customer)
    first = client.post("/api/monitor/transactions", json=data)
    assert first.status_code == 201, first.text
    assert len(first.json()["alerts"]) == 1
    duplicate = client.post("/api/monitor/transactions", json=data)
    assert duplicate.status_code == 201 and duplicate.json()["duplicate"]
    assert (
        client.post(
            "/api/monitor/transactions", json={**data, "amount": "151.00"}
        ).status_code
        == 409
    )
    assert len(client.get("/api/cases").json()) == 1
    assert len(client.get("/api/monitor/transactions").json()) == 1
    alert = first.json()["alerts"][0]
    assert alert["rule_snapshot"]["policy_version"] == "1.0"
    assert alert["facts"]["observed"] == "150.00"


@pytest.mark.parametrize(
    "kind,amounts,currencies,threshold,expected",
    [
        ("velocity", ["10.00", "20.00"], ["USD", "EUR"], "2", 1),
        ("aggregate", ["60.00", "60.00"], ["USD", "USD"], "100", 1),
        ("aggregate", ["60.00", "60.00"], ["USD", "EUR"], "100", 0),
        ("amount", ["1000.00"], ["EUR"], "100", 0),
        ("kyc", ["10.00"], ["EUR"], "100", 1),
        ("corridor", ["10.00"], ["EUR"], "100", 1),
    ],
)
def test_control_conditions_currency_and_window(
    workspace, kind, amounts, currencies, threshold, expected
):
    client, _, _, _ = workspace
    c = add_customer(client)
    p = add_policy(client)
    reviewer = member(client)
    ctrl = rule(
        client,
        p,
        kind,
        threshold=threshold,
        countries=["GB"] if kind == "corridor" else [],
    )
    approve(client, reviewer, ctrl)
    count = 0
    for i, (amount, currency) in enumerate(zip(amounts, currencies)):
        response = client.post(
            "/api/monitor/transactions",
            json=txn(c, "PAY-" + str(i), amount=amount, currency=currency),
        )
        assert response.status_code == 201, response.text
        count += len(response.json()["alerts"])
    assert count == expected


def test_backtest_has_no_live_side_effects_and_control_versions_are_atomic(workspace):
    client, _, _, _ = workspace
    c = add_customer(client)
    p = add_policy(client)
    reviewer = member(client)
    first = rule(client, p)
    client.post("/api/monitor/transactions", json=txn(c))
    simulation = client.post("/api/rules/" + first["id"] + "/backtest").json()
    assert simulation["match_count"] == 1
    assert client.get("/api/cases").json() == []
    approve(client, reviewer, first)
    new = client.put(
        "/api/rules/" + first["id"],
        json={
            "title": "Revised test control",
            "kind": "amount",
            "policy_id": p["id"],
            "threshold": "200.00",
            "description": "A proposed new threshold for the illustrative policy.",
        },
    ).json()
    assert client.get("/api/rules/" + first["id"]).json()["status"] == "active"
    approve(client, reviewer, new)
    assert client.get("/api/rules/" + first["id"]).json()["status"] == "superseded"
    assert client.get("/api/rules/" + new["id"]).json()["status"] == "active"


def test_case_requires_independent_human_resolution(workspace):
    client, _, _, _ = workspace
    c = add_customer(client)
    reviewer = member(client)
    case = client.post(
        "/api/cases",
        json={
            "customer_id": c["id"],
            "title": "Test investigation",
            "description": "Review supporting identity evidence for this test.",
        },
    ).json()
    path = "/api/cases/" + case["id"] + "/actions"
    body = {
        "action": "resolve",
        "notes": "Identity evidence checked during test.",
        "disposition": "false_positive",
    }
    assert client.post(path, json=body).status_code == 409
    owner = client.get("/api/auth/me").json()
    assert (
        client.post(
            path,
            json={
                "action": "assign",
                "assignee_id": owner["id"],
                "notes": "Assign the original investigator.",
            },
        ).status_code
        == 200
    )
    assert client.post(path, json=body).status_code == 403
    with acting_as(client, reviewer):
        assert client.post(path, json=body).status_code == 200
    exported = client.get("/api/cases/" + case["id"] + "/export").json()
    assert exported["status"] == "resolved"
    assert exported["resolved_by"] == reviewer["user"]["id"]


def test_policy_changes_preserve_history_and_review_creates_tasks_once(workspace):
    client, store, _, _ = workspace
    add_customer(client)
    p = add_policy(client)
    client.put(
        "/api/policies/" + p["id"],
        json={
            **POLICY,
            "version": "2.0",
            "content": POLICY["content"] + " Retain complete documentary records.",
        },
    )
    changes = client.get("/api/policy-changes").json()
    assert len(changes) == 1
    detail = client.get("/api/policy-changes/" + changes[0]["id"]).json()
    assert "Retain complete" in detail["diff"]
    path = "/api/policy-changes/" + changes[0]["id"] + "/actions"
    assert (
        client.post(
            path,
            json={
                "action": "approve",
                "notes": "Create applicability reviews for this policy change.",
            },
        ).json()["review_tasks_created"]
        == 1
    )
    assert (
        client.post(
            path,
            json={
                "action": "approve",
                "notes": "Duplicate review must not create more tasks.",
            },
        ).status_code
        == 409
    )
    assert len(client.get("/api/tasks").json()) == 1
    assert client.put("/api/policies/" + p["id"], json=POLICY).status_code == 409


def test_webhook_signature_expiry_idempotency_and_secret_redaction(workspace):
    client, _, _, _ = workspace
    c = add_customer(client)
    integration = client.post(
        "/api/integrations", json={"name": "Test payments integration"}
    ).json()
    assert integration["secret"] not in client.get("/api/integrations").text
    raw = json.dumps(txn(c), separators=(",", ":")).encode()
    stamp = str(int(time.time()))
    signature = (
        "sha256="
        + hmac.new(
            integration["secret"].encode(), stamp.encode() + b"." + raw, hashlib.sha256
        ).hexdigest()
    )
    headers = {
        "X-PolicyLens-Timestamp": stamp,
        "X-PolicyLens-Event-Id": "event-1",
        "X-PolicyLens-Signature": signature,
        "Content-Type": "application/json",
    }
    path = integration["webhook_path"]
    saved = type(client.cookies)(client.cookies)
    client.cookies.clear()
    first = client.post(path, content=raw, headers=headers)
    assert first.status_code == 202, first.text
    assert client.post(path, content=raw, headers=headers).json()["duplicate"]
    assert (
        client.post(
            path,
            content=raw,
            headers={**headers, "X-PolicyLens-Signature": "sha256=bad"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            path, content=raw, headers={**headers, "X-PolicyLens-Timestamp": "1"}
        ).status_code
        == 403
    )
    altered = json.dumps(txn(c, "OTHER-PAY"), separators=(",", ":")).encode()
    altered_sig = (
        "sha256="
        + hmac.new(
            integration["secret"].encode(),
            stamp.encode() + b"." + altered,
            hashlib.sha256,
        ).hexdigest()
    )
    assert (
        client.post(
            path,
            content=altered,
            headers={**headers, "X-PolicyLens-Signature": altered_sig},
        ).status_code
        == 409
    )
    client.cookies.update(saved)
    assert (
        client.post("/api/integrations/" + integration["id"] + "/revoke").status_code
        == 200
    )
    assert client.post(path, content=raw, headers=headers).status_code == 403


def test_csv_validates_all_rows_before_ingestion(workspace):
    client, _, _, _ = workspace
    c = add_customer(client)
    header = "external_id,customer_id,amount,currency,counterparty,counterparty_country,description\n"
    content = (
        header
        + f"A,{c['id']},10.00,USD,Example Receiver,GB,Test payment\nB,{c['id']},-5,USD,Example Receiver,GB,Test payment\n"
    )
    assert (
        client.post(
            "/api/monitor/import", files={"file": ("test.csv", content)}
        ).status_code
        == 422
    )
    assert client.get("/api/monitor/transactions").json() == []
    valid = header + f"A,{c['id']},10.00,USD,Example Receiver,GB,Test payment\n"
    assert (
        client.post("/api/monitor/import", files={"file": ("test.csv", valid)}).json()[
            "imported"
        ]
        == 1
    )


@pytest.mark.parametrize(
    "kind", ["investigation", "screening", "policy_analyst", "policy_change", "report"]
)
def test_agent_workflows_produce_cited_drafts_without_closing_cases(workspace, kind):
    client, store, state, _ = prepare(workspace)
    c = add_customer(client)
    p = store.policies()[0]
    case = client.post(
        "/api/cases",
        json={
            "customer_id": c["id"],
            "title": "Agent test case",
            "description": "Review a software test customer transaction.",
        },
    ).json()
    target = case["id"]
    if kind == "screening":
        target = c["id"]
    if kind == "policy_analyst":
        target = p["id"]
    if kind == "policy_change":
        client.put(
            "/api/policies/" + p["id"],
            json={
                **POLICY,
                "version": "2.0",
                "content": POLICY["content"] + " Retain documentary evidence.",
            },
        )
        target = client.get("/api/policy-changes").json()[0]["id"]
    started = client.post("/api/agents/jobs", json={"kind": kind, "target_id": target})
    assert started.status_code == 202, started.text
    completed = execute_job(client, started.json()["id"])
    assert completed["state"] == "completed", completed
    assert completed["payload"]["result"]["requires_approval"]
    if kind in ("policy_analyst", "policy_change"):
        assert completed["payload"]["result"]["obligations"][0]["citation"]["title"]
    assert any(s["step"] == "verify_evidence" for s in completed["steps"])
    assert client.get("/api/cases/" + case["id"]).json()["status"] == "open"


def test_agent_failure_pause_resume_and_restart_recovery(workspace):
    client, store, state, _ = prepare(workspace)
    c = add_customer(client)
    org = client.get("/api/auth/me").json()["org_id"]
    store = client.app.state.hub.store(org)
    start = client.post(
        "/api/agents/jobs", json={"kind": "screening", "target_id": c["id"]}
    ).json()
    path = "/api/agents/jobs/" + start["id"] + "/control"
    assert client.post(path, json={"action": "pause"}).json()["state"] == "paused"
    assert client.app.state.engine.claim(store) is None
    assert client.post(path, json={"action": "resume"}).json()["state"] == "queued"
    claimed = client.app.state.engine.claim(store)
    client.app.state.engine.recover(store)
    assert (
        client.get("/api/agents/jobs/" + claimed["id"]).json()["state"] == "interrupted"
    )
    assert client.post(path, json={"action": "resume"}).status_code == 200
    state["mode"] = "bad_quote"
    failed = execute_job(client, start["id"])
    assert failed["state"] == "failed"
    assert failed["payload"]["error"]["code"] == "unverified_citation"
    assert failed["steps"]
    assert failed["payload"]["model_attempts"] == 1
    assert client.post(path, json={"action": "resume"}).status_code == 409


def test_late_transactions_recheck_forward_windows_and_preserve_alert_snapshots(
    workspace,
):
    client, _, _, _ = workspace
    p = add_policy(client)
    c = add_customer(client)
    reviewer = member(client)
    control = rule(client, p, kind="velocity", threshold="2")
    approve(client, reviewer, control)
    stamp = datetime.now(timezone.utc) - timedelta(hours=2)
    later = client.post(
        "/api/monitor/transactions", json=txn(c, "LATER", occurred_at=stamp.isoformat())
    )
    assert later.status_code == 201 and not later.json()["alerts"]
    earlier = client.post(
        "/api/monitor/transactions",
        json=txn(c, "EARLIER", occurred_at=(stamp - timedelta(hours=1)).isoformat()),
    )
    assert earlier.status_code == 201, earlier.text
    alert = earlier.json()["alerts"][0]
    assert alert["transaction_id"] == later.json()["id"]
    assert alert["rechecked_after_late_event"]
    assert alert["facts"]["observed"] == "2"
    oldest = client.post(
        "/api/monitor/transactions",
        json=txn(c, "OLDEST", occurred_at=(stamp - timedelta(hours=2)).isoformat()),
    )
    assert oldest.status_code == 201
    case = client.get("/api/cases/" + alert["case_id"]).json()
    original = next(a for a in case["alerts"] if a["id"] == alert["id"])
    assert original["facts"]["observed"] == "2"
    assert len(case["alerts"]) == 2


def test_password_change_preserves_spaces_and_revokes_other_sessions(workspace):
    client, _, _, _ = workspace
    identity = member(client, "analyst")
    reset = client.app.state.hub.issue_password_reset("analyst@example.invalid")
    with acting_as(client, identity):
        old_cookie = type(client.cookies)(client.cookies)
        login = client.post(
            "/api/auth/login",
            json={"email": "analyst@example.invalid", "password": PASSWORD},
        )
        assert login.status_code == 200
        client.headers["X-CSRF-Token"] = login.json()["csrf"]
        password = "  New test password with spaces  "
        changed = client.post(
            "/api/auth/password",
            json={"current_password": PASSWORD, "new_password": password},
        )
        assert changed.status_code == 200
        assert (
            client.post(
                "/api/auth/password-reset",
                json={
                    "email": "analyst@example.invalid",
                    "token": reset["token"],
                    "password": "Rejected-reset-password-2026",
                },
            ).status_code
            == 403
        )
        current = type(client.cookies)(client.cookies)
        client.cookies.clear()
        client.cookies.update(old_cookie)
        assert client.get("/api/auth/me").status_code == 401
        client.cookies.clear()
        client.cookies.update(current)
        assert (
            client.post(
                "/api/auth/login",
                json={"email": "analyst@example.invalid", "password": password.strip()},
            ).status_code
            == 401
        )
        assert (
            client.post(
                "/api/auth/login",
                json={"email": "analyst@example.invalid", "password": password},
            ).status_code
            == 200
        )


def test_change_agent_uses_archived_target_even_after_another_policy_update(workspace):
    client, store, _, _ = prepare(workspace)
    policy = store.policies()[0]
    for version, extra in [
        ("2.0", " Retain documentary evidence."),
        ("3.0", " Retain documentary evidence and record independent review."),
    ]:
        response = client.put(
            "/api/policies/" + policy["id"],
            json={**POLICY, "version": version, "content": POLICY["content"] + extra},
        )
        assert response.status_code == 200
    change = next(
        c for c in client.get("/api/policy-changes").json() if c["new_version"] == "2.0"
    )
    job = client.post(
        "/api/agents/jobs", json={"kind": "policy_change", "target_id": change["id"]}
    ).json()
    done = execute_job(client, job["id"])
    assert done["state"] == "completed", done
    context = next(
        s["output"] for s in done["steps"] if s["step"] == "collect_evidence"
    )
    assert all(p["version"] == "2.0" for p in context["policies"])
    assert "independent review" not in context["policies"][0]["text"]


def test_scheduled_screening_has_no_ai_calls_and_opens_review_case(workspace):
    client, _, state, _ = prepare(workspace)
    add_customer(client, name="Alias Example 149")
    org = client.get("/api/auth/me").json()["org_id"]
    store = client.app.state.hub.store(org)
    job = client.app.state.engine.enqueue(
        store, "maintenance", "workspace", "scheduler"
    )
    result = execute_job(client, job["id"])
    assert result["state"] == "completed", result
    assert result["payload"]["result"]["ai_calls"] == 0
    assert client.get("/api/cases").json()[0]["priority"] == "high"


def test_audit_is_verifiable_and_backup_can_be_restored(workspace, tmp_path):
    client, store, _, _ = workspace
    add_customer(client)
    assert client.get("/api/audit").json()["verification"]["valid"]
    backup = client.post("/api/backups").json()
    downloaded = client.get(backup["download_url"])
    assert downloaded.status_code == 200
    path = tmp_path / "restored.db"
    path.write_bytes(downloaded.content)
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert (
            db.execute("SELECT count(*) FROM records WHERE kind='customer'").fetchone()[
                0
            ]
            == 1
        )
    with store.connect() as db:
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE audit_chain SET action='tampered'")
    with store.connect() as db:
        db.execute("DROP TRIGGER audit_no_update")
        db.execute("UPDATE audit_chain SET action='tampered' WHERE seq=1")
    assert not client.get("/api/audit").json()["verification"]["valid"]


def test_access_revocation_and_last_admin_protection(workspace):
    client, _, _, _ = workspace
    me = client.get("/api/auth/me").json()
    assert (
        client.post(
            "/api/team/" + me["id"] + "/access", json={"role": "revoked"}
        ).status_code
        == 409
    )
    other = member(client, "analyst")
    assert (
        client.post(
            "/api/team/" + other["user"]["id"] + "/access", json={"role": "revoked"}
        ).status_code
        == 200
    )
    with acting_as(client, other):
        assert client.get("/api/customers").status_code == 401


def test_un_and_uk_feed_parsers_include_aliases():
    un = b'<CONSOLIDATED_LIST dateGenerated="2026-10-19"><INDIVIDUALS><INDIVIDUAL><DATAID>1</DATAID><FIRST_NAME>Test</FIRST_NAME><SECOND_NAME>Person</SECOND_NAME><UN_LIST_TYPE>TEST</UN_LIST_TYPE><INDIVIDUAL_ALIAS><ALIAS_NAME>Example Alias</ALIAS_NAME></INDIVIDUAL_ALIAS></INDIVIDUAL></INDIVIDUALS></CONSOLIDATED_LIST>'
    uk = b"<Designations><DateGenerated>2026-10-19</DateGenerated><Designation><UniqueID>TEST1</UniqueID><RegimeName>TEST</RegimeName><Names><Name><Name1>Test</Name1><Name6>Person</Name6></Name><Name><Name1>Example Alias</Name1></Name></Names></Designation></Designations>"
    assert parse_public_feed("un", un)["entries"][0]["aliases"] == ["Example Alias"]
    assert parse_public_feed("uk", uk)["entries"][0]["aliases"] == ["Example Alias"]
