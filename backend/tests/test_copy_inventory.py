import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import copy_inventory as inventory
from operations import canonical


def roots(tmp_path):
    first, second = tmp_path / "backup-root", tmp_path / "export-root"
    first.mkdir()
    second.mkdir()
    (first / "snapshot.db").write_bytes(b"Synthetic SQLite copy bytes")
    (first / "nested").mkdir()
    (first / "nested" / "copy.zip").write_bytes(b"Synthetic export bytes")
    (second / "copy-again.zip").write_bytes(b"Synthetic export bytes")
    (second / "empty-file").write_bytes(b"")
    return first, second


def test_complete_explicit_root_inventory_hashes_every_file_and_never_changes_sources(
    tmp_path,
):
    selected = roots(tmp_path)
    before = {
        path: path.read_bytes()
        for root in selected
        for path in root.rglob("*")
        if path.is_file()
    }
    output = tmp_path / "discovery.json"
    result = inventory.export(selected, output)
    report = json.loads(output.read_bytes())
    assert result["files"] == 4 and result["directories"] == 3
    assert result["no_files_removed"] and not result["complete_system_discovery_proven"]
    assert result["report_sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
    digest = report.pop("inventory_sha256")
    assert digest == hashlib.sha256(canonical(report).encode()).hexdigest()
    assert report["complete_for_selected_roots"]
    by_name = {item["relative_path"]: item for item in report["files"]}
    assert by_name["nested/copy.zip"]["sha256"] == by_name["copy-again.zip"]["sha256"]
    assert by_name["empty-file"]["bytes"] == 0
    assert all(path.read_bytes() == content for path, content in before.items())
    assert "Synthetic SQLite copy bytes" not in output.read_text()
    assert "No customer-content inspection" in report["limits"]


@pytest.mark.parametrize(
    "bound,value",
    [
        ("MAX_FILES", 1),
        ("MAX_DIRECTORIES", 1),
        ("MAX_FILE_BYTES", 1),
        ("MAX_TOTAL_BYTES", 1),
        ("MAX_DEPTH", 0),
        ("MAX_REPORT_BYTES", 1),
    ],
)
def test_exceeded_complete_inventory_bounds_leave_no_report(
    tmp_path, monkeypatch, bound, value
):
    selected = roots(tmp_path)
    monkeypatch.setattr(inventory, bound, value)
    output = tmp_path / "refused.json"
    with pytest.raises(ValueError):
        inventory.export(selected, output)
    assert not output.exists()


def test_overlapping_roots_existing_output_and_self_inventory_are_refused(tmp_path):
    first, _ = roots(tmp_path)
    for selected in ([first, first], [first, first / "nested"], []):
        with pytest.raises(ValueError):
            inventory.scan(selected)
    with pytest.raises(ValueError, match="outside inventoried"):
        inventory.export([first], first / "report.json")
    output = tmp_path / "existing.json"
    output.write_bytes(b"retain this file")
    with pytest.raises(ValueError, match="new file"):
        inventory.export([first], output)
    assert output.read_bytes() == b"retain this file"


def test_file_changes_after_hashing_invalidate_complete_inventory(
    tmp_path, monkeypatch
):
    first, _ = roots(tmp_path)
    target = first / "snapshot.db"
    original = inventory.safe_stat
    calls = {"target": 0}

    def changed(path, root):
        if path == target:
            calls["target"] += 1
            if calls["target"] == 2:
                target.write_bytes(b"changed after initial hashing")
        return original(path, root)

    monkeypatch.setattr(inventory, "safe_stat", changed)
    with pytest.raises(ValueError, match="input changed"):
        inventory.export([first], tmp_path / "refused.json")
    assert not (tmp_path / "refused.json").exists()


def test_unreadable_directory_is_not_silently_skipped(tmp_path, monkeypatch):
    first, _ = roots(tmp_path)
    original = inventory.os.scandir

    def inaccessible(path):
        if Path(path) == first / "nested":
            raise PermissionError("private unreadable directory")
        return original(path)

    monkeypatch.setattr(inventory.os, "scandir", inaccessible)
    with pytest.raises(PermissionError):
        inventory.export([first], tmp_path / "refused.json")
    assert not (tmp_path / "refused.json").exists()


def test_hard_links_remain_separate_entries_requiring_shared_link_review(tmp_path):
    first, _ = roots(tmp_path)
    alias = first / "hard-linked-copy.db"
    try:
        os.link(first / "snapshot.db", alias)
    except OSError:
        pytest.skip("This filesystem cannot create hard links")
    report = inventory.scan([first])
    copies = [
        row
        for row in report["files"]
        if row["relative_path"] in ("snapshot.db", "hard-linked-copy.db")
    ]
    assert len(copies) == 2 and all(
        row["shared_link_review_required"] for row in copies
    )
    assert copies[0]["sha256"] == copies[1]["sha256"]
    assert alias.is_file() and (first / "snapshot.db").is_file()


def test_symlink_copy_is_refused_without_following_it(tmp_path):
    first, second = roots(tmp_path)
    try:
        (first / "unsafe-link").symlink_to(second, target_is_directory=True)
    except OSError:
        pytest.skip("This OS user cannot create test symlinks")
    with pytest.raises(ValueError, match="redirected paths"):
        inventory.export([first], tmp_path / "refused.json")
    assert not (tmp_path / "refused.json").exists()


def test_actual_operator_cli_reports_hashes_and_generic_private_failure(tmp_path):
    selected = roots(tmp_path)
    script = Path(__file__).resolve().parents[2] / "manage.py"
    output = tmp_path / "cli-report.json"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "copy-inventory",
            "--root",
            str(selected[0]),
            "--root",
            str(selected[1]),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["files"] == 4 and summary["no_files_removed"]
    assert str(selected[0]) not in result.stdout
    failed = subprocess.run(
        [
            sys.executable,
            str(script),
            "copy-inventory",
            "--root",
            str(tmp_path / "private-missing-root"),
            "--output",
            str(tmp_path / "refused.json"),
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert failed.returncode == 1
    assert "Complete copy discovery failed" in failed.stderr
    assert (
        "private-missing-root" not in failed.stderr and "Traceback" not in failed.stderr
    )
    assert not (tmp_path / "refused.json").exists()
