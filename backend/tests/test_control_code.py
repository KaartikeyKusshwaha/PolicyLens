import copy
import subprocess

import pytest
import yaml

import control_code
from operations import Operations
from test_product import add_policy, rule, member, approve, acting_as
from test_workflows import POLICY


def document(client, control):
    response = client.get(f"/api/control-code/export?control_id={control['id']}")
    assert response.status_code == 200, response.text
    return yaml.safe_load(response.text)


def request_for(value, **overrides):
    return {"yaml": yaml.safe_dump(value, sort_keys=False), **overrides}


def preview(client, value, **overrides):
    body = request_for(value, **overrides)
    response = client.post("/api/control-code/preview", json=body)
    assert response.status_code == 200, response.text
    return {**body, "preview_sha256": response.json()["preview_sha256"]}


def test_git_yaml_round_trip_creates_only_draft_then_requires_independent_approval(
    workspace, tmp_path
):
    client, _, _, _ = workspace
    policy = add_policy(client)
    reviewer = member(client)
    original = approve(client, reviewer, rule(client, policy))
    value = document(client, original)
    item = value["controls"][0]
    assert "status" not in item["configuration"] and "approved_by" not in item
    item["configuration"]["threshold"] = "250.00"
    git = tmp_path / "git-controls"
    git.mkdir()
    (git / "controls.yaml").write_text(
        yaml.safe_dump(value, sort_keys=False), encoding="utf-8"
    )
    for args in (
        ["init", "-q"],
        ["add", "controls.yaml"],
        [
            "-c",
            "user.name=PolicyLens Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-qm",
            "Draft threshold change",
        ],
    ):
        subprocess.run(["git", *args], cwd=git, check=True, capture_output=True)
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=git, text=True
    ).strip()
    body = preview(client, value, source_commit=commit, source_path="controls.yaml")
    imported = client.post("/api/control-code/import", json=body)
    assert imported.status_code == 201, imported.text
    result = imported.json()
    draft = result["controls"][0]["control"]
    assert not result["replayed"] and draft["status"] == "draft"
    assert draft["replaces_id"] == original["id"] and draft["version"] == 2
    assert draft["threshold"] == "250.00" and "approved_by" not in draft
    assert result["source_commit"] == commit
    self_approve = client.post(
        f"/api/rules/{draft['id']}/actions",
        json={
            "action": "approve",
            "notes": "Attempted self-approval of imported draft.",
        },
    )
    assert self_approve.status_code == 403
    approved = approve(client, reviewer, draft)
    assert approved["status"] == "active"
    assert client.get(f"/api/rules/{original['id']}").json()["status"] == "superseded"
    replay = client.post("/api/control-code/import", json=body)
    assert replay.status_code == 201 and replay.json()["replayed"]
    assert replay.json()["controls"][0]["control"]["id"] == draft["id"]
    assert len(client.get("/api/rules").json()) == 2
    bulk = client.get("/api/control-code/export")
    assert len(yaml.safe_load(bulk.text)["controls"]) == 1


@pytest.mark.parametrize("field", ["status", "approved_by", "version", "created_by"])
def test_yaml_cannot_inject_activation_or_authority_fields(workspace, field):
    client, _, _, _ = workspace
    value = document(client, rule(client, add_policy(client)))
    value["controls"][0]["configuration"][field] = "active"
    response = client.post("/api/control-code/preview", json=request_for(value))
    assert response.status_code == 422
    assert len(client.get("/api/rules").json()) == 1


@pytest.mark.parametrize(
    "content",
    [
        "!!python/object:types.SimpleNamespace {status: active}",
        "value: &anchor [1, 2]\ncopy: *anchor\n",
        "schema_version: one\nschema_version: two\n",
        "first: " + "[" * 30 + "0" + "]" * 30,
        "---\na: 1\n---\nb: 2\n",
    ],
)
def test_unsafe_ambiguous_or_unbounded_yaml_is_rejected(workspace, content):
    client, _, _, _ = workspace
    response = client.post("/api/control-code/preview", json={"yaml": content})
    assert response.status_code == 422


def test_valid_yaml_indentation_is_preserved_and_duplicate_labels_are_refused(
    workspace,
):
    client, _, _, _ = workspace
    value = document(client, rule(client, add_policy(client)))
    text = yaml.safe_dump(value, sort_keys=False)
    indented = "\n" + "\n".join("  " + line for line in text.splitlines())
    assert (
        client.post("/api/control-code/preview", json={"yaml": indented}).status_code
        == 200
    )
    value["controls"].append(copy.deepcopy(value["controls"][0]))
    assert (
        client.post("/api/control-code/preview", json=request_for(value)).status_code
        == 422
    )


def test_policy_change_and_post_preview_change_are_detected(workspace):
    client, _, _, _ = workspace
    policy = add_policy(client)
    value = document(client, rule(client, policy))
    body = preview(client, value)
    tampered = {**body, "source_path": "different.yaml"}
    assert client.post("/api/control-code/import", json=tampered).status_code == 409
    assert (
        client.put(
            f"/api/policies/{policy['id']}", json={**POLICY, "version": "2.0"}
        ).status_code
        == 200
    )
    assert client.post("/api/control-code/import", json=body).status_code == 409
    old = document(client, client.get("/api/rules").json()[0])
    assert old["controls"][0]["policy"]["version"] == "1.0"
    assert (
        client.post("/api/control-code/preview", json=request_for(old)).status_code
        == 409
    )


def test_batch_rollback_leaves_no_control_or_audit_prefix_on_late_failure(
    workspace, monkeypatch
):
    client, store, _, _ = workspace
    value = document(client, rule(client, add_policy(client)))
    value["controls"][0]["replaces"] = None
    value["controls"].append(copy.deepcopy(value["controls"][0]))
    value["controls"][1]["key"] = "second-control"
    body = preview(client, value)
    original = Operations.draft_rule
    calls = []

    def fail_second(self, db, data, user, rule_id=None):
        calls.append(True)
        if len(calls) == 2:
            raise RuntimeError("Synthetic late transactional failure.")
        return original(self, db, data, user, rule_id)

    with store.connect() as db:
        before = db.execute("SELECT count(*) FROM audit_chain").fetchone()[0]
    monkeypatch.setattr(Operations, "draft_rule", fail_second)
    with pytest.raises(RuntimeError):
        client.post("/api/control-code/import", json=body)
    assert len(client.get("/api/rules").json()) == 1
    with store.connect() as db:
        assert db.execute("SELECT count(*) FROM audit_chain").fetchone()[0] == before
        assert (
            db.execute(
                "SELECT count(*) FROM records WHERE kind='control_code_import'"
            ).fetchone()[0]
            == 0
        )


def test_tenant_role_and_parser_size_boundaries(workspace, monkeypatch):
    client, _, _, _ = workspace
    control = rule(client, add_policy(client))
    value = document(client, control)
    auditor = member(client, "auditor")
    with acting_as(client, auditor):
        assert (
            client.get(
                f"/api/control-code/export?control_id={control['id']}"
            ).status_code
            == 200
        )
        assert (
            client.post(
                "/api/control-code/preview", json=request_for(value)
            ).status_code
            == 403
        )
    other = client.post(
        "/api/auth/workspaces", json={"name": "Other code tenant"}
    ).json()["id"]
    assert client.post(f"/api/auth/workspaces/{other}/switch").status_code == 200
    assert (
        client.post("/api/control-code/preview", json=request_for(value)).status_code
        == 409
    )
    assert (
        client.get(f"/api/control-code/export?control_id={control['id']}").status_code
        == 404
    )
    monkeypatch.setattr(control_code, "MAX_BYTES", 10)
    assert (
        client.post("/api/control-code/preview", json=request_for(value)).status_code
        == 413
    )
