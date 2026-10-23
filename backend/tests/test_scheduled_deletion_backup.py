import hashlib
import json
import sys
from types import SimpleNamespace

import pytest

from deploy import deletion_state_backup as state, pull_backup
from deploy.export_backup import export_snapshot
from recovery import create_snapshot
from test_deletion_state_backup import fixtures


def test_stopped_stage_and_readonly_latest_preserve_complete_authenticated_bytes(
    tmp_path,
):
    settings, _, _, _ = fixtures(tmp_path)
    root = tmp_path / "server-staging"
    first = state.stage(settings, root)
    content = state.latest(settings, root)
    assert hashlib.sha256(content).hexdigest() == first["bundle_sha256"]
    assert state.verify_bundle(content, settings)["files"]
    second = state.stage(settings, root)
    assert second["file"] != first["file"]
    assert (
        hashlib.sha256(state.latest(settings, root)).hexdigest()
        == second["bundle_sha256"]
    )
    assert len(list(root.glob("*.json"))) == 2


@pytest.mark.parametrize(
    "change", ["corrupt_newest", "pending", "unsafe_name", "missing"]
)
def test_staging_never_falls_back_or_overlooks_partial_publication(tmp_path, change):
    settings, _, _, _ = fixtures(tmp_path)
    root = tmp_path / "server-staging"
    state.stage(settings, root)
    newest = state.stage(settings, root)
    if change == "corrupt_newest":
        (root / newest["file"]).write_bytes(b"corrupt")
    elif change == "pending":
        (root / "incomplete.pending").write_bytes(b"partial")
    elif change == "unsafe_name":
        (root / "unexpected.json").write_text("{}", encoding="utf-8")
    else:
        root = tmp_path / "missing"
    with pytest.raises(ValueError):
        state.latest(settings, root)
    if change in ("pending", "unsafe_name"):
        before = {path.name for path in root.iterdir()}
        with pytest.raises(ValueError):
            state.stage(settings, root)
        assert {path.name for path in root.iterdir()} == before


def test_deletion_ssh_collector_uses_only_fixed_exporter_and_strict_host_identity(
    tmp_path, monkeypatch
):
    identity, hosts = tmp_path / "identity", tmp_path / "hosts"
    identity.write_text("Synthetic identity placeholder")
    hosts.write_text("Synthetic host placeholder")
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout=b"synthetic-state")

    monkeypatch.setattr(pull_backup.subprocess, "run", run)
    assert (
        pull_backup.collect(
            "ubuntu@server.example", identity, hosts, deletion_state=True
        )
        == b"synthetic-state"
    )
    command, options = calls[0]
    assert command[-2:] == ["/opt/policylens/deploy/deletion_state_backup.py", "latest"]
    assert "StrictHostKeyChecking=yes" in command and "BatchMode=yes" in command
    assert options["timeout"] == 180 and not options.get("shell")


@pytest.mark.parametrize("history_fails", [False, True])
def test_receiver_records_success_only_when_both_snapshot_and_history_verify(
    tmp_path, monkeypatch, capsys, history_fails
):
    settings, key, _, _ = fixtures(tmp_path)
    snapshots = tmp_path / "snapshots"
    snapshots.mkdir()
    create_snapshot(settings, snapshots / "snapshot-20261023T120000Z")
    database_content = export_snapshot(snapshots, settings)
    history = state.export_bundle(settings)
    requested = []

    def collect(*args, deletion_state=False):
        requested.append(deletion_state)
        return (
            b"invalid untrusted history"
            if deletion_state and history_fails
            else history
            if deletion_state
            else database_content
        )

    monkeypatch.setattr(pull_backup, "collect", collect)
    receiver, history_receiver = tmp_path / "receiver-db", tmp_path / "receiver-history"
    monkeypatch.setattr(
        sys,
        "argv",
        [
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
            "--deletion-state-destination",
            str(history_receiver),
        ],
    )
    assert pull_backup.main() == (1 if history_fails else 0)
    assert requested == [False, True]
    attempt = json.loads((receiver / "last-attempt.json").read_text())
    assert attempt["success"] is (not history_fails)
    assert (receiver / "last-success.json").exists() is (not history_fails)
    if not history_fails:
        assert attempt["deletion_state"]["success"]
        assert len(list(history_receiver.glob("*.fernet"))) == 1
    else:
        assert "invalid untrusted" not in capsys.readouterr().err
        assert not history_receiver.exists()
