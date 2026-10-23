import hashlib
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import pytest
from cryptography.fernet import Fernet

from deploy import watchdog
from deploy.export_backup import export_snapshot
from deploy.pull_backup import persist
from test_offsite_backup import snapshot  # noqa: F401


def test_persisted_failure_survives_recovery(tmp_path):
    failure = {
        "schema": watchdog.SCHEMA,
        "healthy": False,
        "checks": [{"code": "disk_below_floor"}],
    }
    recovered = {"schema": watchdog.SCHEMA, "healthy": True, "checks": []}
    watchdog.save_report(tmp_path, failure)
    watchdog.save_report(tmp_path, recovered)
    assert json.loads((tmp_path / "latest.json").read_text()) == recovered
    assert json.loads((tmp_path / "last-failure.json").read_text()) == failure
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "last-failure.json",
        "latest.json",
    ]


def test_report_write_failure_cannot_exit_healthy(tmp_path, monkeypatch):
    monkeypatch.setattr(watchdog, "check", lambda *args, **kwargs: {"healthy": True})
    assert (
        watchdog.main(
            [
                "--origin",
                "https://example.invalid",
                "--offsite-directory",
                str(tmp_path),
                "--disk-path",
                str(tmp_path),
                "--report-directory",
                str(tmp_path / "missing"),
            ]
        )
        == 2
    )


@pytest.fixture
def backup(tmp_path):
    root = tmp_path / "receiver"
    root.mkdir()
    content = b"Synthetic encrypted bytes; unit test does not claim archive decryption"
    name = "policylens-20261023T120000Z-" + "a" * 16 + ".tar.gz.fernet"
    (root / name).write_bytes(content)
    at = datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)
    value = {
        "success": True,
        "completed_at": at.isoformat(),
        "snapshot_created_at": at.isoformat(),
        "archive": name,
        "encrypted_sha256": hashlib.sha256(content).hexdigest(),
        "encrypted_bytes": len(content),
    }
    write_receipts(root, value)
    return root, value, at


def write_receipts(root, value):
    for name in ("last-attempt.json", "last-success.json"):
        (root / name).write_text(json.dumps(value), encoding="utf-8")


@pytest.mark.parametrize("kind", ["deletion_state", "checkpoint_history"])
@pytest.mark.parametrize(
    "change",
    [
        "healthy",
        "missing",
        "changed",
        "stale",
        "failed_latest",
        "mismatched_receipt",
        "missing_metadata",
        "unsafe_name",
        "wrong_identity",
    ],
)
def test_configured_history_checks_refuse_lost_changed_or_stale_copies(
    backup, tmp_path, kind, change
):
    root, value, at = backup
    directory = tmp_path / "private-history"
    directory.mkdir()
    prefix = "deletion-state" if kind == "deletion_state" else "checkpoint-history"
    name = prefix + "-" + "b" * 64 + ".fernet"
    content = b"Synthetic encrypted history bytes"
    path = directory / name
    path.write_bytes(content)
    metadata = {
        "success": True,
        "source_created_at": at.isoformat(),
        "archive": name,
        "bundle_sha256": "b" * 64,
        "encrypted_sha256": hashlib.sha256(content).hexdigest(),
        "encrypted_bytes": len(content),
    }
    value[kind] = metadata
    if change == "missing":
        path.rename(directory / "held")
    elif change == "changed":
        path.write_bytes(b"X" + content[1:])
    elif change == "stale":
        metadata["source_created_at"] = (at - timedelta(hours=31)).isoformat()
    elif change == "missing_metadata":
        metadata.pop("encrypted_sha256")
    elif change == "unsafe_name":
        metadata["archive"] = "../private-secret"
    elif change == "wrong_identity":
        metadata["bundle_sha256"] = "c" * 64
    write_receipts(root, value)
    if change == "failed_latest":
        (root / "last-attempt.json").write_text(
            json.dumps({"success": False}), encoding="utf-8"
        )
    elif change == "mismatched_receipt":
        altered = {**value, kind: {**metadata, "bundle_sha256": "d" * 64}}
        (root / "last-attempt.json").write_text(json.dumps(altered), encoding="utf-8")
    options = {
        "deletion_state_directory"
        if kind == "deletion_state"
        else "checkpoint_directory": directory
    }
    report = watchdog.check(
        "https://pilot.example.invalid",
        root,
        root,
        min_free_bytes=1,
        at=at,
        transport=httpx.MockTransport(ready),
        **options,
    )
    check = next(item for item in report["checks"] if item["name"] == kind + "_backup")
    assert check["healthy"] is (change == "healthy")
    assert report["healthy"] is (change == "healthy")
    assert "private-secret" not in json.dumps(report) and str(
        directory
    ) not in json.dumps(report)


def ready(request):
    assert str(request.url) == "https://pilot.example.invalid/api/ready"
    assert "authorization" not in request.headers
    return httpx.Response(200, json={"status": "ready"})


def run(backup, transport=None):
    root, _, at = backup
    return watchdog.check(
        "https://pilot.example.invalid",
        root,
        root,
        min_free_bytes=1,
        transport=httpx.MockTransport(transport or ready),
        at=at,
    )


def test_healthy_checks_do_not_change_files_or_send_notifications(backup):
    root, _, _ = backup
    before = {path.name: path.read_bytes() for path in root.iterdir()}
    result = run(backup)
    assert result["healthy"]
    assert all(item["healthy"] for item in result["checks"])
    assert "Does not decrypt" in result["scope"]
    assert {path.name: path.read_bytes() for path in root.iterdir()} == before


@pytest.mark.parametrize(
    "mode", ["503", "redirect", "html", "wrong_status", "oversized", "timeout"]
)
def test_readiness_failure_still_runs_backup_and_disk_checks(backup, mode):
    def handler(request):
        if mode == "timeout":
            raise httpx.ReadTimeout(
                "Sensitive internal URL must not appear", request=request
            )
        if mode == "503":
            return httpx.Response(503, json={"status": "not_ready"})
        if mode == "redirect":
            return httpx.Response(
                302, headers={"location": "https://untrusted.invalid/secret"}
            )
        if mode == "html":
            return httpx.Response(200, text="login form, not readiness")
        if mode == "oversized":
            return httpx.Response(200, content=b"x" * 5000)
        return httpx.Response(200, json={"status": "ok"})

    result = run(backup, handler)
    assert not result["healthy"] and len(result["checks"]) == 3
    assert not result["checks"][0]["healthy"]
    assert result["checks"][1]["healthy"] and result["checks"][2]["healthy"]
    assert "secret" not in json.dumps(result) and "Sensitive" not in json.dumps(result)


@pytest.mark.parametrize(
    "change",
    [
        "stale_completion",
        "stale_snapshot",
        "naive",
        "future",
        "failed_attempt",
        "missing_receipt",
        "mismatched_attempt",
        "traversal",
        "missing_archive",
        "changed_bytes",
        "missing_digest",
        "oversized_receipt",
        "nonobject",
        "boolean_size",
    ],
)
def test_backup_failures_refuse_healthy_status_without_echoing_metadata(backup, change):
    root, value, at = backup
    if change == "stale_completion":
        value["completed_at"] = (at - timedelta(hours=31)).isoformat()
    elif change == "stale_snapshot":
        value["snapshot_created_at"] = (at - timedelta(hours=31)).isoformat()
    elif change == "naive":
        value["completed_at"] = "2026-10-23T12:00:00"
    elif change == "future":
        value["completed_at"] = (at + timedelta(hours=1)).isoformat()
    elif change == "traversal":
        value["archive"] = "../private-secret"
    elif change == "missing_digest":
        value.pop("encrypted_sha256")
    elif change == "boolean_size":
        value["encrypted_bytes"] = True
    write_receipts(root, value)
    if change == "failed_attempt":
        (root / "last-attempt.json").write_text(
            json.dumps({"success": False, "error": "Private provider error"}),
            encoding="utf-8",
        )
    elif change == "missing_receipt":
        (root / "last-attempt.json").rename(root / "held-receipt")
    elif change == "mismatched_attempt":
        (root / "last-attempt.json").write_text(
            json.dumps(
                {**value, "completed_at": (at + timedelta(seconds=1)).isoformat()}
            ),
            encoding="utf-8",
        )
    elif change == "missing_archive":
        (root / value["archive"]).rename(root / "held-archive")
    elif change == "changed_bytes":
        data = (root / value["archive"]).read_bytes()
        (root / value["archive"]).write_bytes(b"X" + data[1:])
    elif change == "oversized_receipt":
        (root / "last-success.json").write_bytes(
            b"x" * (watchdog.MAX_RECEIPT_BYTES + 1)
        )
    elif change == "nonobject":
        (root / "last-success.json").write_text("[]", encoding="utf-8")
    result = run(backup)
    assert not result["healthy"] and not result["checks"][1]["healthy"]
    text = json.dumps(result)
    assert "private-secret" not in text and "Private provider error" not in text


def test_disk_floor_failure_and_missing_path_are_reported(backup, monkeypatch):
    monkeypatch.setattr(
        watchdog.shutil, "disk_usage", lambda path: SimpleNamespace(free=0)
    )
    assert run(backup)["checks"][2]["code"] == "disk_below_floor"

    def fail(path):
        raise OSError("Private filesystem path")

    monkeypatch.setattr(watchdog.shutil, "disk_usage", fail)
    result = run(backup)
    assert result["checks"][2]["code"] == "disk_path_unavailable"
    assert "Private filesystem" not in json.dumps(result)


@pytest.mark.parametrize(
    "origin",
    [
        "http://public.example.invalid",
        "https://user:secret@example.invalid",
        "https://example.invalid/login",
        "https://example.invalid?token=secret",
        "https://example.invalid#secret",
        "https://example.invalid:bad",
        "file:///secret",
    ],
)
def test_unsafe_origin_is_rejected_without_network_requests(origin):
    with pytest.raises(ValueError):
        watchdog.origin_url(origin)


@pytest.mark.parametrize(
    "origin",
    [
        "http://127.0.0.1:8000",
        "http://[::1]:8000",
        "http://localhost:8000",
        "https://pilot.example.invalid/",
    ],
)
def test_https_and_loopback_origins_have_fixed_readiness_path(origin):
    assert watchdog.origin_url(origin).endswith("/api/ready")


def test_real_backup_persistence_emits_matching_ciphertext_metadata(snapshot, tmp_path):  # noqa: F811
    root, _ = snapshot
    key = tmp_path / "private-key"
    key.write_bytes(Fernet.generate_key())
    destination = tmp_path / "offsite"
    result = persist(export_snapshot(root), key, destination)
    write_receipts(destination, result)
    content = (destination / result["archive"]).read_bytes()
    assert result["encrypted_sha256"] == hashlib.sha256(content).hexdigest()
    assert result["encrypted_bytes"] == len(content)
    assert watchdog.backup_check(destination, datetime.now(timezone.utc), 30)["healthy"]


def test_cli_exit_code_is_nonzero_on_failure_and_output_omits_user_paths(
    backup, monkeypatch, capsys
):
    root, _, _ = backup
    expected = run(backup)
    monkeypatch.setattr(watchdog, "check", lambda *args, **kwargs: expected)
    arguments = [
        "--origin",
        "https://pilot.example.invalid",
        "--offsite-directory",
        str(root),
        "--disk-path",
        str(root),
    ]
    assert watchdog.main(arguments) == 0
    assert json.loads(capsys.readouterr().out)["healthy"]
    expected["healthy"] = False
    assert watchdog.main(arguments) == 1
    assert str(root) not in capsys.readouterr().out

    def invalid(*args, **kwargs):
        raise ValueError("private configuration")

    monkeypatch.setattr(watchdog, "check", invalid)
    assert watchdog.main(arguments) == 1
    assert "private configuration" not in capsys.readouterr().out


@pytest.mark.parametrize("target", ["receipt", "archive", "directory"])
def test_redirected_backup_paths_cannot_pass_checks(backup, tmp_path, target):
    root, value, at = backup
    try:
        if target == "directory":
            link = tmp_path / "redirected-directory"
            link.symlink_to(root, target_is_directory=True)
            result = watchdog.backup_check(link, at, 30)
        else:
            path = root / (
                "last-success.json" if target == "receipt" else value["archive"]
            )
            held = tmp_path / "held-file"
            path.rename(held)
            path.symlink_to(held)
            result = watchdog.backup_check(root, at, 30)
    except OSError:
        pytest.skip("This OS user cannot create test symlinks")
    assert not result["healthy"]


def test_real_operator_script_refuses_invalid_configuration_without_network_or_traceback(
    tmp_path,
):
    script = Path(__file__).resolve().parents[2] / "deploy" / "watchdog.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--origin",
            "https://user:private-secret@example.invalid",
            "--offsite-directory",
            str(tmp_path),
            "--disk-path",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert (
        not report["healthy"]
        and report["checks"][0]["code"] == "watchdog_configuration_invalid"
    )
    assert "private-secret" not in result.stdout + result.stderr
    assert "Traceback" not in result.stdout + result.stderr
