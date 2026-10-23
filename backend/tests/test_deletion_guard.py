import hashlib
import hmac
import json
import secrets
import shutil
import sys
import uuid

import pytest
from fastapi.testclient import TestClient

import deletion_guard as guard
from config import Settings
from main import create_app
from operations import Operations, canonical
from recovery import create_snapshot, restore_snapshot
from runtime import InstallationLock
from test_product import add_customer
from test_workflows import authenticate


def installation(tmp_path, encryption="none"):
    settings = Settings(
        _env_file=None,
        database_path=tmp_path / "source" / "workspace.db",
        security_key_path=tmp_path / "private" / "installation.key",
        database_encryption=encryption,
    )
    with TestClient(create_app(settings, start_worker=False)) as client:
        user = authenticate(client)
        deleted = add_customer(client, "GUARD-DELETE", name="Synthetic deleted name")
        kept = add_customer(client, "GUARD-KEEP", name="Synthetic retained name")
        store = client.app.state.hub.store(user["org_id"])
    before = tmp_path / "before"
    create_snapshot(settings, before)
    guard.guard_key(settings, create=True)
    # Seed the future executor's completed-receipt contract only in this isolated
    # synthetic fixture. Production deletion execution remains unavailable.
    with store.connect() as db:
        db.execute("DELETE FROM records WHERE id=?", (deleted["id"],))
    receipt = Operations(store).save(
        "deletion_receipt",
        {
            "status": "executed",
            "workspace_id": user["org_id"],
            "request_id": "synthetic-reviewed-request",
            "customer_id": deleted["id"],
            "deleted_records": [
                {"table": "records", "kind": "customer", "record_id": deleted["id"]}
            ],
        },
        user["id"],
    )
    path = tmp_path / "guard.json"
    info = guard.export_guard(settings, path)
    return settings, before, store, deleted, kept, receipt, path, info


@pytest.mark.parametrize("encryption", ["none", "sqlcipher4"])
def test_old_snapshot_refused_before_destination_creation_source_unchanged(
    tmp_path, encryption
):
    settings, before, _, deleted, _, _, path, info = installation(tmp_path, encryption)
    hashes = {
        p.relative_to(before): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in before.rglob("*")
        if p.is_file()
    }
    with pytest.raises(ValueError, match="resurrect"):
        restore_snapshot(
            before,
            tmp_path / "refused",
            settings,
            deletion_guard_path=path,
            trusted_guard_sha256=info["sha256"],
        )
    assert not (tmp_path / "refused").exists()
    assert hashes == {
        p.relative_to(before): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in before.rglob("*")
        if p.is_file()
    }
    payload = guard.read_guard(path, info["sha256"], settings)
    assert payload["receipts"][0]["customer_id"] == deleted["id"]
    assert b"Synthetic deleted name" not in path.read_bytes()


def test_post_deletion_snapshot_restores_with_current_guard_and_preserves_receipts(
    tmp_path,
):
    settings, _, _, deleted, kept, receipt, path, info = installation(tmp_path)
    create_snapshot(settings, tmp_path / "after")
    result = restore_snapshot(
        tmp_path / "after",
        tmp_path / "restored",
        settings,
        deletion_guard_path=path,
        trusted_guard_sha256=info["sha256"],
    )
    assert result["deletion_guard_verified"] and result["deletion_guard_receipts"] == 1
    from auth import Hub

    recovered = settings.model_copy(
        update={"database_path": tmp_path / "restored" / "workspace.db"}
    )
    store = Hub(recovered).store(receipt["workspace_id"])
    assert [value["id"] for value in Operations(store).list("customer")] == [kept["id"]]
    assert (
        Operations(store).get("deletion_receipt", receipt["id"])["customer_id"]
        == deleted["id"]
    )


def test_snapshots_with_receipts_cannot_restore_without_guard_or_with_omitted_receipt(
    tmp_path,
):
    settings, _, _, _, _, _, path, info = installation(tmp_path)
    create_snapshot(settings, tmp_path / "after")
    with pytest.raises(ValueError, match="current independently pinned"):
        restore_snapshot(tmp_path / "after", tmp_path / "missing", settings)
    payload = guard.read_guard(path, info["sha256"], settings)
    payload["receipts"] = []
    document = {
        "payload": payload,
        "hmac_sha256": hmac.new(
            guard.guard_key(settings), canonical(payload).encode(), hashlib.sha256
        ).hexdigest(),
    }
    omitted = tmp_path / "omitted.json"
    omitted.write_text(canonical(document), encoding="utf-8")
    with pytest.raises(ValueError, match="omits or changes"):
        restore_snapshot(
            tmp_path / "after",
            tmp_path / "omitted-restore",
            settings,
            deletion_guard_path=omitted,
            trusted_guard_sha256=hashlib.sha256(omitted.read_bytes()).hexdigest(),
        )
    assert (
        not (tmp_path / "missing").exists()
        and not (tmp_path / "omitted-restore").exists()
    )


def test_guard_pin_authentication_wrong_key_and_argument_pair_fail_closed(tmp_path):
    settings, before, _, _, _, _, path, info = installation(tmp_path)
    with pytest.raises(ValueError, match="trusted SHA-256"):
        guard.read_guard(path, "0" * 64, settings)
    altered = json.loads(path.read_bytes())
    altered["payload"]["receipts"] = []
    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text(canonical(altered), encoding="utf-8")
    with pytest.raises(ValueError, match="authentication"):
        guard.read_guard(
            corrupt, hashlib.sha256(corrupt.read_bytes()).hexdigest(), settings
        )
    wrong = tmp_path / "wrong.key"
    wrong.write_bytes(secrets.token_bytes(32))
    wrong.chmod(0o600)
    with pytest.raises(ValueError, match="authentication"):
        guard.read_guard(
            path,
            info["sha256"],
            settings.model_copy(update={"security_key_path": wrong}),
        )
    for arguments in (
        {"deletion_guard_path": path},
        {"trusted_guard_sha256": info["sha256"]},
    ):
        with pytest.raises(ValueError, match="both"):
            restore_snapshot(before, tmp_path / "unpaired", settings, **arguments)
    assert not (tmp_path / "unpaired").exists()


def test_export_requires_stopped_source_external_location_and_never_overwrites(
    tmp_path,
):
    settings, _, _, _, _, _, path, _ = installation(tmp_path)
    with pytest.raises(FileExistsError):
        guard.export_guard(settings, path)
    with pytest.raises(ValueError, match="outside"):
        guard.export_guard(settings, settings.database_path.parent / "unsafe.json")
    with InstallationLock(settings.database_path.parent):
        with pytest.raises(RuntimeError, match="already running"):
            guard.export_guard(settings, tmp_path / "running.json")
    assert not (tmp_path / "running.json").exists()


@pytest.mark.parametrize(
    "change", ["workspace", "table", "kind", "customer", "duplicate", "time"]
)
def test_signed_malformed_payloads_are_refused_before_restore(tmp_path, change):
    settings, before, _, _, _, _, path, info = installation(tmp_path)
    payload = guard.read_guard(path, info["sha256"], settings)
    receipt = payload["receipts"][0]
    if change == "workspace":
        payload["workspaces"] = ["invalid"]
    elif change == "table":
        receipt["candidates"][0]["table"] = "policies"
    elif change == "kind":
        receipt["candidates"][0]["kind"] = "retention_policy"
    elif change == "customer":
        receipt["customer_id"] = "not-the-selected-customer"
    elif change == "duplicate":
        payload["receipts"].append(receipt)
    else:
        payload["created_at"] = "2026-10-23"
    document = {
        "payload": payload,
        "hmac_sha256": hmac.new(
            guard.guard_key(settings), canonical(payload).encode(), hashlib.sha256
        ).hexdigest(),
    }
    path.write_text(canonical(document), encoding="utf-8")
    with pytest.raises(ValueError):
        restore_snapshot(
            before,
            tmp_path / "invalid",
            settings,
            deletion_guard_path=path,
            trusted_guard_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        )
    assert not (tmp_path / "invalid").exists()


def test_capacity_failure_writes_no_partial_guard_and_legacy_restore_is_refused(
    tmp_path, monkeypatch
):
    settings, before, _, _, _, _, _, _ = installation(tmp_path)
    monkeypatch.setattr(guard, "MAX_RECEIPTS", 0)
    with pytest.raises(ValueError, match="bound"):
        guard.export_guard(settings, tmp_path / "too-many.json")
    assert not (tmp_path / "too-many.json").exists()
    with pytest.raises(ValueError, match="every restore"):
        restore_snapshot(before, tmp_path / "legacy", settings)
    assert not (tmp_path / "legacy").exists()


def test_changed_copy_is_refused_before_restored_identity_is_rebased(
    tmp_path, monkeypatch
):
    import recovery

    settings, before, _, _, _, _, path, info = installation(tmp_path)
    create_snapshot(settings, tmp_path / "after")
    original = shutil.copyfile

    def changed_copy(source, target):
        if source.name != "identity.db":
            source = before / source.relative_to(tmp_path / "after")
        return original(source, target)

    monkeypatch.setattr(recovery.shutil, "copyfile", changed_copy)
    with pytest.raises(ValueError, match="changed during restore"):
        restore_snapshot(
            tmp_path / "after",
            tmp_path / "changed-copy",
            settings,
            deletion_guard_path=path,
            trusted_guard_sha256=info["sha256"],
        )


def test_guard_refuses_omitted_workspace_and_orphan_steps_after_customer_removed(
    tmp_path,
):
    settings, _, store, _, _, receipt, path, info = installation(tmp_path)
    payload = guard.read_guard(path, info["sha256"], settings)
    payload["workspaces"] = [str(uuid.uuid4())]
    payload["receipts"] = []
    document = {
        "payload": payload,
        "hmac_sha256": hmac.new(
            guard.guard_key(settings), canonical(payload).encode(), hashlib.sha256
        ).hexdigest(),
    }
    omitted = tmp_path / "other-workspace.json"
    omitted.write_text(canonical(document), encoding="utf-8")
    with store.connect() as db:
        db.execute(
            "INSERT INTO job_steps VALUES ('deleted-run','retained-step',?,'{}')",
            (receipt["created_at"],),
        )
    receipt["deleted_records"].append(
        {"table": "job_steps", "kind": "job_steps", "record_id": "deleted-run"}
    )
    Operations(store).save("deletion_receipt", receipt, "test", receipt["id"])
    create_snapshot(settings, tmp_path / "orphan")
    with pytest.raises(ValueError, match="omits a snapshot workspace"):
        restore_snapshot(
            tmp_path / "orphan",
            tmp_path / "omitted",
            settings,
            deletion_guard_path=omitted,
            trusted_guard_sha256=hashlib.sha256(omitted.read_bytes()).hexdigest(),
        )
    current = tmp_path / "current-guard.json"
    result = guard.export_guard(settings, current)
    with pytest.raises(ValueError, match="resurrect"):
        restore_snapshot(
            tmp_path / "orphan",
            tmp_path / "orphan-restore",
            settings,
            deletion_guard_path=current,
            trusted_guard_sha256=result["sha256"],
        )
    assert not (tmp_path / "orphan-restore").exists()


def test_operator_cli_exports_and_uses_independently_pinned_guard(
    tmp_path, monkeypatch, capsys
):
    import manage

    settings, _, _, _, _, _, _, _ = installation(tmp_path)
    create_snapshot(settings, tmp_path / "after")
    monkeypatch.setattr(manage, "Settings", lambda: settings)
    path = tmp_path / "cli-guard.json"
    monkeypatch.setattr(
        sys, "argv", ["manage.py", "deletion-guard", "--output", str(path)]
    )
    manage.main()
    result = json.loads(capsys.readouterr().out)
    assert (
        result["receipts"] == 1
        and result["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "manage.py",
            "restore",
            str(tmp_path / "after"),
            "--destination",
            str(tmp_path / "cli-restore"),
            "--deletion-guard",
            str(path),
            "--deletion-guard-sha256",
            result["sha256"],
        ],
    )
    manage.main()
    restored = json.loads(capsys.readouterr().out)
    assert restored["deletion_guard_verified"] and restored["sessions_revoked"]
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "manage.py",
            "restore",
            str(tmp_path / "after"),
            "--destination",
            str(tmp_path / "no-guard"),
        ],
    )
    with pytest.raises(SystemExit) as exc:
        manage.main()
    assert exc.value.code == 2 and not (tmp_path / "no-guard").exists()
