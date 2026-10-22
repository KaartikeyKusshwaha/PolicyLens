import hashlib
import io
import json
import tarfile
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.fernet import Fernet, InvalidToken

from auth import Hub, Setup
from config import Settings
from operations import Operations
from recovery import create_snapshot
from store import Store
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
    with pytest.raises(ValueError):
        collect("ubuntu@server; command", identity, known_hosts)
    with pytest.raises(ValueError):
        collect("ubuntu@server.example", identity, tmp_path / "missing")
