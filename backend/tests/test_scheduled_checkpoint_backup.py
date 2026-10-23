import base64
import hashlib
import json
import sys
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from deploy import checkpoint_backup as checkpoint, pull_backup
from deploy import watchdog
from datetime import datetime, timezone
from deploy.export_backup import export_snapshot
from main import create_app
from recovery import create_snapshot
from test_checkpoint_backup import setup
from test_deletion_state_backup import fixtures as deleted_installation
from deploy import deletion_state_backup


def test_checkpoint_staging_latest_can_be_read_after_server_restarts(tmp_path):
    settings, _, _, fingerprint, _ = setup(tmp_path)
    staging = tmp_path / "staging"
    staged = checkpoint.stage(settings, staging)
    with TestClient(create_app(settings, start_worker=False)):
        content = checkpoint.latest(settings, staging)
        assert hashlib.sha256(content).hexdigest() == staged["bundle_sha256"]
        assert len(checkpoint.verify(content, fingerprint)["files"]) == 2
        with pytest.raises(RuntimeError, match="already running"):
            checkpoint.stage(settings, staging)


@pytest.mark.parametrize("change", ["newest", "pending", "unknown", "missing"])
def test_latest_never_falls_back_from_corrupt_or_incomplete_checkpoint_staging(
    tmp_path, change
):
    settings, *_ = setup(tmp_path)
    staging = tmp_path / "staging"
    checkpoint.stage(settings, staging)
    latest = checkpoint.stage(settings, staging)
    if change == "newest":
        (staging / latest["file"]).write_bytes(b"corrupt newest bundle")
    elif change == "pending":
        (staging / "incomplete.pending").write_bytes(b"partial")
    elif change == "unknown":
        (staging / "unregistered.json").write_text("{}", encoding="utf-8")
    else:
        staging = tmp_path / "missing"
    with pytest.raises(ValueError):
        checkpoint.latest(settings, staging)


def test_fixed_checkpoint_ssh_export_does_not_allow_mixed_kinds(tmp_path, monkeypatch):
    identity, hosts = tmp_path / "identity", tmp_path / "hosts"
    identity.write_text("synthetic identity placeholder")
    hosts.write_text("synthetic hosts placeholder")
    calls = []

    def run(command, **options):
        calls.append((command, options))
        return SimpleNamespace(
            returncode=0, stdout=b"synthetic signed checkpoint history"
        )

    monkeypatch.setattr(pull_backup.subprocess, "run", run)
    pull_backup.collect(
        "ubuntu@server.example", identity, hosts, checkpoint_history=True
    )
    command, options = calls[0]
    assert command[-2:] == ["/opt/policylens/deploy/checkpoint_backup.py", "latest"]
    assert "StrictHostKeyChecking=yes" in command and "BatchMode=yes" in command
    assert options["timeout"] == 180 and not options.get("shell")
    with pytest.raises(ValueError, match="exactly one"):
        pull_backup.collect(
            "ubuntu@server.example",
            identity,
            hosts,
            checkpoint_history=True,
            deletion_state=True,
        )
    assert len(calls) == 1


def test_combined_receiver_requires_checkpoint_success_and_preserves_old_success_on_failure(
    tmp_path, monkeypatch, capsys
):
    settings, _, _, fingerprint, key = setup(tmp_path)
    snapshots = tmp_path / "snapshots"
    snapshots.mkdir()
    create_snapshot(settings, snapshots / "snapshot-20261023T120000Z")
    database = export_snapshot(snapshots, settings)
    history = checkpoint.export_bundle(settings)
    state, calls = {"fail": False}, []

    def collect(*args, checkpoint_history=False):
        calls.append(checkpoint_history)
        return (
            b"untrusted checkpoint input"
            if checkpoint_history and state["fail"]
            else history
            if checkpoint_history
            else database
        )

    monkeypatch.setattr(pull_backup, "collect", collect)
    receiver, archive_root = tmp_path / "receiver", tmp_path / "checkpoint-receiver"
    arguments = [
        "pull_backup.py",
        "--host",
        "ubuntu@server.example",
        "--identity",
        str(tmp_path / "identity"),
        "--known-hosts",
        str(tmp_path / "hosts"),
        "--key-file",
        str(key),
        "--database-key-file",
        str(settings.security_key_path),
        "--destination",
        str(receiver),
        "--checkpoint-destination",
        str(archive_root),
        "--checkpoint-fingerprint",
        fingerprint,
    ]
    monkeypatch.setattr(sys, "argv", arguments)
    assert pull_backup.main() == 0
    saved = (receiver / "last-success.json").read_bytes()
    success = json.loads(saved)
    assert (
        success["checkpoint_history"]["success"]
        and success["checkpoint_history"]["anchors"] == 2
    )
    state["fail"] = True
    assert pull_backup.main() == 1
    assert calls == [False, True, False, True]
    assert (receiver / "last-success.json").read_bytes() == saved
    assert json.loads((receiver / "last-attempt.json").read_text())["success"] is False
    assert "untrusted checkpoint input" not in capsys.readouterr().err


def test_all_three_real_encrypted_copies_are_required_in_combined_success_receipt(
    tmp_path, monkeypatch
):
    settings, key, _, _ = deleted_installation(tmp_path / "complete")
    settings = settings.model_copy(
        update={"checkpoint_directory": tmp_path / "checkpoint-root"}
    )
    checkpoints = checkpoint.export_bundle(settings)
    fingerprint = hashlib.sha256(
        base64.b64decode(json.loads(checkpoints)["public_key"])
    ).hexdigest()
    deletion = deletion_state_backup.export_bundle(settings)
    snapshots = tmp_path / "snapshots"
    snapshots.mkdir()
    create_snapshot(settings, snapshots / "snapshot-20261023T120000Z")
    database = export_snapshot(snapshots, settings)
    calls = []

    def collect(*args, deletion_state=False, checkpoint_history=False):
        calls.append((deletion_state, checkpoint_history))
        return (
            deletion
            if deletion_state
            else checkpoints
            if checkpoint_history
            else database
        )

    monkeypatch.setattr(pull_backup, "collect", collect)
    receiver = tmp_path / "database-receiver"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "pull_backup.py",
            "--host",
            "ubuntu@server.example",
            "--identity",
            "unused",
            "--known-hosts",
            "unused",
            "--key-file",
            str(key),
            "--database-key-file",
            str(settings.security_key_path),
            "--destination",
            str(receiver),
            "--deletion-state-destination",
            str(tmp_path / "deletion-receiver"),
            "--checkpoint-destination",
            str(tmp_path / "checkpoint-receiver"),
            "--checkpoint-fingerprint",
            fingerprint,
        ],
    )
    assert pull_backup.main() == 0
    receipt = json.loads((receiver / "last-success.json").read_text())
    assert (
        receipt["success"]
        and receipt["deletion_state"]["success"]
        and receipt["checkpoint_history"]["success"]
    )
    assert receipt["deletion_state"]["artifacts"] == 1
    assert receipt["checkpoint_history"]["anchors"] >= 1
    assert calls == [(False, False), (True, False), (False, True)]
    at = datetime.now(timezone.utc)
    assert watchdog.history_check(
        receiver, tmp_path / "deletion-receiver", "deletion_state", at, 30
    )["healthy"]
    assert watchdog.history_check(
        receiver, tmp_path / "checkpoint-receiver", "checkpoint_history", at, 30
    )["healthy"]


@pytest.mark.parametrize(
    "extra",
    [
        ["--checkpoint-destination", "missing-fingerprint"],
        ["--checkpoint-fingerprint", "a" * 64],
        ["--checkpoint-destination", "bad", "--checkpoint-fingerprint", "invalid"],
    ],
)
def test_receiver_requires_complete_trust_configuration_before_any_network(
    tmp_path, monkeypatch, extra
):
    def forbidden(*args, **kwargs):
        raise AssertionError("No remote collection expected")

    monkeypatch.setattr(pull_backup, "collect", forbidden)
    arguments = [
        "pull_backup.py",
        "--host",
        "ubuntu@server.example",
        "--identity",
        "unused",
        "--known-hosts",
        "unused",
        "--key-file",
        "unused",
        "--destination",
        str(tmp_path / "receipts"),
        *extra,
    ]
    monkeypatch.setattr(sys, "argv", arguments)
    assert pull_backup.main() == 1
    assert (
        json.loads((tmp_path / "receipts" / "last-attempt.json").read_text())["success"]
        is False
    )
