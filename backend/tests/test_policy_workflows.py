from test_product import add_customer, add_policy, approve, member, rule, txn, acting_as
from test_workflows import POLICY


def test_policy_review_covers_all_activity_and_never_claims_full_compliance(workspace):
    client, _, _, _ = workspace
    customer = add_customer(client)
    policy = add_policy(client)
    for ref, amount in [("small", "10.00"), ("large", "150.00")]:
        assert (
            client.post(
                "/api/monitor/transactions", json=txn(customer, ref, amount=amount)
            ).status_code
            == 201
        )
    result = client.post(f"/api/policies/{policy['id']}/review").json()
    assert (
        result["total"] == 2
        and result["not_covered"] == 2
        and result["no_control_hit"] == 0
    )
    control = rule(client, policy)
    reviewer = member(client)
    approve(client, reviewer, control)
    result = client.post(f"/api/policies/{policy['id']}/review").json()
    assert (
        result["flagged"] == 1
        and result["no_control_hit"] == 1
        and result["not_covered"] == 0
    )
    assert "No hit is not policy compliance" in result["scope"]
    assert (
        client.get(f"/api/policies/{policy['id']}/workflow").json()["review"][
            "policy_version"
        ]
        == policy["version"]
    )


def test_archive_removes_retrieval_disables_controls_preserves_history_and_restores(
    workspace,
):
    client, store, _, _ = workspace
    policy = add_policy(client)
    reviewer = member(client)
    control = rule(client, policy)
    approve(client, reviewer, control)
    assert store.search("international transaction")
    with acting_as(client, reviewer):
        assert client.delete(f"/api/policies/{policy['id']}").status_code == 403
    response = client.delete(f"/api/policies/{policy['id']}")
    assert response.status_code == 200 and response.json()["disabled_controls"] == 1
    assert client.get("/api/policies").json() == []
    assert store.search("international transaction") == []
    assert store.policy(policy["id"])["content"] == POLICY["content"]
    assert client.get("/api/rules/" + control["id"]).json()["status"] == "disabled"
    assert client.post(f"/api/policies/{policy['id']}/review").status_code == 409
    assert client.post(f"/api/policies/{policy['id']}/restore").status_code == 200
    assert len(client.get("/api/policies").json()) == 1
    assert client.get("/api/rules/" + control["id"]).json()["status"] == "disabled"


def test_upload_queues_automatic_version_pinned_analysis_and_records_review(workspace):
    client, store, _, settings = workspace
    settings.automatic_policy_analysis = True
    response = client.post("/api/policies", json=POLICY)
    assert response.status_code == 201, response.text
    result = response.json()
    assert result["automation"]["review"]["total"] == 0
    job = client.get(
        "/api/agents/jobs/" + result["automation"]["preparation_id"]
    ).json()
    assert (
        job["state"] == "queued"
        and job["payload"]["target_policy_version"] == POLICY["version"]
    )
    workflow = client.get(f"/api/policies/{result['id']}/workflow").json()
    assert workflow["automation"]["preparation_id"] == job["id"]
    with store.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 1


def test_email_delivery_is_explicit_and_invitations_are_workspace_bound(
    workspace, monkeypatch
):
    client, _, _, settings = workspace
    result = client.post(
        "/api/team/invites", json={"email": "new@example.invalid", "role": "analyst"}
    ).json()
    assert result["delivery"]["status"] == "not_configured"
    pending = client.get("/api/team/invites").json()
    assert len(pending) == 1 and "token" not in pending[0] and pending[0]["used"] == 0
    messages = []

    class SMTP:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def starttls(self, **kwargs):
            pass

        def send_message(self, message):
            messages.append(message)
            return {}

    monkeypatch.setattr("invitation_mail.smtplib.SMTP", SMTP)
    settings.smtp_host = "smtp.example.invalid"
    settings.smtp_from = "PolicyLens <invite@example.invalid>"
    settings.public_url = "https://policylens.example.invalid"
    result = client.post(
        "/api/team/invites",
        json={"email": "recipient@example.invalid", "role": "reviewer"},
    ).json()
    assert result["delivery"]["status"] == "sent"
    assert messages[0]["To"] == "recipient@example.invalid"
    assert "/join#" + result["token"] in messages[0].get_content()
    assert "Test workspace" in messages[0]["Subject"]


def test_mail_failure_does_not_claim_delivery(workspace, monkeypatch):
    client, _, _, settings = workspace
    settings.smtp_host = "smtp.example.invalid"
    settings.smtp_from = "invite@example.invalid"
    settings.public_url = "https://example.invalid"

    def unavailable(*args, **kwargs):
        raise OSError("connection unavailable")

    monkeypatch.setattr("invitation_mail.smtplib.SMTP", unavailable)
    result = client.post(
        "/api/team/invites",
        json={"email": "recipient@example.invalid", "role": "analyst"},
    ).json()
    assert result["delivery"]["status"] == "failed" and result["token"]


def test_activity_and_control_changes_refresh_policy_review_automatically(workspace):
    from operations import Operations
    from policy_workflows import refresh_pending

    client, store, _, settings = workspace
    settings.automatic_policy_analysis = True
    policy = add_policy(client)
    customer = add_customer(client)
    control = rule(client, policy)
    reviewer = member(client)
    approve(client, reviewer, control)
    client.post(
        "/api/monitor/transactions", json=txn(customer, "AUTO-1", amount="150.00")
    )
    assert client.get(f"/api/policies/{policy['id']}/workflow").json()[
        "refresh_pending"
    ]
    refresh_pending(store, Operations(store))
    result = client.get(f"/api/policies/{policy['id']}/workflow").json()
    assert result["review"]["flagged"] == 1 and not result["refresh_pending"]
    client.post(
        "/api/rules/" + control["id"] + "/actions",
        json={
            "action": "disable",
            "notes": "Disable the test control for refresh verification.",
        },
    )
    refresh_pending(store, Operations(store))
    result = client.get(f"/api/policies/{policy['id']}/workflow").json()
    assert (
        result["review"]["not_covered"] == 1
        and result["review"]["active_controls"] == 0
    )


def test_update_replaces_automatic_run_and_stops_old_version_checks(workspace):
    client, _, _, settings = workspace
    settings.automatic_policy_analysis = True
    policy = add_policy(client)
    previous = policy["automation"]["preparation_id"]
    control = rule(client, policy)
    reviewer = member(client)
    approve(client, reviewer, control)
    updated = client.put(
        "/api/policies/" + policy["id"], json={**POLICY, "version": "2.0"}
    )
    assert updated.status_code == 200
    result = updated.json()
    assert result["automation"]["preparation_id"] != previous
    assert client.get("/api/agents/jobs/" + previous).json()["state"] == "cancelled"
    assert client.get("/api/rules/" + control["id"]).json()["status"] == "disabled"
    assert result["automation"]["review"]["active_controls"] == 0


def test_archive_and_policy_workflow_do_not_cross_workspace_boundary(workspace):
    from test_registration import registration

    client, _, _, _ = workspace
    policy = add_policy(client)
    client.delete("/api/policies/" + policy["id"])
    assert len(client.get("/api/policy-archive").json()) == 1
    client.post("/api/auth/logout")
    identity = client.post("/api/auth/register", json=registration()).json()
    client.headers["X-CSRF-Token"] = identity["csrf"]
    assert client.get("/api/policy-archive").json() == []
    assert client.get(f"/api/policies/{policy['id']}/workflow").status_code == 404
    assert client.post(f"/api/policies/{policy['id']}/review").status_code == 404
    assert client.delete(f"/api/policies/{policy['id']}").status_code == 404
