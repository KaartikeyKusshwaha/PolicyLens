import copy
import json

import pytest
from fastapi.testclient import TestClient

from config import Settings
from main import create_app
from recovery import create_snapshot, restore_snapshot, verify_snapshot
from snapshot_mapping import verify_workspace_mapping
from test_workflows import authenticate
from test_offsite_backup import rewrite
from deploy.export_backup import export_snapshot
from deploy.pull_backup import verify_archive


def manifest():
    return {
        "organization_paths": {"one": "workspace.db", "two": "workspaces/two.db"},
        "files": [
            {"path": name}
            for name in ("identity.db", "workspace.db", "workspaces/two.db")
        ],
    }


@pytest.mark.parametrize("root", ["/var/lib/policylens", "C:/Private/PolicyLens"])
def test_mapping_matches_original_identity_on_both_operating_systems(root):
    verify_workspace_mapping(
        manifest(),
        [("one", root + "/workspace.db"), ("two", root + "/workspaces/two.db")],
    )


@pytest.mark.parametrize(
    "mutation",
    ["swap", "duplicate", "identity", "extra", "root", "relative", "traversal"],
)
def test_mapping_refuses_mixed_tenants_and_ambiguous_files(mutation):
    value = copy.deepcopy(manifest())
    organizations = [("one", "/data/workspace.db"), ("two", "/data/workspaces/two.db")]
    if mutation == "swap":
        value["organization_paths"] = {
            "two": "workspace.db",
            "one": "workspaces/two.db",
        }
    elif mutation == "duplicate":
        value["organization_paths"]["two"] = "workspace.db"
    elif mutation == "identity":
        value["organization_paths"]["two"] = "identity.db"
    elif mutation == "extra":
        value["files"].append({"path": "unregistered.db"})
    elif mutation == "root":
        organizations[1] = ("two", "/other/workspaces/two.db")
    elif mutation == "relative":
        organizations[1] = ("two", "workspaces/two.db")
    else:
        value["organization_paths"]["two"] = "../two.db"
        value["files"][2]["path"] = "../two.db"
    with pytest.raises(ValueError):
        verify_workspace_mapping(value, organizations)


@pytest.mark.parametrize("encryption", ["none", "sqlcipher4"])
def test_swapped_tenant_mapping_refused_by_restore_and_offsite_verifier(
    tmp_path, encryption
):
    settings = Settings(
        _env_file=None,
        database_path=tmp_path / "source" / "workspace.db",
        security_key_path=tmp_path / "private" / "key",
        database_encryption=encryption,
    )
    with TestClient(create_app(settings, start_worker=False)) as client:
        user = authenticate(client)
        second = client.post(
            "/api/auth/workspaces", json={"name": "Mapping isolation"}
        ).json()["id"]
    backup_root = tmp_path / "backups"
    backup_root.mkdir()
    backup = backup_root / "snapshot-20261023T120000Z"
    value = create_snapshot(settings, backup)
    archive = export_snapshot(backup_root, settings)
    value["organization_paths"][user["org_id"]], value["organization_paths"][second] = (
        value["organization_paths"][second],
        value["organization_paths"][user["org_id"]],
    )
    (backup / "manifest.json").write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError, match="workspace mapping"):
        verify_snapshot(backup, settings)
    with pytest.raises(ValueError, match="workspace mapping"):
        restore_snapshot(backup, tmp_path / "refused", settings)
    assert not (tmp_path / "refused").exists()
    with pytest.raises(ValueError, match="workspace mapping"):
        export_snapshot(backup_root, settings)

    def alter_mapping(files):
        files["manifest.json"] = json.dumps(value).encode()

    archive = rewrite(archive, alter_mapping)
    with pytest.raises(ValueError, match="workspace mapping"):
        verify_archive(
            archive,
            database_key_file=settings.security_key_path
            if encryption != "none"
            else None,
        )
