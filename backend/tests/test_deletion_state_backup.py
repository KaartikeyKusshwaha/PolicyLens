import hashlib
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.fernet import Fernet, InvalidToken
import deletion_execution

from deploy import deletion_state_backup as backup
from deletion_execution import execute, verify_runtime
from auth import Hub
from runtime import InstallationLock
from test_deletion_execution import prepared
from test_deletion_requests import REASON


def fixtures(tmp_path):
    settings, user, _, request, store = prepared(tmp_path)
    execute(
        settings,
        user["org_id"],
        request["id"],
        REASON["reason"],
        acknowledge_retained_data=True,
        discovery_evidence=settings.database_path.parent.parent
        / "discovery-evidence.json",
    )
    encryption_key = tmp_path / "transfer.key"
    encryption_key.write_bytes(Fernet.generate_key())
    encryption_key.chmod(0o600)
    return settings, encryption_key, tmp_path / "receiver", store


def test_real_executed_history_is_authenticated_encrypted_and_idempotent(tmp_path):
    settings, key, destination, _ = fixtures(tmp_path)
    content = backup.export_bundle(settings)
    verified = backup.verify_bundle(content, settings)
    assert len(verified["files"]) == 1
    result = backup.persist(content, settings.security_key_path, key, destination)
    assert result["artifacts"] == 1 and result["success"]
    archive = destination / result["archive"]
    cipher = Fernet(key.read_bytes())
    assert cipher.decrypt(archive.read_bytes()) == content
    assert result["bundle_sha256"] == hashlib.sha256(content).hexdigest()
    assert b"workspace_id" not in archive.read_bytes()
    assert settings.security_key_path.read_bytes() not in content
    assert (
        backup.persist(content, settings.security_key_path, key, destination) == result
    )
    assert len(list(destination.glob("*.fernet"))) == 1


def test_encrypted_history_recovers_into_new_directory_and_matches_real_receipts(
    tmp_path,
):
    settings, key, destination, _ = fixtures(tmp_path)
    content = backup.export_bundle(settings)
    result = backup.persist(content, settings.security_key_path, key, destination)
    recovered = tmp_path / "recovered-state"
    outcome = backup.recover(
        destination / result["archive"],
        settings.security_key_path,
        key,
        recovered,
        result["bundle_sha256"],
    )
    assert outcome["restored_artifacts"] == 1
    assert not (recovered / "restoration.pending").exists()
    restored_settings = settings.model_copy(
        update={"deletion_state_directory": recovered}
    )
    verify_runtime(Hub(restored_settings), restored_settings)
    with pytest.raises(ValueError, match="new directory"):
        backup.recover(
            destination / result["archive"],
            settings.security_key_path,
            key,
            recovered,
            result["bundle_sha256"],
        )
    with pytest.raises(ValueError, match="independently retained"):
        backup.recover(
            destination / result["archive"],
            settings.security_key_path,
            key,
            tmp_path / "wrong-pin",
            "0" * 64,
        )
    assert not (tmp_path / "wrong-pin").exists()


@pytest.mark.parametrize(
    "change",
    [
        "outer_hmac",
        "inner_hmac",
        "missing_history",
        "changed_name",
        "stale",
        "future",
        "rollback_time",
    ],
)
def test_tamper_or_rollback_never_replaces_retained_history(tmp_path, change):
    settings, key, destination, _ = fixtures(tmp_path)
    content = backup.export_bundle(settings)
    result = backup.persist(content, settings.security_key_path, key, destination)
    original = (destination / result["archive"]).read_bytes()
    document = json.loads(content)
    payload = document["payload"]
    if change == "outer_hmac":
        document["hmac_sha256"] = "0" * 64
    else:
        if change == "inner_hmac":
            import base64

            name = next(iter(payload["files"]))
            inner = json.loads(base64.b64decode(payload["files"][name]))
            inner["hmac_sha256"] = "0" * 64
            payload["files"][name] = base64.b64encode(
                json.dumps(inner).encode()
            ).decode()
        elif change == "missing_history":
            payload["files"] = {}
        elif change == "changed_name":
            name = next(iter(payload["files"]))
            payload["files"]["../private.guard"] = payload["files"].pop(name)
        else:
            stamp = datetime.now(timezone.utc) + (
                timedelta(hours=1)
                if change == "future"
                else -timedelta(hours=31)
                if change == "stale"
                else -timedelta(minutes=1)
            )
            payload["created_at"] = stamp.isoformat()
        document = backup.sign(payload, settings)
    with pytest.raises((ValueError, TypeError)):
        backup.persist(
            json.dumps(document).encode(), settings.security_key_path, key, destination
        )
    assert (destination / result["archive"]).read_bytes() == original
    assert len(list(destination.glob("*.fernet"))) == 1


def test_export_requires_stopped_source_and_no_pending_operation(tmp_path):
    settings, _, _, _ = fixtures(tmp_path)
    with InstallationLock(settings.database_path.parent):
        with pytest.raises(RuntimeError, match="already running"):
            backup.export_bundle(settings)
    guard = next(settings.deletion_state_directory.glob("*.guard"))
    guard.rename(guard.with_suffix(".pending"))
    with pytest.raises(ValueError, match="interrupted"):
        backup.export_bundle(settings)


@pytest.mark.parametrize(
    "change",
    ["key_in_destination", "unknown_file", "changed_archive", "wrong_recovery_key"],
)
def test_receiver_requires_private_keys_and_intact_complete_history(tmp_path, change):
    settings, key, destination, _ = fixtures(tmp_path)
    content = backup.export_bundle(settings)
    result = backup.persist(content, settings.security_key_path, key, destination)
    if change == "key_in_destination":
        copied = destination / "unsafe.key"
        copied.write_bytes(key.read_bytes())
        key = copied
    elif change == "unknown_file":
        (destination / "interrupted.pending").write_bytes(b"incomplete")
    elif change == "changed_archive":
        archive = destination / result["archive"]
        archive.write_bytes(b"changed encrypted archive")
    else:
        wrong = tmp_path / "wrong-recovery.key"
        wrong.write_bytes(b"x" * 32)
        wrong.chmod(0o600)
        settings = settings.model_copy(update={"security_key_path": wrong})
    with pytest.raises((ValueError, InvalidToken)):
        backup.persist(content, settings.security_key_path, key, destination)
    assert len(list(destination.glob("*.fernet"))) == 1


def test_newer_complete_copy_keeps_prior_artifact_hashes(tmp_path):
    settings, key, destination, _ = fixtures(tmp_path)
    initial = backup.export_bundle(settings)
    first = backup.persist(initial, settings.security_key_path, key, destination)
    newer = backup.export_bundle(settings)
    second = backup.persist(newer, settings.security_key_path, key, destination)
    assert first["bundle_sha256"] != second["bundle_sha256"]
    assert len(list(destination.glob("*.fernet"))) == 2
    assert (
        backup.verify_bundle(initial, settings)["files"]
        == backup.verify_bundle(newer, settings)["files"]
    )


def test_aborted_reconciliation_history_survives_encrypted_offsite_recovery(
    tmp_path, monkeypatch
):
    settings, user, _, request, _ = prepared(tmp_path)
    original = deletion_execution.audit

    def fail(*args, **kwargs):
        raise RuntimeError("Injected rollback")

    monkeypatch.setattr(deletion_execution, "audit", fail)
    with pytest.raises(RuntimeError):
        execute(
            settings,
            user["org_id"],
            request["id"],
            REASON["reason"],
            acknowledge_retained_data=True,
            discovery_evidence=settings.database_path.parent.parent
            / "discovery-evidence.json",
        )
    monkeypatch.setattr(deletion_execution, "audit", original)
    deletion_execution.reconcile(
        settings, user["org_id"], request["id"], "abort", REASON["reason"]
    )
    key = tmp_path / "transfer.key"
    key.write_bytes(Fernet.generate_key())
    key.chmod(0o600)
    content = backup.export_bundle(settings)
    assert next(iter(backup.verify_bundle(content, settings)["files"])).endswith(
        ".aborted"
    )
    destination = tmp_path / "receiver"
    saved = backup.persist(content, settings.security_key_path, key, destination)
    recovered = tmp_path / "recovered-aborted"
    backup.recover(
        destination / saved["archive"],
        settings.security_key_path,
        key,
        recovered,
        saved["bundle_sha256"],
    )
    restored = settings.model_copy(update={"deletion_state_directory": recovered})
    verify_runtime(Hub(restored), restored)


def test_interrupted_recovery_keeps_blocking_marker_and_preserves_source(
    tmp_path, monkeypatch
):
    settings, key, destination, _ = fixtures(tmp_path)
    content = backup.export_bundle(settings)
    result = backup.persist(content, settings.security_key_path, key, destination)
    source = destination / result["archive"]
    before = source.read_bytes()

    def fail(*args):
        raise OSError("Injected fsync failure")

    monkeypatch.setattr(backup.os, "fsync", fail)
    recovered = tmp_path / "interrupted-recovery"
    with pytest.raises(OSError):
        backup.recover(
            source, settings.security_key_path, key, recovered, result["bundle_sha256"]
        )
    assert (recovered / "restoration.pending").is_file()
    assert source.read_bytes() == before


def test_receiver_cli_refuses_untrusted_input_without_echoing_keys_or_traceback(
    tmp_path,
):
    installation = tmp_path / "original.key"
    installation.write_bytes(b"x" * 32)
    installation.chmod(0o600)
    encryption = tmp_path / "transfer.key"
    encryption.write_bytes(Fernet.generate_key())
    encryption.chmod(0o600)
    script = Path(__file__).resolve().parents[2] / "deploy" / "deletion_state_backup.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "receive",
            "--installation-key",
            str(installation),
            "--encryption-key",
            str(encryption),
            "--destination",
            str(tmp_path / "refused"),
        ],
        input=b'{"private-untrusted-input": "never echo"}',
        capture_output=True,
        timeout=15,
    )
    assert result.returncode == 1
    assert result.stdout == b""
    assert b"Deletion state backup failed" in result.stderr
    assert b"never echo" not in result.stderr and b"Traceback" not in result.stderr
    assert str(installation).encode() not in result.stderr
    assert not (tmp_path / "refused").exists()
