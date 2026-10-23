import os
import shlex
import shutil
import subprocess
import time
from pathlib import Path

import pytest


def bash_path():
    candidate = Path("C:/Program Files/Git/bin/bash.exe")
    if os.name == "nt" and candidate.is_file():
        return str(candidate)
    found = shutil.which("bash")
    if found:
        return found
    pytest.skip("Bash is required for isolated backup-service script tests")


@pytest.mark.parametrize(
    "mode", ["database_only", "combined", "snapshot_failure", "history_failure"]
)
def test_real_backup_shell_preserves_old_snapshots_and_restarts_on_failure(
    tmp_path, mode
):
    repo = Path(__file__).resolve().parents[2]
    script = (repo / "deploy" / "backup.sh").read_text()
    # Redirect only fixed deployment locations into this isolated installation.
    # Actual shell execution covers set -e/trap behavior; no host services run.
    script = script.replace("/var/backups/policylens", "${TEST_BACKUP_ROOT}").replace(
        "cd /opt/policylens", 'cd "$TEST_INSTALL_ROOT"'
    )
    installation = tmp_path / "synthetic-installation"
    python = installation / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text(
        """#!/bin/bash
printf 'python %s\\n' "$*" >> "$TEST_TRACE"
if [[ "$1" == "manage.py" && "$TEST_MODE" == "snapshot_failure" ]]; then exit 31; fi
if [[ "$1" == "deploy/deletion_state_backup.py" && "$TEST_MODE" == "history_failure" ]]; then exit 32; fi
exit 0
""",
        encoding="utf-8",
        newline="\n",
    )
    python.chmod(0o700)
    script_path = tmp_path / "isolated-backup.sh"
    script_path.write_text(script, encoding="utf-8", newline="\n")
    root = tmp_path / "snapshots"
    old = root / "snapshot-20000101T000000Z"
    old.mkdir(parents=True)
    retained = old / "hold-protected-synthetic-record"
    retained.write_text("Retain until independently reviewed removal", encoding="utf-8")
    aged = time.time() - 100 * 86400
    os.utime(old, (aged, aged))
    trace = tmp_path / "trace.txt"
    env = {
        **os.environ,
        "TEST_INSTALL_ROOT": installation.as_posix(),
        "TEST_BACKUP_ROOT": root.as_posix(),
        "TEST_TRACE": trace.as_posix(),
        "TEST_MODE": mode,
        "DELETION_STATE_DIRECTORY": ""
        if mode == "database_only"
        else (tmp_path / "external-state").as_posix(),
    }
    runner = """systemctl() { printf 'systemctl %s\\n' "$*" >> "$TEST_TRACE"; return 0; }
source """ + shlex.quote(script_path.as_posix())
    if os.name == "nt":
        # Unix CI uses real install; Git Bash cannot chmod this Windows test
        # directory. The shell trap/control behavior remains exercised here.
        runner = 'install() { command mkdir -p -- "${@: -1}"; }\n' + runner
    result = subprocess.run(
        [bash_path(), "-c", runner], env=env, capture_output=True, text=True, timeout=15
    )
    assert trace.is_file(), (result.returncode, result.stdout, result.stderr)
    calls = trace.read_text().splitlines()
    assert calls[:2] == [
        "systemctl is-active --quiet policylens",
        "systemctl stop policylens",
    ]
    assert calls[-1] == "systemctl start policylens"
    assert calls.count("systemctl start policylens") == 1
    snapshot = next(
        index
        for index, call in enumerate(calls)
        if call.startswith("python manage.py backup --output ")
    )
    history = [
        index
        for index, call in enumerate(calls)
        if call == "python deploy/deletion_state_backup.py stage"
    ]
    if mode == "database_only":
        assert not history and result.returncode == 0
    elif mode == "snapshot_failure":
        assert not history and result.returncode == 31
    else:
        assert len(history) == 1 and history[0] > snapshot
        assert result.returncode == (32 if mode == "history_failure" else 0)
    assert retained.read_text() == "Retain until independently reviewed removal"
