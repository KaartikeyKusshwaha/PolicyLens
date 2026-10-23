import copy
import hashlib
import json
from pathlib import Path

import pytest

from evaluation import pilot_load


def test_percentiles_keep_failures_and_do_not_average_endpoint_tail_latencies():
    samples = [("POST ingest", value, 201) for value in range(1, 101)] + [
        ("GET cases", 6000, 503)
    ]
    summary = pilot_load.latency_summary(samples)
    assert summary["POST ingest"]["p95_ms"] == 95
    assert summary["GET cases"]["p95_ms"] == 6000
    assert summary["GET cases"]["http_statuses"] == {"503": 1}
    report = {
        "invariants": {"count": True},
        "request_failures": 0,
        "latencies": summary,
        "evidence_pack_seconds": 1,
        "evidence_pack_verified": True,
        "server_stopped": True,
    }
    assert not pilot_load.gate(report, 2000)["passed"]


@pytest.mark.parametrize(
    "failure",
    [
        "invariant",
        "request",
        "tail",
        "pack_time",
        "pack_signature",
        "shutdown",
        "empty",
    ],
)
def test_every_release_gate_condition_is_required(failure):
    report = {
        "invariants": {"count": True},
        "request_failures": 0,
        "latencies": {"GET cases": {"p95_ms": 10}},
        "evidence_pack_seconds": 1,
        "evidence_pack_verified": True,
        "server_stopped": True,
    }
    assert pilot_load.gate(report, 2000)["passed"]
    changed = copy.deepcopy(report)
    if failure == "invariant":
        changed["invariants"]["count"] = False
    elif failure == "request":
        changed["request_failures"] = 1
    elif failure == "tail":
        changed["latencies"]["GET cases"]["p95_ms"] = 2001
    elif failure == "pack_time":
        changed["evidence_pack_seconds"] = 61
    elif failure == "pack_signature":
        changed["evidence_pack_verified"] = False
    elif failure == "shutdown":
        changed["server_stopped"] = False
    else:
        changed["invariants"] = {}
    assert not pilot_load.gate(changed, 2000)["passed"]


def test_existing_output_and_out_of_bounds_profiles_do_not_start_or_modify_data(
    tmp_path,
):
    existing = tmp_path / "existing"
    existing.mkdir()
    marker = existing / "user-file"
    marker.write_text("Retain existing files", encoding="utf-8")
    with pytest.raises(FileExistsError):
        pilot_load.run(
            existing, customers=1, transactions=1, concurrency=1, read_rounds=1
        )
    assert marker.read_text() == "Retain existing files"
    for values in (
        {"customers": 2001},
        {"transactions": 10001},
        {"concurrency": 17},
        {"read_rounds": 101},
        {"p95_ms": 0},
    ):
        with pytest.raises(ValueError):
            pilot_load.run(tmp_path / "must-not-exist", **values)
        assert not (tmp_path / "must-not-exist").exists()


def test_real_separate_single_worker_http_smoke_verifies_counts_isolation_and_pack(
    tmp_path,
):
    directory = tmp_path / "isolated-http"
    report = pilot_load.run(
        directory,
        customers=4,
        transactions=8,
        concurrency=2,
        read_rounds=1,
        p95_ms=60000,
    )
    assert report["gate"]["passed"], report
    assert all(value is True for value in report["invariants"].values())
    assert report["latencies"]["POST /api/monitor/transactions"]["http_statuses"] == {
        "201": 16
    }
    assert report["request_failures"] == 0
    assert (
        report["evidence_pack_verified"]
        and (directory / "synthetic-evidence.zip").is_file()
    )
    assert report["configuration"]["database_encryption"] == "sqlcipher4"
    assert report["environment"]["oracle_vm_proven"] is False
    assert report["server_stopped"]
    retained = json.loads((directory / "report.json").read_text())
    digest = retained.pop("report_sha256")
    assert (
        hashlib.sha256(
            json.dumps(retained, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        == digest
    )
    assert "csrf" not in json.dumps(report).lower()
    assert "load-owner@example.invalid" not in json.dumps(report)


def test_retained_synthetic_reports_keep_original_failure_and_recomputable_gates():
    root = (
        Path(__file__).resolve().parents[2]
        / "evaluation"
        / "results"
        / "20261023-http-load"
    )
    trusted = {
        "smoke.json": "4ed1f0113f5e7ba876b7a2730060be06f5dd14221b31a11c955ee6f5e7507b5b",
        "envelope-before-print-bound-failed.json": "b0a3f283d18d62a0cc083522e69803d54ccd5aa3f369a57e28766fb5db8b9b0a",
        "envelope-after-print-bound.json": "234e5586258d87d8aa745cdc81f0fae14a97a8f34517576aeb837b5ef5746a18",
    }
    for name, expected in trusted.items():
        value = json.loads((root / name).read_text())
        saved = value.pop("report_sha256")
        assert saved == expected
        assert (
            hashlib.sha256(
                json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            == expected
        )
        assert (
            pilot_load.gate(value, value["configuration"]["chosen_p95_ms"])
            == value["gate"]
        )
        assert value["environment"]["oracle_vm_proven"] is False
    failed = json.loads((root / "envelope-before-print-bound-failed.json").read_text())
    assert failed["failure_phase"] == "signed_evidence" and not failed["gate"]["passed"]
    passed = json.loads((root / "envelope-after-print-bound.json").read_text())
    assert passed["gate"]["passed"] and passed["request_failures"] == 0
    assert passed["latencies"]["POST /api/monitor/transactions"]["requests"] == 2000
