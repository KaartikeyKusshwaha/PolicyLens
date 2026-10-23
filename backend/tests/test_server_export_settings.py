import os
import stat
from types import SimpleNamespace

import pytest

from deploy.server_settings import load_server_settings


def test_export_loads_private_environment_without_systemd_environment(
    tmp_path, monkeypatch
):
    from pathlib import Path

    path = tmp_path / "server.env"
    path.write_text(
        "DATABASE_PATH=/var/lib/policylens/encrypted/workspace.db\nDATABASE_ENCRYPTION=sqlcipher4\nSECURITY_KEY_PATH=/etc/policylens-secrets/installation.key\nCHECKPOINT_DIRECTORY=/var/lib/policylens-checkpoints\nDELETION_STATE_DIRECTORY=/var/lib/policylens-deletion-state\n"
    )
    path.chmod(0o600)
    if os.name != "nt":
        original = Path.lstat

        def owned(target):
            info = original(target)
            if target == path:
                return SimpleNamespace(st_mode=info.st_mode, st_uid=0)
            return info

        monkeypatch.setattr(Path, "lstat", owned)
    for key in (
        "DATABASE_PATH",
        "DATABASE_ENCRYPTION",
        "SECURITY_KEY_PATH",
        "CHECKPOINT_DIRECTORY",
        "DELETION_STATE_DIRECTORY",
    ):
        monkeypatch.delenv(key, raising=False)
    settings = load_server_settings(path)
    assert settings.database_encryption == "sqlcipher4"
    assert (
        settings.database_path.as_posix()
        == "/var/lib/policylens/encrypted/workspace.db"
    )
    assert settings.checkpoint_directory.as_posix() == "/var/lib/policylens-checkpoints"
    assert (
        settings.deletion_state_directory.as_posix()
        == "/var/lib/policylens-deletion-state"
    )


def test_export_refuses_missing_or_nonregular_environment(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_server_settings(tmp_path / "missing.env")
    with pytest.raises(ValueError):
        load_server_settings(tmp_path)


@pytest.mark.skipif(os.name == "nt", reason="POSIX ownership/mode rules")
@pytest.mark.parametrize(
    "mode,uid", [(stat.S_IFREG | 0o644, 0), (stat.S_IFREG | 0o600, 1000)]
)
def test_export_refuses_untrusted_environment_ownership(
    tmp_path, monkeypatch, mode, uid
):
    from pathlib import Path

    path = tmp_path / "server.env"
    path.write_text("DATABASE_ENCRYPTION=sqlcipher4\n")
    monkeypatch.setattr(
        Path, "lstat", lambda self: SimpleNamespace(st_mode=mode, st_uid=uid)
    )
    with pytest.raises(ValueError):
        load_server_settings(path)
