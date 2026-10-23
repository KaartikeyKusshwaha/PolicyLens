import asyncio
import json

import httpx
import pytest
from mcp import Client as MCPClient

from policylens_toolkit import PolicyLens, PolicyLensError
from policylens_toolkit.mcp_server import build_server
from privacy import pseudonymize
from test_product import (
    add_customer,
    add_policy,
    execute_job,
    member,
    acting_as,
    rule,
    approve,
    txn,
)
from test_workflows import prepare
from tool_contracts import TOOLS

PASSWORD = "Test-only-password-2026"


def key(client, **overrides):
    response = client.post(
        "/api/agent-keys",
        json={
            "name": "Test governed agent",
            "scopes": list(TOOLS),
            "password": PASSWORD,
            "pseudonymize": False,
            **overrides,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def call(client, credential, tool, **arguments):
    return client.post(
        "/api/toolkit/call/" + tool,
        headers={"Authorization": "Bearer " + credential["token"]},
        json=arguments,
    )


def case(client, reference="CASE-CUSTOMER", **overrides):
    customer = add_customer(client, reference, **overrides)
    response = client.post(
        "/api/cases",
        json={
            "customer_id": customer["id"],
            "title": "Seeded toolkit case",
            "description": "Investigate a synthetic customer for toolkit acceptance.",
        },
    )
    assert response.status_code == 201, response.text
    return customer, response.json()


def test_keys_are_hashed_one_time_scoped_and_not_human_sessions(workspace):
    client, _, _, _ = workspace
    credential = key(client, scopes=["search_policy"])
    assert "token" not in json.dumps(client.get("/api/agent-keys").json())
    with client.app.state.hub.connect() as db:
        assert (
            credential["token"]
            not in db.execute("SELECT token_hash FROM agent_keys").fetchone()[0]
        )
    response = client.get(
        "/api/toolkit/tools", headers={"Authorization": "Bearer " + credential["token"]}
    )
    assert [tool["name"] for tool in response.json()["tools"]] == ["search_policy"]
    assert (
        call(client, credential, "get_case_context", case_id="anything").status_code
        == 403
    )
    # A human cookie present in this test must not silently override the agent identity.
    assert (
        client.get(
            "/api/auth/me", headers={"Authorization": "Bearer " + credential["token"]}
        ).status_code
        == 403
    )
    assert client.get("/api/toolkit/tools").status_code == 401


@pytest.mark.parametrize(
    "tool",
    [
        "approve_control",
        "activate_control",
        "close_case",
        "file_report",
        "delete_customer",
    ],
)
def test_decision_and_destructive_tools_do_not_exist_and_denials_are_audited(
    workspace, tool
):
    client, store, _, _ = workspace
    credential = key(client)
    assert call(client, credential, tool).status_code == 403
    events = client.app.state.hub.store(
        client.get("/api/auth/me").json()["org_id"]
    ).connect()
    with events as db:
        event = db.execute(
            "SELECT actor,data FROM audit_chain WHERE action='tool_denied' ORDER BY seq DESC LIMIT 1"
        ).fetchone()
    assert event["actor"] == "agent:" + credential["id"]
    assert json.loads(event["data"])["tool"] == tool
    assert store is not None


def test_revocation_expiry_rate_limit_and_creator_membership_are_enforced(workspace):
    client, _, _, _ = workspace
    limited = key(client, scopes=["search_policy"], requests_per_minute=1)
    assert call(client, limited, "search_policy", query="identity").status_code == 200
    assert call(client, limited, "search_policy", query="identity").status_code == 429
    expired = key(client)
    with client.app.state.hub.connect() as db:
        db.execute(
            "UPDATE agent_keys SET expires_at='2000-01-01' WHERE id=?", (expired["id"],)
        )
    assert call(client, expired, "search_policy", query="identity").status_code == 401
    revoked = key(client)
    assert (
        client.post("/api/agent-keys/" + revoked["id"] + "/revoke").status_code == 200
    )
    assert call(client, revoked, "search_policy", query="identity").status_code == 401
    orphan = key(client)
    user = client.get("/api/auth/me").json()
    with client.app.state.hub.connect() as db:
        db.execute(
            "UPDATE memberships SET role='analyst' WHERE user_id=?", (user["id"],)
        )
    assert call(client, orphan, "search_policy", query="identity").status_code == 401


def test_non_admin_cannot_create_keys_and_arguments_cannot_smuggle_decisions(workspace):
    client, _, _, _ = workspace
    analyst = member(client, "analyst")
    with acting_as(client, analyst):
        assert (
            client.post(
                "/api/agent-keys",
                json={
                    "name": "Analyst",
                    "scopes": ["search_policy"],
                    "password": PASSWORD,
                },
            ).status_code
            == 403
        )
    credential = key(client)
    response = call(
        client,
        credential,
        "get_case_context",
        case_id="x",
        action="approve",
        private_password="DO-NOT-ECHO",
    )
    assert response.status_code == 422
    assert "DO-NOT-ECHO" not in response.text
    assert (
        client.post(
            "/api/agent-keys",
            json={
                "name": "Bad scopes",
                "password": PASSWORD,
                "scopes": ["approve_control"],
            },
        ).status_code
        == 422
    )


def test_agent_budget_and_revocation_cancel_pending_runs(workspace):
    client, _, _, _ = prepare(workspace)
    _, first = case(client, "FIRST")
    _, second = case(client, "SECOND")
    credential = key(client, daily_runs=1)
    started = call(client, credential, "draft_investigation_brief", case_id=first["id"])
    assert started.status_code == 200, started.text
    assert (
        call(
            client, credential, "draft_investigation_brief", case_id=second["id"]
        ).status_code
        == 429
    )
    assert (
        client.post("/api/agent-keys/" + credential["id"] + "/revoke").status_code
        == 200
    )
    assert (
        client.get("/api/agents/jobs/" + started.json()["id"]).json()["state"]
        == "cancelled"
    )


def test_agent_cannot_control_human_runs_or_cross_tenant_records(workspace):
    client, _, _, _ = prepare(workspace)
    customer, current = case(client)
    human = client.post(
        "/api/agents/jobs", json={"kind": "screening", "target_id": customer["id"]}
    ).json()
    credential = key(client)
    assert (
        call(
            client, credential, "control_agent_run", run_id=human["id"], action="cancel"
        ).status_code
        == 403
    )
    new_org = client.post(
        "/api/auth/workspaces", json={"name": "Separate tenant"}
    ).json()["id"]
    client.post("/api/auth/workspaces/" + new_org + "/switch")
    _, other = case(client, "OTHER-TENANT")
    assert (
        call(client, credential, "get_case_context", case_id=other["id"]).status_code
        == 404
    )
    assert (
        call(client, credential, "get_case_context", case_id=current["id"]).status_code
        == 200
    )


def test_runner_uses_pinned_model_and_masks_wire_identifiers(workspace, monkeypatch):
    client, _, _, settings = prepare(workspace)
    _, current = case(
        client,
        "PRIVATE-REFERENCE",
        name="Private Customer Name",
        address="91 Private Street",
        notes="Private analyst notes",
    )
    credential = key(client, pseudonymize=True)
    started = call(
        client, credential, "draft_investigation_brief", case_id=current["id"]
    ).json()
    expected = started["payload"]["model"]
    settings.groq_model = "changed-after-queue"
    original = client.app.state.client.post
    sent = []

    async def capture(url, **kwargs):
        sent.append(kwargs["json"])
        return await original(url, **kwargs)

    monkeypatch.setattr(client.app.state.client, "post", capture)
    result = execute_job(client, started["id"])
    assert result["state"] == "completed", result
    assert sent[0]["model"] == expected
    wire = json.dumps(sent[0])
    for value in (
        "Private Customer Name",
        "PRIVATE-REFERENCE",
        "91 Private Street",
        "Private analyst notes",
    ):
        assert value not in wire
    assert result["payload"]["model"] == expected
    assert any(step["step"] == "model_identity" for step in result["steps"])
    exported = call(client, credential, "get_case_context", case_id=current["id"])
    assert "Private Customer Name" not in exported.text
    assert (
        exported.json()["customer"]["id"]
        == result["steps"][0]["output"]["customer"]["id"]
    )


def test_explicit_provider_revision_mismatch_fails_without_another_model_attempt(
    workspace, monkeypatch
):
    client, _, _, settings = prepare(workspace)
    _, current = case(client)
    settings.groq_model_revision = "expected-fingerprint"
    credential = key(client)
    started = call(
        client, credential, "draft_investigation_brief", case_id=current["id"]
    ).json()
    original = client.app.state.client.post
    count = []

    async def mismatch(url, **kwargs):
        response = await original(url, **kwargs)
        count.append(1)
        return httpx.Response(
            200,
            json={**response.json(), "system_fingerprint": "different-fingerprint"},
            request=response.request,
        )

    monkeypatch.setattr(client.app.state.client, "post", mismatch)
    completed = execute_job(client, started["id"])
    assert completed["state"] == "failed"
    assert completed["payload"]["error"]["code"] == "model_revision_mismatch"
    assert len(count) == 1


def test_mcp_client_investigates_seeded_case_and_is_denied_approval(workspace):
    client, store, _, _ = prepare(workspace)
    _, current = case(client)
    credential = key(client)
    sdk = PolicyLens("http://127.0.0.1:8000", credential["token"], client=client)
    server = build_server(sdk)

    async def journey():
        async with MCPClient(server) as agent:
            tools = await agent.list_tools()
            assert {tool.name for tool in tools.tools} == set(TOOLS)
            context = await agent.call_tool(
                "get_case_context", {"case_id": current["id"]}
            )
            assert not context.is_error
            started = await agent.call_tool(
                "draft_investigation_brief", {"case_id": current["id"]}
            )
            run_id = started.structured_content["id"]
            # The seeded API runner is executed in its application portal, not a second runner.
            import anyio

            await anyio.to_thread.run_sync(lambda: execute_job(client, run_id))
            completed = await agent.call_tool("get_agent_run", {"run_id": run_id})
            run = completed.structured_content
            assert run["state"] == "completed", run
            verified = await agent.call_tool(
                "verify_evidence",
                {
                    "run_id": run_id,
                    "citations": [
                        {"chunk_id": citation["chunk_id"], "quote": citation["quote"]}
                        for citation in run["payload"]["result"]["citations"]
                    ],
                },
            )
            assert verified.structured_content["valid"]
            review = await agent.call_tool(
                "create_review_task",
                {
                    "case_id": current["id"],
                    "instructions": "Review the cited brief independently before any disposition.",
                },
            )
            assert review.structured_content["requires_approval"]
            for forbidden in ("approve_control", "close_case"):
                denied = await agent.call_tool(forbidden, {})
                assert denied.is_error
                assert "tool_scope_denied" in denied.content[0].text

    asyncio.run(journey())
    assert client.get("/api/cases/" + current["id"]).json()["status"] == "open"
    assert store is not None


def test_sdk_refuses_unsafe_origins_redirects_and_does_not_retry_mutations():
    for origin in (
        "http://public.example",
        "https://user:secret@example.com",
        "https://example.com/?token=x",
    ):
        with pytest.raises(ValueError):
            PolicyLens(origin, "test")
    count = []

    def redirect(request):
        count.append(request)
        return httpx.Response(307, headers={"Location": "https://other.example"})

    http = httpx.Client(
        base_url="https://example.test",
        transport=httpx.MockTransport(redirect),
        follow_redirects=True,
    )
    with PolicyLens("https://example.test", "test", client=http) as client:
        with pytest.raises(PolicyLensError, match="never forwarded"):
            client.call("search_policy", query="test")
    assert len(count) == 1


def test_structured_pseudonymization_retains_citation_references_but_masks_known_names():
    context = {
        "customer": {
            "name": "Alice Sample",
            "external_id": "CUSTOMER-123",
            "notes": "private",
        },
        "policies": [
            {"chunk_id": "policy:1:0", "text": "Alice Sample requires identity review."}
        ],
    }
    result = pseudonymize(context, b"x" * 32, "agent-one")
    assert "Alice Sample" not in json.dumps(result)
    assert "CUSTOMER-123" not in json.dumps(result)
    assert result["policies"][0]["chunk_id"] == "policy:1:0"
    assert result != pseudonymize(context, b"x" * 32, "agent-two")


def test_control_simulation_alert_pagination_and_exports_preserve_human_approvals(
    workspace,
):
    client, _, _, _ = workspace
    customer = add_customer(client)
    policy = add_policy(client)
    control = rule(client, policy)
    reviewer = member(client, "reviewer")
    approve(client, reviewer, control)
    assert (
        client.post("/api/monitor/transactions", json=txn(customer)).status_code == 201
    )
    credential = key(client)
    original_alerts = call(client, credential, "list_alerts", limit=1)
    assert len(original_alerts.json()["alerts"]) == 1
    current = original_alerts.json()["alerts"][0]["case_id"]
    details = call(client, credential, "get_control", control_id=control["id"])
    assert details.json()["control"]["status"] == "active"
    assert any(
        row["action"] == "rule_approve" for row in details.json()["approval_history"]
    )
    simulated = call(client, credential, "simulate_control", control_id=control["id"])
    assert simulated.status_code == 200, simulated.text
    assert simulated.json()["simulation"]["match_count"] == 1
    assert simulated.json()["activated"] is False
    assert simulated.json()["live_alerts_created"] is False
    assert call(client, credential, "list_alerts", offset=1).json()["alerts"] == []
    exported = call(client, credential, "export_case_pack", case_id=current)
    assert exported.json()["audit_checkpoint"]["valid"]
    assert len(exported.json()["alerts"]) == 1
    assert call(client, credential, "search_policy", query="identity").json()[
        "excerpts"
    ]


def test_masked_citations_verify_against_the_same_masked_snapshot(workspace):
    client, store, _, _ = prepare(workspace)
    policy = store.policies()[0]
    from test_workflows import POLICY

    client.put(
        "/api/policies/" + policy["id"],
        json={
            **POLICY,
            "version": "2.0",
            "content": "Private Customer Name must retain identity evidence for international transactions. "
            + POLICY["content"],
        },
    )
    _, current = case(client, name="Private Customer Name")
    credential = key(client, pseudonymize=True)
    started = call(
        client, credential, "draft_investigation_brief", case_id=current["id"]
    ).json()
    completed = execute_job(client, started["id"])
    assert completed["state"] == "completed", completed
    exported = call(client, credential, "get_agent_run", run_id=started["id"]).json()
    citations = [
        {"chunk_id": citation["chunk_id"], "quote": citation["quote"]}
        for citation in exported["payload"]["result"]["citations"]
    ]
    assert "Private Customer Name" not in json.dumps(citations)
    assert call(
        client, credential, "verify_evidence", run_id=started["id"], citations=citations
    ).json()["valid"]


def test_key_creation_requires_the_current_password(workspace):
    from test_password_auth import legacy_factor

    client, _, _, _ = workspace
    legacy_factor(client.app.state.hub, client.get("/api/auth/me").json()["id"])
    body = {
        "name": "Password protected agent",
        "scopes": ["search_policy"],
        "password": "Incorrect-password-2026",
        "pseudonymize": False,
    }
    assert client.post("/api/agent-keys", json=body).status_code == 401
    body["password"] = PASSWORD
    assert client.post("/api/agent-keys", json=body).status_code == 201


def test_prompt_version_change_never_reinterprets_a_queued_run(workspace, monkeypatch):
    client, _, state, _ = prepare(workspace)
    _, current = case(client)
    credential = key(client)
    run = call(
        client, credential, "draft_investigation_brief", case_id=current["id"]
    ).json()
    monkeypatch.setattr("agents.PROMPT_VERSION", "reviewed-future-prompt")
    completed = execute_job(client, run["id"])
    assert completed["state"] == "failed"
    assert completed["payload"]["error"]["code"] == "agent_prompt_version_changed"
    assert "model_attempts" not in completed["payload"]
    assert not any("groq.com" in url for url in state["calls"])


def test_restored_snapshot_revokes_all_agent_keys(tmp_path):
    from auth import Hub, Setup
    from agent_keys import KeyCreate
    from config import Settings
    from operations import Operations
    from recovery import create_snapshot, restore_snapshot
    from store import Store

    settings = Settings(
        _env_file=None, database_path=tmp_path / "source" / "workspace.db"
    )
    Operations(Store(settings.database_path))
    hub = Hub(settings)
    user_id, org_id = hub.setup(
        Setup(
            email="restore@example.invalid",
            name="Restore Owner",
            workspace="Restore Test",
            password=PASSWORD,
            bootstrap_token=hub.bootstrap_file.read_text(),
        )
    )
    _, user = hub.session(user_id, org_id)
    credential = hub.agent_keys.create(
        user,
        KeyCreate(
            name="Restore agent",
            scopes=["search_policy"],
            password=PASSWORD,
            pseudonymize=False,
        ),
    )
    assert hub.agent_keys.active(credential["id"])
    snapshot = tmp_path / "snapshot"
    create_snapshot(settings, snapshot)
    restored = tmp_path / "restored"
    from recovery_helpers import guard_arguments

    restore_snapshot(
        snapshot, restored, settings, **guard_arguments(settings, tmp_path)
    )
    recovered = Hub(
        settings.model_copy(update={"database_path": restored / "workspace.db"})
    )
    assert not recovered.agent_keys.active(credential["id"])
    with recovered.connect() as db:
        assert db.execute("SELECT revoked FROM agent_keys").fetchone()[0] == 1
