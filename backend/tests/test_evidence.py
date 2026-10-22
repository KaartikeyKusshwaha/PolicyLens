import base64
import copy
import hashlib
import io
import json
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import pytest
from pypdf import PdfReader

import evidence
from checkpoints import verify_bundle
from operations import audit, canonical
from test_product import add_customer, add_policy, approve, member, rule, txn, acting_as
from verify_evidence_pack import verify_pack


def setup_pack(workspace, tmp_path):
    client, store, _, settings = workspace
    settings.checkpoint_directory = tmp_path.parent / (tmp_path.name + "-anchors")
    manager = client.app.state.checkpoints
    org = client.get("/api/auth/me").json()["org_id"]
    return client, store, manager, org


def unpack(content):
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def repack(files):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, value in files.items():
            archive.writestr(name, value)
    return output.getvalue()


def test_seeded_signed_pack_contains_policy_control_history_case_notes_and_agent_steps(
    workspace, tmp_path
):
    client, store, manager, org = setup_pack(workspace, tmp_path)
    policy = add_policy(client)
    customer = add_customer(client)
    reviewer = member(client)
    control = approve(client, reviewer, rule(client, policy))
    client.post("/api/monitor/transactions", json=txn(customer))
    case = client.get("/api/cases").json()[0]
    client.post(
        f"/api/cases/{case['id']}/actions",
        json={"action": "note", "notes": "Important retained investigation note."},
    )
    client.post("/api/sources/ofac/sync")
    job = client.post(
        "/api/agents/jobs", json={"kind": "investigation", "target_id": case["id"]}
    ).json()
    client.app.state.engine.step(
        store, job["id"], "test_step", {"sample": "Retained agent output."}
    )
    with store.connect() as db:
        db.execute(
            "INSERT INTO records VALUES (?,?,?,?,?)",
            (
                "integration",
                "secret-integration",
                "now",
                "now",
                canonical({"secret": "DO-NOT-EXPORT-THIS-CONNECTOR-SECRET"}),
            ),
        )
    start = time.monotonic()
    response = client.get("/api/evidence/sponsor-pack")
    assert response.status_code == 200, response.text
    assert time.monotonic() - start < 60
    fingerprint = manager.status(org)["fingerprint"]
    assert verify_pack(response.content, fingerprint)["valid"]
    files = unpack(response.content)
    data = json.loads(files["evidence.json"])
    assert data["policies"][0]["id"] == policy["id"]
    assert data["policy_versions"][0]["version"] == policy["version"]
    assert data["records"]["rule"][0]["approved_by"] == control["approved_by"]
    assert "Important retained" in data["records"]["case_note"][0]["notes"]
    assert data["jobs"][0]["payload"]["model_revision"] == "provider-unreported"
    assert data["job_steps"][0]["payload"]["sample"] == "Retained agent output."
    assert data["source_freshness"][0]["sha256"]
    assert data["source_freshness"][0]["status"] == "ready"
    assert data["source_freshness"][1]["status"] == "not_synced"
    assert not data["source_freshness"][1]["enabled"]
    assert b"DO-NOT-EXPORT-THIS-CONNECTOR-SECRET" not in b"".join(files.values())
    bundle = json.loads(files["audit.json"])
    assert verify_bundle(bundle, fingerprint)["fully_anchored"]
    assert any(e["action"] == "rule_approve" for e in bundle["events"])
    pdf = PdfReader(io.BytesIO(files["report.pdf"]))
    text = "\n".join(p.extract_text() for p in pdf.pages)
    assert (
        "Sponsor evidence" in text and "Important retained investigation note" in text
    )
    # Persist only fictional output for rendering and offline subprocess validation.
    destination = tmp_path / "seeded-sponsor.zip"
    destination.write_bytes(response.content)
    result = subprocess.run(
        [
            sys.executable,
            str(Path(evidence.__file__).with_name("verify_evidence_pack.py")),
            str(destination),
            "--fingerprint",
            fingerprint,
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stdout
    assert json.loads(result.stdout)["valid"]


@pytest.mark.parametrize(
    "target",
    [
        "evidence.json",
        "report.pdf",
        "audit.json",
        "verify.py",
        "README.txt",
        "manifest.json",
    ],
)
def test_any_modified_pack_component_is_rejected(workspace, tmp_path, target):
    _, _, manager, org = setup_pack(workspace, tmp_path)
    content = evidence.export_pack(manager, org)
    files = unpack(content)
    files[target] = files[target] + b"malicious change"
    with pytest.raises(Exception):
        verify_pack(repack(files), manager.status(org)["fingerprint"])


def test_resigned_manifest_cannot_hide_bad_audit_links_or_cross_workspace_snapshot(
    workspace, tmp_path
):
    _, _, manager, org = setup_pack(workspace, tmp_path)
    content = evidence.export_pack(manager, org)
    original = unpack(content)
    key = manager.signing_key(manager.root())
    fingerprint = manager.status(org)["fingerprint"]
    for target in ("audit", "workspace"):
        files = copy.deepcopy(original)
        if target == "audit":
            data = json.loads(files["audit.json"])
            data["events"][0]["action"] = "forged_action"
            files["audit.json"] = canonical(data).encode()
        else:
            data = json.loads(files["evidence.json"])
            data["workspace_id"] = "different-workspace"
            files["evidence.json"] = canonical(data).encode()
        manifest = json.loads(files["manifest.json"])
        manifest["payload"]["files"] = {
            name: hashlib.sha256(value).hexdigest()
            for name, value in files.items()
            if name != "manifest.json"
        }
        manifest["signature"] = base64.b64encode(
            key.sign(canonical(manifest["payload"]).encode())
        ).decode()
        files["manifest.json"] = canonical(manifest).encode()
        with pytest.raises(ValueError):
            verify_pack(repack(files), fingerprint)


def test_missing_checkpoint_wrong_key_extra_or_duplicate_file_rejected(
    workspace, tmp_path
):
    client, _, manager, org = setup_pack(workspace, tmp_path)
    content = evidence.export_pack(manager, org)
    fingerprint = manager.status(org)["fingerprint"]
    for untrusted in ("", "0" * 64):
        with pytest.raises(ValueError):
            verify_pack(content, untrusted)
    files = unpack(content)
    files["../unexpected.txt"] = b"never extracted"
    with pytest.raises(ValueError):
        verify_pack(repack(files), fingerprint)
    with pytest.warns(UserWarning):
        duplicate = io.BytesIO(content)
        with zipfile.ZipFile(duplicate, "a") as archive:
            archive.writestr("evidence.json", b"{}")
    with pytest.raises(ValueError):
        verify_pack(duplicate.getvalue(), fingerprint)
    manager.settings.checkpoint_directory = None
    response = client.get("/api/evidence/sponsor-pack")
    assert response.status_code == 409


def test_export_bounds_fail_visibly_without_partial_pack_or_retention_failure(
    workspace, tmp_path, monkeypatch
):
    client, _, manager, org = setup_pack(workspace, tmp_path)
    manager.capture(org)
    monkeypatch.setattr(evidence, "MAX_SNAPSHOT_BYTES", 1)
    assert client.get("/api/evidence/sponsor-pack").status_code == 413
    assert manager.status(org)["status"] == "retained"


def test_auditor_can_export_and_snapshot_stays_consistent_if_writer_appends(
    workspace, tmp_path, monkeypatch
):
    client, store, manager, org = setup_pack(workspace, tmp_path)
    auditor = member(client, "auditor")
    original = evidence.read_snapshot

    def writer_after_read(db, workspace_id, settings):
        snapshot = original(db, workspace_id, settings)
        with store.connect() as writer:
            audit(writer, "test-writer", "concurrent_event", {})
        return snapshot

    monkeypatch.setattr(evidence, "read_snapshot", writer_after_read)
    with acting_as(client, auditor):
        response = client.get("/api/evidence/sponsor-pack")
    assert response.status_code == 200
    files = unpack(response.content)
    assert not any(
        e["action"] == "concurrent_event"
        for e in json.loads(files["audit.json"])["events"]
    )
    assert manager.status(org)["unanchored_events"] == 1
    assert verify_pack(response.content, manager.status(org)["fingerprint"])["valid"]


def test_workspace_export_cannot_include_other_tenant_records(workspace, tmp_path):
    client, _, manager, _ = setup_pack(workspace, tmp_path)
    original = add_customer(client, "PRIVATE-REFERENCE-ORIGINAL-TENANT")
    other = client.post(
        "/api/auth/workspaces", json={"name": "Separate evidence tenant"}
    ).json()["id"]
    assert client.post(f"/api/auth/workspaces/{other}/switch").status_code == 200
    response = client.get("/api/evidence/sponsor-pack")
    assert response.status_code == 200
    files = unpack(response.content)
    assert original["id"].encode() not in b"".join(files.values())
    data = json.loads(files["evidence.json"])
    assert data["workspace_id"] == other and data["records"]["customer"] == []
    assert verify_pack(response.content, manager.status(other)["fingerprint"])["valid"]


def test_fifty_case_pack_with_unicode_and_markup_renders_and_verifies_under_minute(
    workspace, tmp_path
):
    client, _, manager, org = setup_pack(workspace, tmp_path)
    customer = add_customer(client, name="Fictional <script> & Café \\ customer")
    for index in range(50):
        # Explicitly distinct customers prevent the case grouper collapsing cases.
        item = customer if index == 0 else add_customer(client, f"FICTIONAL-{index}")
        response = client.post(
            "/api/cases",
            json={
                "customer_id": item["id"],
                "title": f"Fictional case {index}",
                "description": "Synthetic evidence for pack scale verification.",
            },
        )
        assert response.status_code == 201
    started = time.monotonic()
    content = evidence.export_pack(manager, org)
    assert time.monotonic() - started < 60
    files = unpack(content)
    data = json.loads(files["evidence.json"])
    assert len(data["records"]["case"]) == 50
    assert any(row["name"] == customer["name"] for row in data["records"]["customer"])
    text = "\n".join(
        p.extract_text() for p in PdfReader(io.BytesIO(files["report.pdf"])).pages
    )
    assert "Fictional <script> & Caf" in text
    assert "Synthetic evidence for pack scale verification." in text
    assert verify_pack(content, manager.status(org)["fingerprint"])["valid"]


def test_record_and_printable_bounds_refuse_complete_export(
    workspace, tmp_path, monkeypatch
):
    client, _, _, _ = setup_pack(workspace, tmp_path)
    add_customer(client)
    monkeypatch.setattr(evidence, "MAX_ROWS", 0)
    assert client.get("/api/evidence/sponsor-pack").status_code == 413
    monkeypatch.setattr(evidence, "MAX_ROWS", 5000)
    monkeypatch.setattr(evidence, "MAX_REPORT_CHARACTERS", 1)
    assert client.get("/api/evidence/sponsor-pack").status_code == 413
