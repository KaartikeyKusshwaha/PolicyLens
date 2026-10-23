import uuid
import sys
import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import deletion_execution as execution
from auth import Hub
from config import Settings
from deletion_guard import read_guard
from recovery import create_snapshot, restore_snapshot
from main import create_app
from operations import Operations, canonical
from test_deletion_requests import aged, submit, APPROVAL, REASON
from test_product import acting_as, member
from test_workflows import authenticate


def prepared(tmp_path, encryption="sqlcipher4", linked=False):
    settings = Settings(
        _env_file=None,
        database_path=tmp_path / "data" / "workspace.db",
        security_key_path=tmp_path / "keys" / "key",
        database_encryption=encryption,
        deletion_state_directory=tmp_path / "deletion-state",
    )
    with TestClient(create_app(settings, start_worker=False)) as client:
        user = authenticate(client)
        customer = aged(client)
        if linked:
            store = client.app.state.hub.store(user["org_id"])
            stamp = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
            case_id, job_id, decision_id = (str(uuid.uuid4()) for _ in range(3))
            with store.connect() as db:
                for kind, record_id, data in (
                    (
                        "case",
                        case_id,
                        {
                            "customer_id": customer["id"],
                            "status": "resolved",
                            "resolved_at": stamp,
                        },
                    ),
                    (
                        "task",
                        str(uuid.uuid4()),
                        {
                            "case_id": case_id,
                            "status": "completed",
                            "completed_at": stamp,
                        },
                    ),
                    (
                        "case_note",
                        str(uuid.uuid4()),
                        {"case_id": case_id, "notes": "Synthetic retained note"},
                    ),
                ):
                    db.execute(
                        "INSERT INTO records VALUES (?,?,?,?,?)",
                        (kind, record_id, stamp, stamp, canonical(data)),
                    )
                db.execute(
                    "INSERT INTO transactions VALUES ('test-transaction','TX-DELETE',?,100,'USD',?,?, '{}')",
                    (customer["id"], stamp, stamp),
                )
                db.execute(
                    "INSERT INTO alerts VALUES ('test-alert','ALERT-DELETE',?,?, '{}')",
                    (case_id, stamp),
                )
                db.execute(
                    "INSERT INTO jobs VALUES (?, 'investigation',?, 'completed',?,?, 'synthetic','{}')",
                    (job_id, case_id, stamp, stamp),
                )
                db.execute(
                    "INSERT INTO job_steps VALUES (?, 'test-step',?, '{}')",
                    (job_id, stamp),
                )
                db.execute(
                    "INSERT INTO decisions VALUES (?, 'test-decision-txn',?,?)",
                    (decision_id, stamp, canonical({"customer_id": customer["id"]})),
                )
                db.execute(
                    "INSERT INTO reviews VALUES ('test-review',?,?, '{}')",
                    (decision_id, stamp),
                )
        reviewer = member(client)
        request = submit(client, customer)
        with acting_as(client, reviewer):
            result = client.post(
                f"/api/retention/deletion-requests/{request['id']}/approve",
                json=APPROVAL,
            )
            assert result.status_code == 200, result.text
        store = client.app.state.hub.store(user["org_id"])
    return settings, user, customer, request, store


def run(settings, user, request):
    return execution.execute(
        settings,
        user["org_id"],
        request["id"],
        REASON["reason"],
        acknowledge_retained_data=True,
    )


def test_exact_logical_deletion_keeps_governance_and_audit_and_restarts(tmp_path):
    settings, user, customer, request, store = prepared(tmp_path)
    result = run(settings, user, request)
    assert result["deleted_records"] == 1 and not result["physical_erasure_proven"]
    assert not Operations(store).list("customer")
    receipt = Operations(store).get("deletion_receipt", result["receipt_id"])
    assert receipt["customer_id"] == customer["id"]
    assert receipt["maker_id"] != receipt["reviewer_id"]
    assert receipt["inventory_sha256"] == request["inventory_sha256"]
    payload = read_guard(result["guard_path"], result["guard_sha256"], settings)
    assert payload["receipts"][0]["receipt_id"] == receipt["id"]
    assert Operations(store).list("retention_policy")[0]["status"] == "active"
    settings = settings.model_copy(
        update={"checkpoint_directory": tmp_path / "checkpoints"}
    )
    with TestClient(create_app(settings, start_worker=False)) as client:
        login = client.post(
            "/api/auth/login",
            json={
                "email": "owner@example.invalid",
                "password": "Test-only-password-2026",
            },
        )
        assert login.status_code == 200
        detail = client.get(f"/api/retention/deletion-requests/{request['id']}")
        assert detail.status_code == 200, detail.text
        assert detail.json()["receipt"]["id"] == result["receipt_id"]
        assert client.get("/api/audit").json()["verification"]["valid"]
        from test_evidence import unpack
        from verify_evidence_pack import verify_pack

        pack = client.get("/api/evidence/sponsor-pack")
        assert pack.status_code == 200, pack.text
        fingerprint = client.app.state.checkpoints.status(user["org_id"])["fingerprint"]
        assert verify_pack(pack.content, fingerprint)["valid"]
        evidence = json.loads(unpack(pack.content)["evidence.json"])
        assert evidence["records"]["deletion_receipt"][0]["id"] == result["receipt_id"]
        assert evidence["records"]["customer"] == []
    with pytest.raises(ValueError, match="independently approved"):
        run(settings, user, request)


def test_abort_reconciliation_can_resume_after_its_database_commit(
    tmp_path, monkeypatch
):
    settings, user, customer, request, store = prepared(tmp_path)
    original_audit, original_complete = execution.audit, execution.complete_file

    def fail(*args, **kwargs):
        raise RuntimeError("Injected interruption")

    monkeypatch.setattr(execution, "audit", fail)
    with pytest.raises(RuntimeError):
        run(settings, user, request)
    monkeypatch.setattr(execution, "audit", original_audit)
    monkeypatch.setattr(execution, "complete_file", fail)
    with pytest.raises(RuntimeError):
        execution.reconcile(
            settings, user["org_id"], request["id"], "abort", REASON["reason"]
        )
    assert (
        Operations(store).get("deletion_request", request["id"])["status"]
        == "cancelled"
    )
    monkeypatch.setattr(execution, "complete_file", original_complete)
    execution.reconcile(
        settings, user["org_id"], request["id"], "abort", REASON["reason"]
    )
    execution.verify_runtime(Hub(settings), settings)
    assert Operations(store).get("customer", customer["id"])
    # Retrying needs a new independent approval rather than reusing the aborted
    # execution's pending/final filenames and review authorization.
    from deletion import preview
    from deletion_requests import create, approve, RequestInput, ApprovalInput

    old = Operations(store).get("deletion_request", request["id"])
    snapshot = preview(store, user["org_id"], customer["id"])
    fresh = create(
        store,
        user["org_id"],
        RequestInput(
            customer_id=customer["id"],
            inventory_sha256=snapshot["inventory_sha256"],
            **REASON,
        ),
        user,
    )
    approve(
        store,
        user["org_id"],
        fresh["id"],
        ApprovalInput(**APPROVAL),
        {"id": old["approved_by"], "role": "reviewer"},
    )
    assert run(settings, user, fresh)["deleted_records"] == 1


def test_linked_operational_rows_removed_atomically_in_dependency_order(tmp_path):
    settings, user, _, request, store = prepared(tmp_path, linked=True)
    result = run(settings, user, request)
    assert result["deleted_records"] == 10
    with store.connect() as db:
        for table in (
            "transactions",
            "alerts",
            "jobs",
            "job_steps",
            "decisions",
            "reviews",
        ):
            assert db.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0
        assert (
            db.execute(
                "SELECT count(*) FROM records WHERE kind IN ('customer','case','task','case_note')"
            ).fetchone()[0]
            == 0
        )
        assert (
            db.execute(
                "SELECT count(*) FROM records WHERE kind='retention_policy'"
            ).fetchone()[0]
            == 1
        )
    execution.verify_runtime(Hub(settings), settings)


@pytest.mark.parametrize(
    "change", ["customer", "hold", "reviewer", "expiry", "state", "copy"]
)
def test_changes_since_review_refuse_before_publication(tmp_path, change):
    from datetime import datetime, timedelta, timezone

    settings, user, customer, request, store = prepared(tmp_path)
    hub = Hub(settings)
    ops = Operations(store)
    if change == "customer":
        ops.save(
            "customer", {**customer, "notes": "changed"}, user["id"], customer["id"]
        )
    elif change == "hold":
        ops.save(
            "retention_hold",
            {"scope": "workspace", "target_id": "", "status": "active"},
            user["id"],
        )
    elif change == "reviewer":
        value = ops.get("deletion_request", request["id"])
        with hub.connect() as db:
            db.execute(
                "DELETE FROM memberships WHERE user_id=? AND org_id=?",
                (value["approved_by"], user["org_id"]),
            )
    elif change in ("expiry", "state"):
        value = ops.get("deletion_request", request["id"])
        value["expires_at"] = (
            datetime.now(timezone.utc) - timedelta(days=1)
        ).isoformat()
        if change == "state":
            value["status"] = "cancelled"
        ops.save("deletion_request", value, user["id"], request["id"])
    else:
        ops.save(
            "retained_copy",
            {"scope": "workspace", "category": "evidence_export", "status": "retained"},
            user["id"],
        )
    with pytest.raises((ValueError, HTTPException)):
        run(settings, user, request)
    assert Operations(store).get("customer", customer["id"])
    assert not list(settings.deletion_state_directory.glob("*.pending"))


def test_audit_failure_rolls_back_rows_and_blocks_startup_until_proved_abort(
    tmp_path, monkeypatch
):
    settings, user, customer, request, store = prepared(tmp_path)
    original = execution.audit

    def fail(*args):
        raise RuntimeError("Injected audit failure")

    monkeypatch.setattr(execution, "audit", fail)
    with pytest.raises(RuntimeError, match="Injected"):
        run(settings, user, request)
    assert Operations(store).get("customer", customer["id"])
    assert not Operations(store).list("deletion_receipt")
    with pytest.raises(ValueError, match="interrupted deletion"):
        with TestClient(create_app(settings, start_worker=False)):
            pass
    monkeypatch.setattr(execution, "audit", original)
    with pytest.raises(HTTPException):
        execution.reconcile(
            settings, user["org_id"], request["id"], "commit", REASON["reason"]
        )
    outcome = execution.reconcile(
        settings, user["org_id"], request["id"], "abort", REASON["reason"]
    )
    assert outcome["outcome"] == "abort"
    execution.verify_runtime(Hub(settings), settings)
    assert (
        Operations(store).get("deletion_request", request["id"])["status"]
        == "cancelled"
    )
    with pytest.raises(ValueError, match="independently approved"):
        run(settings, user, request)


def test_guard_publication_failure_prevents_any_row_removal(tmp_path, monkeypatch):
    settings, user, customer, request, store = prepared(tmp_path)

    def fail(*args, **kwargs):
        raise OSError("Injected disk publication failure")

    monkeypatch.setattr(execution, "export_guard", fail)
    with pytest.raises(OSError, match="Injected"):
        run(settings, user, request)
    assert Operations(store).get("customer", customer["id"])
    assert not Operations(store).list("deletion_receipt")
    assert not list(settings.deletion_state_directory.glob("*.pending"))


def test_guard_flush_failure_keeps_full_rollback_and_requires_abort(
    tmp_path, monkeypatch
):
    import deletion_guard

    settings, user, customer, request, store = prepared(tmp_path)
    original = deletion_guard.os.fsync

    def fail(*args):
        raise OSError("Injected guard flush failure")

    monkeypatch.setattr(deletion_guard.os, "fsync", fail)
    with pytest.raises(OSError, match="Injected guard flush"):
        run(settings, user, request)
    assert Operations(store).get("customer", customer["id"])
    assert not Operations(store).list("deletion_receipt")
    monkeypatch.setattr(deletion_guard.os, "fsync", original)
    with pytest.raises(ValueError, match="interrupted deletion"):
        execution.verify_runtime(Hub(settings), settings)
    execution.reconcile(
        settings, user["org_id"], request["id"], "abort", REASON["reason"]
    )
    execution.verify_runtime(Hub(settings), settings)


def test_partial_guard_write_cannot_start_execute_export_or_claim_reconciliation(
    tmp_path, monkeypatch
):
    import deletion_guard

    settings, user, customer, request, store = prepared(tmp_path)
    original = deletion_guard.os.fdopen

    class PartialWriter:
        def __init__(self, descriptor, mode):
            self.stream = original(descriptor, mode)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.stream.close()

        def write(self, value):
            self.stream.write(value[: len(value) // 2])
            raise OSError("Injected partial guard write")

    monkeypatch.setattr(deletion_guard.os, "fdopen", PartialWriter)
    with pytest.raises(OSError, match="Injected partial"):
        run(settings, user, request)
    monkeypatch.setattr(deletion_guard.os, "fdopen", original)
    assert Operations(store).get("customer", customer["id"])
    assert not Operations(store).list("deletion_receipt")
    for action in (
        lambda: execution.verify_runtime(Hub(settings), settings),
        lambda: run(settings, user, request),
        lambda: deletion_guard.export_guard(
            settings, tmp_path / "must-not-publish.json"
        ),
    ):
        with pytest.raises(ValueError, match="interrupted deletion"):
            action()
    with pytest.raises(ValueError):
        execution.reconcile(
            settings, user["org_id"], request["id"], "abort", REASON["reason"]
        )
    assert not (tmp_path / "must-not-publish.json").exists()
    assert list(settings.deletion_state_directory.glob("*.pending"))


def test_publication_capacity_failure_retains_pending_and_requires_abort(
    tmp_path, monkeypatch
):
    settings, user, customer, request, store = prepared(tmp_path)
    monkeypatch.setattr(execution, "MAX_STATE_BYTES", 1)
    with pytest.raises(ValueError, match="byte bound"):
        run(settings, user, request)
    assert Operations(store).get("customer", customer["id"])
    assert not Operations(store).list("deletion_receipt")
    monkeypatch.setattr(execution, "MAX_STATE_BYTES", 64 * 1024 * 1024)
    execution.reconcile(
        settings, user["org_id"], request["id"], "abort", REASON["reason"]
    )
    execution.verify_runtime(Hub(settings), settings)


def test_post_commit_interruption_requires_matching_receipt_and_absent_targets(
    tmp_path, monkeypatch
):
    settings, user, customer, request, store = prepared(tmp_path)
    original = execution.complete_file

    def fail(*args):
        raise RuntimeError("Injected publication interruption")

    monkeypatch.setattr(execution, "complete_file", fail)
    with pytest.raises(RuntimeError, match="Injected"):
        run(settings, user, request)
    assert not Operations(store).list("customer")
    assert len(Operations(store).list("deletion_receipt")) == 1
    monkeypatch.setattr(execution, "complete_file", original)
    with pytest.raises(ValueError, match="Cannot abort"):
        execution.reconcile(
            settings, user["org_id"], request["id"], "abort", REASON["reason"]
        )
    result = execution.reconcile(
        settings, user["org_id"], request["id"], "commit", REASON["reason"]
    )
    assert result["outcome"] == "commit"
    execution.verify_runtime(Hub(settings), settings)
    Operations(store).save("customer", customer, user["id"], customer["id"])
    with pytest.raises(ValueError, match="reappeared"):
        execution.verify_runtime(Hub(settings), settings)


def test_missing_tampered_external_state_and_pending_artifacts_block_startup(tmp_path):
    settings, user, _, request, _ = prepared(tmp_path)
    result = run(settings, user, request)
    path = settings.deletion_state_directory / (request["id"] + ".guard")
    original = path.read_bytes()
    path.write_bytes(b"{}")
    with pytest.raises(ValueError):
        execution.verify_runtime(Hub(settings), settings)
    path.write_bytes(original)
    missing_settings = settings.model_copy(
        update={"deletion_state_directory": tmp_path / "empty-state"}
    )
    with pytest.raises(ValueError, match="differ"):
        execution.verify_runtime(Hub(missing_settings), missing_settings)
    with pytest.raises(ValueError, match="original external"):
        execution.verify_runtime(
            Hub(settings),
            settings.model_copy(update={"deletion_state_directory": None}),
        )
    assert result["guard_sha256"]


def test_committed_guard_cannot_be_ignored_by_renaming_it_as_aborted(tmp_path):
    settings, user, _, request, _ = prepared(tmp_path)
    run(settings, user, request)
    guard = settings.deletion_state_directory / (request["id"] + ".guard")
    guard.rename(guard.with_suffix(".aborted"))
    with pytest.raises(ValueError, match="exactly one cancelled"):
        execution.verify_runtime(Hub(settings), settings)


@pytest.mark.parametrize("change", ["filename", "request", "receipt_link"])
def test_aborted_guard_requires_authenticated_identity_and_current_cancelled_request(
    tmp_path, monkeypatch, change
):
    settings, user, _, request, store = prepared(tmp_path)
    original = execution.audit

    def fail(*args, **kwargs):
        raise RuntimeError("Injected transaction rollback")

    monkeypatch.setattr(execution, "audit", fail)
    with pytest.raises(RuntimeError):
        run(settings, user, request)
    monkeypatch.setattr(execution, "audit", original)
    execution.reconcile(
        settings, user["org_id"], request["id"], "abort", REASON["reason"]
    )
    if change == "filename":
        path = settings.deletion_state_directory / (request["id"] + ".aborted")
        path.rename(path.with_name(str(uuid.uuid4()) + ".aborted"))
    else:
        value = Operations(store).get("deletion_request", request["id"])
        if change == "request":
            value["status"] = "approved"
        else:
            value["aborted_execution_receipt_id"] = str(uuid.uuid4())
        Operations(store).save("deletion_request", value, user["id"], request["id"])
    with pytest.raises(ValueError, match="Aborted deletion"):
        execution.verify_runtime(Hub(settings), settings)


def test_executed_deletion_refuses_old_restore_and_retains_receipt_in_new_restore(
    tmp_path,
):
    settings, user, customer, request, _ = prepared(tmp_path)
    create_snapshot(settings, tmp_path / "before")
    result = run(settings, user, request)
    with pytest.raises(ValueError, match="resurrect"):
        restore_snapshot(
            tmp_path / "before",
            tmp_path / "old-restore",
            settings,
            deletion_guard_path=result["guard_path"],
            trusted_guard_sha256=result["guard_sha256"],
        )
    assert not (tmp_path / "old-restore").exists()
    create_snapshot(settings, tmp_path / "after")
    restored = tmp_path / "new-restore"
    restore_snapshot(
        tmp_path / "after",
        restored,
        settings,
        deletion_guard_path=result["guard_path"],
        trusted_guard_sha256=result["guard_sha256"],
    )
    recovered = settings.model_copy(update={"database_path": restored / "workspace.db"})
    with TestClient(create_app(recovered, start_worker=False)) as client:
        assert (
            client.post(
                "/api/auth/login",
                json={
                    "email": "owner@example.invalid",
                    "password": "Test-only-password-2026",
                },
            ).status_code
            == 200
        )
        assert client.get("/api/customers").json() == []
        assert (
            client.get(f"/api/retention/deletion-requests/{request['id']}").json()[
                "receipt"
            ]["customer_id"]
            == customer["id"]
        )


def test_operator_cli_requires_explicit_acknowledgement_and_returns_guard_digest(
    tmp_path, monkeypatch, capsys
):
    import manage

    settings, user, _, request, _ = prepared(tmp_path)
    monkeypatch.setattr(manage, "Settings", lambda: settings)
    arguments = [
        "manage.py",
        "execute-deletion",
        "--workspace",
        user["org_id"],
        "--request",
        request["id"],
        "--reason",
        REASON["reason"],
    ]
    monkeypatch.setattr(sys, "argv", arguments)
    with pytest.raises(SystemExit) as exc:
        manage.main()
    assert exc.value.code == 2
    monkeypatch.setattr(sys, "argv", arguments + ["--acknowledge-retained-data"])
    manage.main()
    result = json.loads(capsys.readouterr().out)
    assert result["deleted_records"] == 1 and len(result["guard_sha256"]) == 64


def test_execution_requires_stopped_encrypted_installation_and_acknowledgement(
    tmp_path,
):
    from runtime import InstallationLock

    settings, user, _, request, _ = prepared(tmp_path)
    with InstallationLock(settings.database_path.parent):
        with pytest.raises(RuntimeError, match="already running"):
            run(settings, user, request)
    with pytest.raises(ValueError, match="SQLCipher"):
        run(settings.model_copy(update={"database_encryption": "none"}), user, request)
    with pytest.raises(ValueError, match="Acknowledge"):
        execution.execute(settings, user["org_id"], request["id"], REASON["reason"])
    with pytest.raises(ValueError, match="Configure"):
        run(
            settings.model_copy(update={"deletion_state_directory": None}),
            user,
            request,
        )
