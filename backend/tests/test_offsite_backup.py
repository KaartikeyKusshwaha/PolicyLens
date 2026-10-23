import hashlib
import io
import json
import tarfile
import secrets
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.fernet import Fernet, InvalidToken
from fastapi.testclient import TestClient

from auth import Hub, Setup
from config import Settings
from operations import Operations
from recovery import create_snapshot, restore_snapshot
from store import Store
from main import create_app
from test_product import add_customer, add_policy
from test_workflows import authenticate
from deploy.export_backup import export_snapshot
from deploy.pull_backup import collect, persist, verify_archive


@pytest.fixture
def snapshot(tmp_path):
    settings = Settings(
        _env_file=None, database_path=tmp_path / "source" / "workspace.db"
    )
    Operations(Store(settings.database_path))
    hub = Hub(settings)
    hub.setup(
        Setup(
            email="backup@example.invalid",
            name="Backup Test",
            password="Test-backup-password-2026",
            workspace="Backup Test Workspace",
            bootstrap_token=hub.bootstrap_file.read_text(),
        )
    )
    root = tmp_path / "server"
    root.mkdir()
    destination = root / "snapshot-20261022T030000Z"
    create_snapshot(settings, destination)
    return root, destination


def rewrite(payload, mutate):
    output = io.BytesIO()
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as original:
        files = {
            member.name: original.extractfile(member).read()
            for member in original.getmembers()
        }
    mutate(files)
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        for name, data in files.items():
            member = tarfile.TarInfo(name)
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
    return output.getvalue()


def test_verified_export_and_encrypted_persistence_never_write_plaintext(
    snapshot, tmp_path
):
    root, _ = snapshot
    payload = export_snapshot(root)
    assert verify_archive(payload)["format"] == 1
    key_file = tmp_path / "private-key"
    key_file.write_bytes(Fernet.generate_key())
    destination = tmp_path / "offsite"
    result = persist(payload, key_file, destination)
    assert result["success"] and result["databases"] == 2
    files = list(destination.iterdir())
    assert len(files) == 1 and files[0].name.endswith(".tar.gz.fernet")
    encrypted = files[0].read_bytes()
    assert b"SQLite format 3" not in encrypted
    recovered = Fernet(key_file.read_bytes()).decrypt(encrypted)
    assert hashlib.sha256(recovered).hexdigest() == result["plaintext_sha256"]
    assert verify_archive(recovered)["files"]
    repeated = persist(payload, key_file, destination)
    assert repeated["archive"] == result["archive"]
    assert len(list(destination.iterdir())) == 1
    with pytest.raises(InvalidToken):
        Fernet(Fernet.generate_key()).decrypt(encrypted)


@pytest.mark.parametrize(
    "mutation",
    [
        "checksum",
        "extra",
        "traversal",
        "duplicate_manifest",
        "stale",
        "future",
        "identity_mapping",
    ],
)
def test_invalid_archive_is_not_saved(snapshot, tmp_path, mutation):
    payload = export_snapshot(snapshot[0])

    def mutate(files):
        manifest = json.loads(files["manifest.json"])
        if mutation == "checksum":
            files["identity.db"] += b"tamper"
        elif mutation == "extra":
            files["unlisted.db"] = b"unlisted"
        elif mutation == "traversal":
            files["../escape"] = b"outside"
        elif mutation == "duplicate_manifest":
            manifest["files"].append(dict(manifest["files"][0]))
        elif mutation in ("stale", "future"):
            offset = timedelta(days=-2 if mutation == "stale" else 2)
            manifest["created_at"] = (datetime.now(timezone.utc) + offset).isoformat()
        else:
            manifest["organization_paths"] = {"wrong-workspace": "workspace.db"}
        files["manifest.json"] = json.dumps(manifest).encode()

    invalid = rewrite(payload, mutate)
    key = tmp_path / "key"
    key.write_bytes(Fernet.generate_key())
    destination = tmp_path / "offsite"
    with pytest.raises(ValueError):
        persist(invalid, key, destination)
    assert not destination.exists()


def test_corrupt_newest_snapshot_does_not_silently_export_an_older_one(snapshot):
    root, _ = snapshot
    newest = root / "snapshot-20261023T030000Z"
    newest.mkdir()
    newest.joinpath("manifest.json").write_text("{}")
    with pytest.raises(ValueError):
        export_snapshot(root)


def test_ssh_collection_requires_verified_host_and_noninteractive_auth(
    tmp_path, monkeypatch
):
    identity = tmp_path / "identity"
    known_hosts = tmp_path / "known_hosts"
    identity.write_text("test placeholder")
    known_hosts.write_text("test placeholder")
    called = []

    def run(command, **options):
        called.append((command, options))
        return type("Result", (), {"returncode": 0, "stdout": b"test archive"})()

    monkeypatch.setattr("deploy.pull_backup.subprocess.run", run)
    assert collect("ubuntu@server.example", identity, known_hosts) == b"test archive"
    command, options = called[0]
    assert "StrictHostKeyChecking=yes" in command and "BatchMode=yes" in command
    assert options["timeout"] == 180 and not options.get("shell")
    import os
    import subprocess

    assert options["creationflags"] == (
        subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    )
    with pytest.raises(ValueError):
        collect("ubuntu@server; command", identity, known_hosts)
    with pytest.raises(ValueError):
        collect("ubuntu@server.example", identity, tmp_path / "missing")


@pytest.fixture
def cipher_snapshot(tmp_path):
    settings = Settings(
        _env_file=None,
        database_path=tmp_path / "source" / "workspace.db",
        security_key_path=tmp_path / "private" / "installation.key",
        database_encryption="sqlcipher4",
    )
    with TestClient(create_app(settings, start_worker=False)) as client:
        identity = authenticate(client)
        policy = add_policy(client)
        add_customer(client, name="Fictional encrypted offsite customer")
        second = client.post(
            "/api/auth/workspaces", json={"name": "Offsite second tenant"}
        ).json()["id"]
    root = tmp_path / "server"
    root.mkdir()
    snapshot = root / "snapshot-20261023T030000Z"
    create_snapshot(settings, snapshot)
    return settings, root, identity["org_id"], second, policy["id"]


def test_sqlcipher_offsite_round_trip_restores_all_tenants_without_plaintext_staging(
    cipher_snapshot, tmp_path, monkeypatch
):
    settings, root, original, second, policy_id = cipher_snapshot
    payload = export_snapshot(root, settings)
    recovery_key = tmp_path / "private-recovery-copy.key"
    recovery_key.write_bytes(settings.security_key_path.read_bytes())
    recovery_key.chmod(0o600)
    import deploy.pull_backup as pull

    original_connect = pull.connect_database
    staged = []

    def inspect(path, config, **options):
        content = path.read_bytes()
        assert not content.startswith(b"SQLite format 3")
        assert b"Fictional encrypted offsite customer" not in content
        assert options["readonly"]
        staged.append(path)
        return original_connect(path, config, **options)

    monkeypatch.setattr(pull, "connect_database", inspect)
    key = tmp_path / "fernet.key"
    key.write_bytes(Fernet.generate_key())
    destination = tmp_path / "offsite"
    result = persist(payload, key, destination, database_key_file=recovery_key)
    assert (
        result["databases"] == 3
        and result["database_encryption"]["scheme"] == "sqlcipher4"
    )
    assert len(list(destination.iterdir())) == 1
    assert len(staged) == 6 and all(not path.exists() for path in staged)
    saved = destination / result["archive"]
    recovered = Fernet(key.read_bytes()).decrypt(saved.read_bytes())
    assert recovered == payload
    manifest = verify_archive(recovered, database_key_file=recovery_key)
    assert (
        persist(payload, key, destination, database_key_file=recovery_key)["archive"]
        == result["archive"]
    )
    # Restore only verified ciphertext files and the manifest into an isolated drill.
    verified = tmp_path / "verified-cipher-snapshot"
    verified.mkdir()
    with tarfile.open(fileobj=io.BytesIO(recovered), mode="r:gz") as archive:
        for name in ["manifest.json", *[item["path"] for item in manifest["files"]]]:
            target = verified / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.extractfile(name).read())
    restored = tmp_path / "restored"
    recovery_settings = settings.model_copy(update={"security_key_path": recovery_key})
    from recovery_helpers import guard_arguments

    restore_snapshot(
        verified, restored, recovery_settings, **guard_arguments(settings, tmp_path)
    )
    restarted = recovery_settings.model_copy(
        update={"database_path": restored / "workspace.db"}
    )
    with TestClient(create_app(restarted, start_worker=False)) as client:
        response = client.post(
            "/api/auth/login",
            json={
                "email": "owner@example.invalid",
                "password": "Test-only-password-2026",
            },
        )
        assert response.status_code == 200
        client.headers["X-CSRF-Token"] = response.json()["csrf"]
        assert {item["id"] for item in client.get("/api/auth/workspaces").json()} == {
            original,
            second,
        }
        assert client.post(f"/api/auth/workspaces/{original}/switch").status_code == 200
        assert (
            client.get("/api/customers").json()[0]["name"]
            == "Fictional encrypted offsite customer"
        )
        assert (
            client.app.state.hub.store(original).search("identity")[0]["policy_id"]
            == policy_id
        )


@pytest.mark.parametrize(
    "mutation",
    ["mode", "fingerprint", "page", "plaintext", "mapping", "wrong_key", "no_key"],
)
def test_sqlcipher_offsite_rejects_downgrade_tampering_and_wrong_keys(
    cipher_snapshot, tmp_path, mutation
):
    settings, root, *_ = cipher_snapshot
    payload = export_snapshot(root, settings)

    def mutate(files):
        manifest = json.loads(files["manifest.json"])
        if mutation == "mode":
            manifest["database_encryption"] = {"scheme": "none"}
        elif mutation == "fingerprint":
            manifest["database_encryption"]["key_fingerprint"] = "0" * 64
        elif mutation in ("page", "plaintext"):
            item = next(
                item for item in manifest["files"] if item["path"] == "identity.db"
            )
            data = bytearray(files[item["path"]])
            if mutation == "page":
                data[4096 + 200] ^= 1
            else:
                data[:16] = b"SQLite format 3\x00"
            files[item["path"]] = bytes(data)
            item["sha256"] = hashlib.sha256(data).hexdigest()
        elif mutation == "mapping":
            manifest["organization_paths"] = {"wrong-tenant": "workspace.db"}
        files["manifest.json"] = json.dumps(manifest).encode()

    payload = rewrite(payload, mutate)
    database_key = settings.security_key_path
    if mutation == "wrong_key":
        database_key = tmp_path / "wrong.key"
        database_key.write_bytes(secrets.token_bytes(32))
        database_key.chmod(0o600)
    elif mutation == "no_key":
        database_key = None
    fernet_key = tmp_path / "fernet.key"
    fernet_key.write_bytes(Fernet.generate_key())
    destination = tmp_path / "must-not-be-created"
    with pytest.raises(ValueError):
        persist(payload, fernet_key, destination, database_key_file=database_key)
    assert not destination.exists()


def test_receiver_rejects_plaintext_when_encrypted_mode_is_selected(snapshot, tmp_path):
    database_key = tmp_path / "installation.key"
    database_key.write_bytes(secrets.token_bytes(32))
    database_key.chmod(0o600)
    with pytest.raises(ValueError, match="encryption mode"):
        verify_archive(export_snapshot(snapshot[0]), database_key_file=database_key)


def test_persist_rejects_keys_inside_archive_destination(snapshot, tmp_path):
    destination = tmp_path / "offsite"
    with pytest.raises(ValueError, match="outside"):
        persist(export_snapshot(snapshot[0]), destination / "key", destination)
    assert not destination.exists()


def test_encrypted_cli_receipt_reports_key_loss_without_erasing_last_success(
    cipher_snapshot, tmp_path, monkeypatch, capsys
):
    import deploy.pull_backup as pull

    settings, root, *_ = cipher_snapshot
    payload = export_snapshot(root, settings)
    key = tmp_path / "fernet.key"
    key.write_bytes(Fernet.generate_key())
    destination = tmp_path / "offsite"
    monkeypatch.setattr(pull, "collect", lambda *args: payload)
    monkeypatch.setattr(
        "sys.argv",
        [
            "pull_backup.py",
            "--host",
            "ubuntu@server.example",
            "--identity",
            str(tmp_path / "ssh.key"),
            "--known-hosts",
            str(tmp_path / "known_hosts"),
            "--key-file",
            str(key),
            "--database-key-file",
            str(settings.security_key_path),
            "--destination",
            str(destination),
        ],
    )
    assert pull.main() == 0
    success = (destination / "last-success.json").read_bytes()
    assert json.loads(success)["database_encryption"]["scheme"] == "sqlcipher4"
    assert json.loads((destination / "last-attempt.json").read_text())["success"]
    settings.security_key_path.rename(settings.security_key_path.with_suffix(".held"))
    assert pull.main() == 1
    assert (destination / "last-success.json").read_bytes() == success
    assert not json.loads((destination / "last-attempt.json").read_text())["success"]
    output = capsys.readouterr()
    assert str(settings.security_key_path) not in output.err
