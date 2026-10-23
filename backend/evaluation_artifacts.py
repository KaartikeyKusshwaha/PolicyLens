"""Recompute a retained evaluation against its dataset and every terminal run."""

import json
from pathlib import Path

from scorecards import Dataset, scorecard, sha

MAX_FILE_BYTES = 4_000_000
MAX_BUNDLE_BYTES = 32_000_000
REFERENCE_DIRECTORY = (
    Path(__file__).resolve().parents[1]
    / "evaluation"
    / "results"
    / "20261023-gpt-oss-20b"
)
REFERENCE_SCORECARD_SHA256 = (
    "8f1b3b85e5a3da3cbcf808036db190f9d3368dc4f1fa8b5b0e75097ff6ad84fc"
)


def read_json(path, sizes):
    if path.is_symlink() or not path.is_file():
        raise ValueError("A retained evaluation artifact is missing or redirected.")
    with path.open("rb") as source:
        content = source.read(MAX_FILE_BYTES + 1)
    sizes[0] += len(content)
    if len(content) > MAX_FILE_BYTES or sizes[0] > MAX_BUNDLE_BYTES:
        raise ValueError("Evaluation artifacts exceed the complete verification bound.")
    return json.loads(content)


def verify_directory(directory, *, trusted_digest):
    directory = Path(directory)
    if directory.is_symlink():
        raise ValueError("The retained evaluation directory is redirected.")
    sizes = [0]
    dataset_path = directory / "dataset.json"
    normalized = read_json(dataset_path, sizes)
    dataset = Dataset.model_validate(normalized)
    if dataset.model_dump(mode="json") != normalized:
        raise ValueError("Retained dataset must already be normalized.")
    report = read_json(directory / "scorecard.json", sizes)
    unsigned = dict(report)
    supplied = unsigned.pop("scorecard_sha256", None)
    if supplied != trusted_digest or sha(unsigned) != trusted_digest:
        raise ValueError(
            "Scorecard digest does not match the independently retained value."
        )
    manifest = read_json(directory / "replay-manifest.json", sizes)
    if (
        manifest["dataset_sha256"] != sha(normalized)
        or manifest["execution_mode"] != report["execution_mode"]
    ):
        raise ValueError("Replay manifest and dataset do not match the scorecard.")
    jobs = {}
    expected = {"dataset.json", "scorecard.json", "replay-manifest.json"}
    for case in dataset.cases:
        name = "run-" + case.id + ".json"
        expected.add(name)
        job = read_json(directory / name, sizes)
        if job["state"] not in ("completed", "failed"):
            raise ValueError("Every scored run must be terminal.")
        payload = job["payload"]
        if any(
            payload.get(key) != manifest.get(key)
            for key in ("model", "model_revision", "prompt_version")
        ):
            raise ValueError(
                "Retained run identity disagrees with its replay manifest."
            )
        jobs[case.id] = job
    actual = {item.name for item in directory.iterdir() if item.suffix == ".json"}
    if actual != expected:
        raise ValueError(
            "The retained bundle must contain exactly the expected JSON artifacts."
        )
    recomputed = scorecard(dataset, jobs, execution_mode=report["execution_mode"])
    for field in ("dataset_sha256", "metrics", "models", "categories", "cases", "gate"):
        if recomputed[field] != report[field]:
            raise ValueError(
                "Retained evaluation metrics or case evidence do not recompute."
            )
    return {
        "report": report,
        "verification": {
            "valid": True,
            "trusted_scorecard_sha256": trusted_digest,
            "dataset_sha256": sha(normalized),
            "terminal_runs_recomputed": len(jobs),
            "bytes_checked": sizes[0],
            "scope": "Digest and retained-run recomputation against the supplied trusted digest. This does not authenticate the external provider, validate human labels or prove raw-token quotation accuracy.",
        },
    }


def reference_result():
    result = verify_directory(
        REFERENCE_DIRECTORY, trusted_digest=REFERENCE_SCORECARD_SHA256
    )
    if result["report"]["data_origin"] != "synthetic":
        raise ValueError("The bundled reference must contain synthetic data only.")
    return {
        **result,
        "kind": "bundled_synthetic_reference",
        "workspace_measurement": False,
        "promotion_allowed": False,
        "notice": "Public synthetic reference evaluation, shared across workspaces. It does not measure this workspace's customers, configuration or current model behavior. No preparation or decision authority is granted.",
    }
