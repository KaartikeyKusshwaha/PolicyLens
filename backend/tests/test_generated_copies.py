import hashlib
import io
import json
import uuid
import zipfile
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

import product_api
import retained_copies
from config import Settings
from main import create_app
from operations import canonical
from providers import problem
from recovery import checksum, create_snapshot, restore_snapshot
from test_evidence import setup_pack
from test_deletion import approved
from test_product import add_customer, member, acting_as
from test_retention import REVIEW
from test_toolkit import case, key, call
from test_workflows import authenticate


def copies(client):
    response = client.get("/api/retention")
    assert response.status_code == 200, response.text
    return response.json()["copies"]


def test_sponsor_pack_tracks_exact_bytes_and_prior_custody_in_next_signed_snapshot(
    workspace, tmp_path
):
    client, _, manager, org = setup_pack(workspace, tmp_path)
    first = client.get("/api/evidence/sponsor-pack")
    assert first.status_code == 200
    custody = copies(client)[0]
    assert first.headers["X-PolicyLens-Custody-ID"] == custody["id"]
    assert custody["content_sha256"] == hashlib.sha256(first.content).hexdigest()
    assert custody["content_bytes"] == len(first.content)
    assert custody["registered_policy_id"] is None and custody["preserve_until"] is None
    assert custody["generation_status"] == "complete"
    second = client.get("/api/evidence/sponsor-pack")
    assert second.status_code == 200
    with zipfile.ZipFile(io.BytesIO(second.content)) as archive:
        evidence = json.loads(archive.read("evidence.json"))
        assert evidence["records"]["retained_copy"][0]["id"] == custody["id"]
        assert b"content_sha256" in archive.read("evidence.json")
        (tmp_path / "custody-report.pdf").write_bytes(archive.read("report.pdf"))
    with zipfile.ZipFile(io.BytesIO(first.content)) as archive:
        bundle = json.loads(archive.read("audit.json"))
        assert not any(
            event["data"].get("id") == custody["id"] for event in bundle["events"]
        )
    from verify_evidence_pack import verify_pack

    assert verify_pack(second.content, manager.status(org)["fingerprint"])["valid"]


@pytest.mark.parametrize(
    "endpoint", ["/api/audit/export", "/api/audit/checkpoints/export"]
)
def test_audit_downloads_track_exact_response_bytes(workspace, tmp_path, endpoint):
    client, *_ = setup_pack(workspace, tmp_path)
    response = client.get(endpoint)
    assert response.status_code == 200
    custody = copies(client)[0]
    assert custody["content_sha256"] == hashlib.sha256(response.content).hexdigest()
    assert custody["category"] == "audit_checkpoint"
    assert custody["hash_encoding"] == "file-bytes"
    assert response.headers["X-PolicyLens-Custody-ID"] == custody["id"]


def test_case_view_is_not_a_download_but_case_export_tracks_customer_scope(workspace):
    client, *_ = workspace
    customer, investigation = case(client)
    assert client.get(f"/api/cases/{investigation['id']}").status_code == 200
    assert copies(client) == []
    response = client.get(f"/api/cases/{investigation['id']}/export")
    assert response.status_code == 200
    custody = copies(client)[0]
    assert custody["scope"] == "customer" and custody["target_id"] == customer["id"]
    assert custody["content_sha256"] == hashlib.sha256(response.content).hexdigest()


def test_toolkit_export_hashes_masked_result_not_unmasked_context(workspace):
    client, *_ = workspace
    customer, investigation = case(client, name="Fictional private export marker")
    credential = key(
        client, scopes=["export_case_pack", "get_case_context"], pseudonymize=True
    )
    assert (
        call(
            client, credential, "get_case_context", case_id=investigation["id"]
        ).status_code
        == 200
    )
    assert copies(client) == []
    response = call(client, credential, "export_case_pack", case_id=investigation["id"])
    assert response.status_code == 200
    assert customer["name"] not in response.text
    custody = copies(client)[0]
    assert custody["hash_encoding"] == "canonical-json-tool-result"
    assert (
        custody["content_sha256"]
        == hashlib.sha256(canonical(response.json()).encode()).hexdigest()
    )
    assert custody["target_id"] == customer["id"]
    assert custody["custodian"].startswith("agent:")


def test_workspace_backup_reserves_local_custody_and_tracks_each_download(workspace):
    client, *_ = workspace
    add_customer(client)
    response = client.post("/api/backups")
    assert response.status_code == 201, response.text
    local = copies(client)[0]
    assert response.json()["custody_id"] == local["id"]
    assert local["generation_status"] == "complete"
    downloaded = client.get(response.json()["download_url"])
    assert downloaded.status_code == 200
    all_copies = copies(client)
    assert len(all_copies) == 2
    assert downloaded.headers["X-PolicyLens-Custody-ID"] != local["id"]
    assert all(
        copy["content_sha256"] == hashlib.sha256(downloaded.content).hexdigest()
        for copy in all_copies
    )


@pytest.mark.parametrize(
    "endpoint", ["/api/evidence/sponsor-pack", "/api/audit/export", "/api/backups"]
)
def test_full_copy_register_refuses_untracked_export_or_durable_backup(
    workspace, tmp_path, monkeypatch, endpoint
):
    client, *_ = setup_pack(workspace, tmp_path)
    monkeypatch.setattr(retained_copies, "MAX_COPIES", 0)
    response = (
        client.post(endpoint) if endpoint == "/api/backups" else client.get(endpoint)
    )
    assert response.status_code == 422
    assert not response.content.startswith(b"PK")
    assert copies(client) == []
    store = client.app.state.hub.store(client.get("/api/auth/me").json()["org_id"])
    assert not list((store.path.parent / "backups").glob("*.db"))


def test_auditor_export_records_delivery_intent_without_gaining_custody_mutations(
    workspace, tmp_path
):
    client, *_ = setup_pack(workspace, tmp_path)
    auditor = member(client, "auditor")
    with acting_as(client, auditor):
        response = client.get("/api/evidence/sponsor-pack")
        assert response.status_code == 200
        copy = copies(client)[0]
        assert copy["custodian"] == auditor["user"]["id"]
        assert (
            client.post(
                f"/api/retention/copies/{copy['id']}/request-removal", json=REVIEW
            ).status_code
            == 403
        )


def test_failed_backup_stays_tracked_and_admin_inspection_hashes_only_local_artifact(
    workspace, monkeypatch
):
    client, *_ = workspace
    original = product_api.verify_database_integrity

    def fail(*args):
        raise problem(409, "injected_failure", "Injected backup verification failure.")

    monkeypatch.setattr(product_api, "verify_database_integrity", fail)
    assert client.post("/api/backups").status_code == 409
    failed = copies(client)[0]
    assert failed["generation_status"] == "failed_unknown"
    assert failed["content_sha256"] is None
    monkeypatch.setattr(product_api, "verify_database_integrity", original)
    response = client.post(
        f"/api/retention/copies/{failed['id']}/inspect-backup", json=REVIEW
    )
    assert response.status_code == 200, response.text
    assert response.json()["generation_status"] == "reconciled_present"
    assert (
        response.json()["content_sha256"] and response.json()["generation_observed_at"]
    )


def test_missing_pending_backup_can_be_observed_without_recreating_it(workspace):
    client, *_ = workspace
    user = client.get("/api/auth/me").json()
    store = client.app.state.hub.store(user["org_id"])
    identifier = str(uuid.uuid4())
    copy = retained_copies.reserve_generated(
        store,
        user,
        category="backup",
        location_reference="workspace-backup:" + identifier,
        storage_root=str(store.path.parent.resolve()),
    )
    response = client.post(
        f"/api/retention/copies/{copy['id']}/inspect-backup", json=REVIEW
    )
    assert response.status_code == 200
    assert response.json()["generation_status"] == "observed_missing"
    assert not (store.path.parent / "backups" / (identifier + ".db")).exists()


def test_restored_installation_cannot_treat_local_absence_as_origin_copy_removal(
    tmp_path, monkeypatch
):
    settings = Settings(
        _env_file=None,
        database_path=tmp_path / "original" / "workspace.db",
        database_encryption="sqlcipher4",
        security_key_path=tmp_path / "private" / "installation.key",
    )
    original_verifier = product_api.verify_database_integrity
    with TestClient(create_app(settings, start_worker=False)) as client:
        authenticate(client)

        def fail(*args):
            raise problem(
                409, "injected_failure", "Injected backup verification failure."
            )

        monkeypatch.setattr(product_api, "verify_database_integrity", fail)
        assert client.post("/api/backups").status_code == 409
        failed = copies(client)[0]
        origin = next((settings.database_path.parent / "backups").glob("*.db"))
        before = checksum(origin)
    monkeypatch.setattr(product_api, "verify_database_integrity", original_verifier)
    create_snapshot(settings, tmp_path / "snapshot")
    from recovery_helpers import guard_arguments

    restore_snapshot(
        tmp_path / "snapshot",
        tmp_path / "restored",
        settings,
        **guard_arguments(settings, tmp_path),
    )
    recovered = settings.model_copy(
        update={"database_path": tmp_path / "restored" / "workspace.db"}
    )
    with TestClient(create_app(recovered, start_worker=False)) as client:
        response = client.post(
            "/api/auth/login",
            json={
                "email": "owner@example.invalid",
                "password": "Test-only-password-2026",
            },
        )
        assert response.status_code == 200
        client.headers["X-CSRF-Token"] = response.json()["csrf"]
        assert (
            client.post(
                f"/api/retention/copies/{failed['id']}/inspect-backup", json=REVIEW
            ).status_code
            == 409
        )
    assert checksum(origin) == before


def test_changed_backup_is_refused_and_failed_download_remains_tracked(workspace):
    client, *_ = workspace
    generated = client.post("/api/backups")
    assert generated.status_code == 201
    store = client.app.state.hub.store(client.get("/api/auth/me").json()["org_id"])
    path = store.path.parent / "backups" / generated.json()["file"]
    with path.open("ab") as file:
        file.write(b"fictional backup tamper marker")
    response = client.get(generated.json()["download_url"])
    assert response.status_code == 409
    assert any(copy["generation_status"] == "failed_unknown" for copy in copies(client))


def test_unassigned_generated_copy_uses_later_policy_and_new_copies_pin_floor(
    workspace,
):
    client, *_ = workspace
    _, investigation = case(client)
    assert client.get(f"/api/cases/{investigation['id']}/export").status_code == 200
    first = copies(client)[0]
    assert first["registered_policy_id"] is None
    policy = approved(client)
    denied = client.post(
        f"/api/retention/copies/{first['id']}/request-removal", json=REVIEW
    )
    assert denied.status_code == 409
    assert denied.json()["detail"]["code"] == "retention_copy_not_due"
    assert client.get(f"/api/cases/{investigation['id']}/export").status_code == 200
    assigned = next(
        copy for copy in copies(client) if copy["registered_policy_id"] == policy["id"]
    )
    assert datetime.fromisoformat(assigned["preserve_until"]) >= datetime.fromisoformat(
        assigned["copy_created_at"]
    ) + timedelta(days=policy["audit_minimum_days"])


@pytest.mark.parametrize(
    "reference",
    [
        "workspace-backup:../outside",
        "https://example.invalid/private.db",
        "workspace-backup:not-a-uuid",
    ],
)
def test_generated_backup_inspection_never_follows_arbitrary_location_references(
    workspace, monkeypatch, reference
):
    client, *_ = workspace
    user = client.get("/api/auth/me").json()
    store = client.app.state.hub.store(user["org_id"])
    copy = retained_copies.reserve_generated(
        store,
        user,
        category="backup",
        location_reference=reference,
        storage_root=str(store.path.parent.resolve()),
    )
    called = []
    monkeypatch.setattr(retained_copies, "integrity", lambda *args: called.append(args))
    assert (
        client.post(
            f"/api/retention/copies/{copy['id']}/inspect-backup", json=REVIEW
        ).status_code
        == 409
    )
    assert not called
