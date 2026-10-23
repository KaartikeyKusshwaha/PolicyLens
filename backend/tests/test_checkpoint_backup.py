import base64
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from auth import Hub
from checkpoints import Checkpoints
from config import Settings
from deploy import checkpoint_backup as backup
from main import create_app
from operations import canonical
from runtime import InstallationLock
from test_product import add_customer
from test_workflows import authenticate


def setup(tmp_path):
    settings = Settings(
        _env_file=None,
        database_path=tmp_path / "data" / "workspace.db",
        checkpoint_directory=tmp_path / "anchors",
        database_encryption="sqlcipher4",
        security_key_path=tmp_path / "private" / "key",
    )
    with TestClient(create_app(settings, start_worker=False)) as client:
        user = authenticate(client)
        client.app.state.checkpoints.capture(user["org_id"])
        add_customer(
            client, name="Synthetic checkpoint narrative must stay outside anchors"
        )
        fingerprint = client.app.state.checkpoints.status(user["org_id"])["fingerprint"]
    manager = Checkpoints(Hub(settings), settings)
    key = tmp_path / "transfer.key"
    key.write_bytes(Fernet.generate_key())
    key.chmod(0o600)
    return settings, user, manager, fingerprint, key


def resign(payload, manager):
    key = manager.signing_key(manager.root())
    public, _ = manager.identity(key)
    return (
        canonical(
            {
                "payload": payload,
                "public_key": public,
                "signature": base64.b64encode(
                    key.sign(canonical(payload).encode())
                ).decode(),
                "algorithm": "Ed25519",
            }
        )
        + "\n"
    ).encode()


def test_complete_history_verifies_encrypts_and_recovers_with_live_audit_link(tmp_path):
    settings, user, manager, fingerprint, key = setup(tmp_path)
    content = backup.export_bundle(settings)
    inventory = backup.verify(content, fingerprint)
    assert len(inventory["files"]) == 2
    assert b"Synthetic checkpoint narrative" not in content
    assert settings.security_key_path.read_bytes() not in content
    receiver = tmp_path / "receiver"
    result = backup.persist(content, fingerprint, key, receiver)
    assert result["success"] and result["anchors"] == 2
    archive = receiver / result["archive"]
    assert Fernet(key.read_bytes()).decrypt(archive.read_bytes()) == content
    assert backup.persist(content, fingerprint, key, receiver) == result
    recovered = tmp_path / "restored-anchors"
    assert (
        backup.recover(archive, fingerprint, key, recovered, result["bundle_sha256"])[
            "restored_anchors"
        ]
        == 2
    )
    restored_settings = settings.model_copy(update={"checkpoint_directory": recovered})
    status = Checkpoints(Hub(restored_settings), restored_settings).status(
        user["org_id"]
    )
    assert status["status"] == "retained" and status["unanchored_events"] == 0
    assert status["fingerprint"] == fingerprint
    with pytest.raises(ValueError, match="independently retained current digest"):
        backup.recover(
            archive, fingerprint, key, tmp_path / "wrong-current-pin", "0" * 64
        )
    assert not (tmp_path / "wrong-current-pin").exists()


@pytest.mark.parametrize(
    "change",
    [
        "signature",
        "inner_signature",
        "drop_first",
        "reverse",
        "workspace",
        "stale",
        "future",
    ],
)
def test_invalid_signed_history_is_not_accepted(tmp_path, change):
    settings, user, manager, fingerprint, _ = setup(tmp_path)
    content = backup.export_bundle(settings)
    document = json.loads(content)
    payload = document["payload"]
    anchors = payload["workspaces"][user["org_id"]]
    if change == "signature":
        document["signature"] = base64.b64encode(b"x" * 64).decode()
        content = canonical(document).encode()
    else:
        if change == "inner_signature":
            anchors[0]["signature"] = base64.b64encode(b"x" * 64).decode()
        elif change == "drop_first":
            anchors.pop(0)
        elif change == "reverse":
            anchors.reverse()
        elif change == "workspace":
            payload["workspaces"]["bad-workspace"] = payload["workspaces"].pop(
                user["org_id"]
            )
        else:
            payload["created_at"] = (
                datetime.now(timezone.utc)
                + (timedelta(hours=1) if change == "future" else -timedelta(hours=31))
            ).isoformat()
        content = resign(payload, manager)
    with pytest.raises(ValueError):
        backup.verify(content, fingerprint)


def test_receiver_rejects_authentic_truncation_and_older_state(tmp_path):
    settings, user, manager, fingerprint, key = setup(tmp_path)
    content = backup.export_bundle(settings)
    destination = tmp_path / "receiver"
    retained = backup.persist(content, fingerprint, key, destination)
    payload = json.loads(content)["payload"]
    payload["workspaces"][user["org_id"]].pop()
    payload["created_at"] = datetime.now(timezone.utc).isoformat()
    truncated = resign(payload, manager)
    assert backup.verify(truncated, fingerprint)
    with pytest.raises(ValueError, match="omits or rewrites"):
        backup.persist(truncated, fingerprint, key, destination)
    with pytest.raises(ValueError, match="trusted fingerprint"):
        backup.verify(content, "0" * 64)
    assert len(list(destination.glob("*.fernet"))) == 1
    assert (destination / retained["archive"]).is_file()


def test_unsafe_incomplete_source_and_online_export_fail_closed(tmp_path):
    settings, _, _, _, _ = setup(tmp_path)
    with InstallationLock(settings.database_path.parent):
        with pytest.raises(RuntimeError, match="already running"):
            backup.export_bundle(settings)
    (settings.checkpoint_directory / "unregistered.pending").write_text(
        "partial", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="unregistered or incomplete"):
        backup.export_bundle(settings)


def test_interrupted_recovery_blocks_normal_checkpoint_access(tmp_path, monkeypatch):
    settings, user, _, fingerprint, key = setup(tmp_path)
    saved = backup.persist(
        backup.export_bundle(settings), fingerprint, key, tmp_path / "receiver"
    )
    recovered = tmp_path / "incomplete"

    def fail(*args):
        raise OSError("Injected flush failure")

    monkeypatch.setattr(backup.os, "fsync", fail)
    with pytest.raises(OSError):
        backup.recover(
            tmp_path / "receiver" / saved["archive"],
            fingerprint,
            key,
            recovered,
            saved["bundle_sha256"],
        )
    assert (recovered / "restoration.pending").exists()
    restored = settings.model_copy(update={"checkpoint_directory": recovered})
    assert (
        Checkpoints(Hub(restored), restored).status(user["org_id"])["status"]
        == "failed"
    )


def test_real_receiver_cli_rejects_untrusted_input_without_private_output(tmp_path):
    key = tmp_path / "private-transfer.key"
    key.write_bytes(Fernet.generate_key())
    key.chmod(0o600)
    script = Path(__file__).resolve().parents[2] / "deploy" / "checkpoint_backup.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "receive",
            "--fingerprint",
            "a" * 64,
            "--key-file",
            str(key),
            "--destination",
            str(tmp_path / "refused"),
        ],
        input=b"private-untrusted-input",
        capture_output=True,
        timeout=15,
    )
    assert result.returncode == 1 and result.stdout == b""
    assert b"Checkpoint history backup failed" in result.stderr
    assert (
        b"private-untrusted-input" not in result.stderr
        and b"Traceback" not in result.stderr
    )
    assert str(key).encode() not in result.stderr
    assert not (tmp_path / "refused").exists()
