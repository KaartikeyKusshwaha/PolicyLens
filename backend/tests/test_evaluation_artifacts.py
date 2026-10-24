import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import evaluation_artifacts as artifacts


def test_retained_live_result_recomputes_every_case_failure_and_quote():
    result = artifacts.reference_result()
    report = result["report"]
    assert result["verification"]["valid"]
    assert result["verification"]["terminal_runs_recomputed"] == 50
    assert report["execution_mode"] == "live_provider"
    assert report["data_origin"] == "synthetic"
    assert report["metrics"]["completed_runs"] == 46
    assert (
        report["metrics"]["citation_count"]
        == report["metrics"]["valid_citations"]
        == 109
    )
    assert report["metrics"]["disposition_agreement"] == 43 / 50
    assert report["metrics"]["runs_without_retained_draft"] == 4
    assert sum(case["state"] == "failed" for case in report["cases"]) == 4
    assert not report["gate"]["draft_preparation_quality_passed"]
    assert not report["gate"]["checks"]["single_model_and_prompt"]
    assert not report["gate"]["checks"]["all_runs_completed_and_cited"]
    assert not result["workspace_measurement"] and not result["promotion_allowed"]


@pytest.mark.parametrize(
    "mutation",
    [
        "report",
        "run",
        "run_context",
        "missing_run",
        "extra_run",
        "manifest",
        "dataset",
        "oversized",
    ],
)
def test_reference_verifier_refuses_tampered_missing_or_partial_artifacts(
    tmp_path, mutation
):
    destination = tmp_path / "retained"
    shutil.copytree(artifacts.REFERENCE_DIRECTORY, destination)
    first = sorted(destination.glob("run-*.json"))[0]
    if mutation == "report":
        path = destination / "scorecard.json"
        value = json.loads(path.read_text())
        value["metrics"]["disposition_agreement"] = 1.0
        path.write_text(json.dumps(value))
    elif mutation == "run":
        value = json.loads(first.read_text())
        value["payload"]["model"] = "substituted-model"
        first.write_text(json.dumps(value))
    elif mutation == "run_context":
        value = json.loads(first.read_text())
        collected = next(
            step for step in value["steps"] if step["step"] == "collect_evidence"
        )
        collected["output"]["policies"][0]["text"] = (
            "Altered quotation source after evaluation."
        )
        first.write_text(json.dumps(value))
    elif mutation == "missing_run":
        first.unlink()
    elif mutation == "extra_run":
        (destination / "run-extra.json").write_text("{}")
    elif mutation == "manifest":
        path = destination / "replay-manifest.json"
        value = json.loads(path.read_text())
        value["dataset_sha256"] = "a" * 64
        path.write_text(json.dumps(value))
    elif mutation == "dataset":
        path = destination / "dataset.json"
        value = json.loads(path.read_text())
        value["cases"][0]["expected_disposition"] = "false_positive"
        path.write_text(json.dumps(value))
    else:
        first.write_bytes(b" " * (artifacts.MAX_FILE_BYTES + 1))
    with pytest.raises((ValueError, OSError)):
        artifacts.verify_directory(
            destination, trusted_digest=artifacts.REFERENCE_SCORECARD_SHA256
        )


def test_verifier_requires_trusted_digest_and_bounded_whole_bundle(monkeypatch):
    with pytest.raises(ValueError, match="digest"):
        artifacts.verify_directory(
            artifacts.REFERENCE_DIRECTORY, trusted_digest="f" * 64
        )
    monkeypatch.setattr(artifacts, "MAX_BUNDLE_BYTES", 100)
    with pytest.raises(ValueError, match="bound"):
        artifacts.reference_result()




def test_offline_verifier_subprocess_recomputes_the_committed_run_bundle():
    root = Path(__file__).resolve().parents[2]
    command = [
        sys.executable,
        str(root / "verify_agent_evaluation.py"),
        str(artifacts.REFERENCE_DIRECTORY),
        "--scorecard-sha256",
        artifacts.REFERENCE_SCORECARD_SHA256,
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["terminal_runs_recomputed"] == 50
    command[-1] = "0" * 64
    refused = subprocess.run(command, capture_output=True, text=True, timeout=30)
    assert refused.returncode == 1 and json.loads(refused.stdout)["valid"] is False
