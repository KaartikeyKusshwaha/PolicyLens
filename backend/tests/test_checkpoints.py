import copy
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from checkpoints import verify_bundle, verify_signature
from operations import audit, canonical
from runtime import InstallationLock
from test_product import add_customer


def configured(workspace, tmp_path):
    client, _, _, settings = workspace
    settings.checkpoint_directory = tmp_path.parent / (tmp_path.name + "-anchors")
    org_id = client.get("/api/auth/me").json()["org_id"]
    return client, client.app.state.checkpoints, org_id


def test_external_signed_bundle_is_retained_idempotent_and_verifies_offline(
    workspace, tmp_path
):
    client, manager, org = configured(workspace, tmp_path)
    add_customer(client)
    response = client.get("/api/audit/checkpoints/export")
    assert response.status_code == 200, response.text
    bundle = response.json()
    fingerprint = manager.status(org)["fingerprint"]
    assert verify_bundle(bundle, fingerprint)["fully_anchored"]
    assert not verify_signature(bundle["checkpoint"])["trusted_key"]
    root = manager.root()
    assert not root.is_relative_to(client.app.state.settings.database_path.parent)
    files = list(root.glob("*/checkpoint-*.json"))
    assert len(files) == 1
    second = manager.capture(org)
    assert second == bundle["checkpoint"]
    assert len(list(root.glob("*/checkpoint-*.json"))) == 1
    with client.app.state.hub.store(org).connect() as db:
        audit(
            db, "test-reviewer", "new_review_recorded", {"reason": "Synthetic record."}
        )
    newer = manager.capture(org)
    assert newer["payload"]["previous_checkpoint_sha256"] != "0" * 64
    assert manager.status(org)["unanchored_events"] == 0
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps(bundle), encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            "manage.py",
            "verify-checkpoint",
            str(path),
            "--fingerprint",
            fingerprint,
        ],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["verified"]
    assert "Example Customer" not in result.stdout


@pytest.mark.parametrize(
    "damage",
    [
        "signature",
        "head",
        "workspace",
        "event",
        "truncation",
        "unsigned_tail",
        "wrong_key",
    ],
)
def test_verifier_rejects_tampering_and_untrusted_identity(workspace, tmp_path, damage):
    client, manager, org = configured(workspace, tmp_path)
    add_customer(client)
    bundle = manager.capture(org, include_events=True)
    fingerprint = manager.status(org)["fingerprint"]
    broken = copy.deepcopy(bundle)
    if damage == "signature":
        broken["checkpoint"]["signature"] = "a" * 88
    elif damage == "head":
        broken["checkpoint"]["payload"]["head_hash"] = "a" * 64
    elif damage == "workspace":
        broken["checkpoint"]["payload"]["workspace_id"] = (
            "00000000-0000-0000-0000-000000000000"
        )
    elif damage == "event":
        broken["events"][0]["data"]["tampered"] = True
    elif damage == "truncation":
        broken["events"] = broken["events"][:-1]
    elif damage == "unsigned_tail":
        with client.app.state.hub.store(org).connect() as db:
            audit(db, "test", "new_unanchored_event", {})
        broken["events"] = manager.capture(org, include_events=True)["events"]
    else:
        fingerprint = "0" * 64
    with pytest.raises(ValueError):
        verify_bundle(broken, fingerprint)


def test_full_database_rewrite_cannot_replace_retained_checkpoint(workspace, tmp_path):
    client, manager, org = configured(workspace, tmp_path)
    add_customer(client)
    original = manager.capture(org)
    store = client.app.state.hub.store(org)
    with store.connect() as db:
        db.execute("DROP TRIGGER audit_no_delete")
        db.execute("DELETE FROM audit_chain")
        db.execute("DELETE FROM sqlite_sequence WHERE name='audit_chain'")
        audit(db, "attacker", "rewritten_history", {"invented": True})
    # This replacement chain is self-consistent, but disagrees with the external anchor.
    assert client.get("/api/audit").json()["verification"]["valid"]
    with pytest.raises(ValueError, match="conflicts"):
        manager.capture(org)
    response = client.get("/api/audit/checkpoints/export")
    assert response.status_code == 409
    assert manager.status(org)["status"] == "failed"
    assert client.get("/api/ready").status_code == 503
    retained = list(manager.root().glob("*/checkpoint-*.json"))
    assert len(retained) == 1
    assert json.loads(retained[0].read_text())["signature"] == original["signature"]


def test_missing_original_key_is_not_regenerated_and_bad_signature_is_not_replaced(
    workspace, tmp_path
):
    _, manager, org = configured(workspace, tmp_path)
    manager.capture(org)
    key_file = manager.settings.database_path.parent / ".security-key"
    saved = key_file.with_suffix(".saved")
    key_file.rename(saved)
    with pytest.raises(RuntimeError, match="unavailable"):
        manager.capture(org)
    assert not key_file.exists()
    saved.rename(key_file)
    file = next(manager.root().glob("*/checkpoint-*.json"))
    original = json.loads(file.read_text())
    original["signature"] = "a" * 88
    file.write_text(json.dumps(original))
    with pytest.raises(ValueError):
        manager.capture(org)
    assert json.loads(file.read_text())["signature"] == "a" * 88


def test_checkpoint_directory_inside_database_storage_is_rejected(workspace, tmp_path):
    client, _, _, settings = workspace
    settings.checkpoint_directory = tmp_path / "inside-data"
    manager = client.app.state.checkpoints
    with pytest.raises(ValueError, match="outside"):
        manager.capture(client.get("/api/auth/me").json()["org_id"])
    assert not settings.checkpoint_directory.exists()


def test_busy_checkpoint_writer_fails_visibly_and_recovers_after_release(
    workspace, tmp_path
):
    client, manager, org = configured(workspace, tmp_path)
    manager.capture(org)
    with InstallationLock(manager.root()):
        response = client.get("/api/audit/checkpoints/export")
        assert response.status_code == 409
    manager.tick(force=True)
    assert manager.status(org)["status"] == "retained"
    assert client.get("/api/ready").status_code == 200


def test_actual_background_runner_retains_checkpoints_without_model_calls(
    workspace, tmp_path
):
    client, manager, org = configured(workspace, tmp_path)
    manager.settings.checkpoint_interval_seconds = 1
    worker = client.portal.start_task_soon(client.app.state.engine.loop)
    try:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if list(manager.root().glob("*/checkpoint-*.json")):
                break
            time.sleep(0.05)
        assert manager.status(org)["status"] == "retained"
        assert not workspace[2]["calls"]
    finally:
        worker.cancel()


def test_checkpoint_bundle_contains_no_signing_secret(workspace, tmp_path):
    _, manager, org = configured(workspace, tmp_path)
    bundle = manager.capture(org, include_events=True)
    text = canonical(bundle)
    raw = (manager.settings.database_path.parent / ".security-key").read_bytes()
    assert raw.hex() not in text
    assert "private_key" not in text
    assert verify_bundle(bundle, manager.status(org)["fingerprint"])["trusted_key"]
    if os.name != "nt":
        assert manager.root().stat().st_mode & 0o077 == 0


def test_export_size_limit_does_not_poison_retention_health(
    workspace, tmp_path, monkeypatch
):
    client, manager, org = configured(workspace, tmp_path)
    manager.capture(org)
    monkeypatch.setattr("checkpoints.MAX_BUNDLE_BYTES", 1)
    response = client.get("/api/audit/checkpoints/export")
    assert response.status_code == 413
    assert manager.status(org)["status"] == "retained"
    assert client.get("/api/ready").status_code == 200


def test_unpinned_empty_fingerprint_and_unsigned_extra_fields_are_rejected(
    workspace, tmp_path
):
    _, manager, org = configured(workspace, tmp_path)
    bundle = manager.capture(org, include_events=True)
    fingerprint = manager.status(org)["fingerprint"]
    with pytest.raises(ValueError):
        verify_signature(bundle["checkpoint"], "")
    extra = copy.deepcopy(bundle)
    extra["events"][0]["unverified_claim"] = "This was never in the audit hash."
    with pytest.raises(ValueError):
        verify_bundle(extra, fingerprint)
    with pytest.raises(ValueError):
        verify_bundle(
            {**bundle, "unverified_claim": "Do not accept extra fields."}, fingerprint
        )
