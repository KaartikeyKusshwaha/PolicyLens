import asyncio
import copy
import json
import subprocess
import sys
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from agents import AgentEngine
from config import Settings
from evaluation_replay import load_dataset, replay
from operations import Operations
from providers import GROQ_URL, PROMPT_VERSION
from scorecards import Dataset, aggregate, scorecard, score_case, sha
from store import Store

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "evaluation" / "seeded-cases.json"


def corpus():
    return load_dataset(DATASET)


def retained_job(label, *, state="completed", prediction=None, quote=None):
    return {
        "id": "run-" + label.id,
        "state": state,
        "payload": {
            "model": "test-model",
            "model_revision": "test-revision",
            "prompt_version": PROMPT_VERSION,
        },
        "steps": [
            {
                "step": "collect_evidence",
                "output": {
                    "policies": [
                        {
                            "chunk_id": "source-1",
                            "text": "Only human reviewers may resolve a case after reviewing the evidence.",
                        }
                    ]
                },
            },
            {
                "step": "draft_analysis",
                "output": {
                    "draft_disposition": prediction or label.expected_disposition,
                    "citations": [
                        {
                            "chunk_id": "source-1",
                            "quote": quote or "Only human reviewers may resolve a case",
                        }
                    ],
                },
            },
        ],
    }


def test_seeded_labels_are_reviewable_balanced_and_unique():
    dataset = corpus()
    assert len(dataset.cases) == 50
    assert len({case.category for case in dataset.cases}) == 10
    assert {case.expected_disposition for case in dataset.cases} == {
        "confirmed",
        "false_positive",
        "insufficient_evidence",
    }
    assert all(
        case.label_reference and len(case.label_rationale) >= 20
        for case in dataset.cases
    )
    source = dataset.model_dump(mode="json")
    duplicate = copy.deepcopy(source)
    duplicate["cases"][1]["id"] = duplicate["cases"][0]["id"]
    with pytest.raises(ValidationError, match="unique"):
        Dataset.model_validate(duplicate)
    duplicate = copy.deepcopy(source)
    duplicate["cases"][1]["customer"]["external_id"] = duplicate["cases"][0][
        "customer"
    ]["external_id"]
    with pytest.raises(ValidationError, match="distinct"):
        Dataset.model_validate(duplicate)


def test_scoring_includes_failures_abstentions_and_exact_quote_errors():
    label = corpus().cases[0]
    good = score_case(label, retained_job(label))
    unsupported = score_case(
        label,
        retained_job(
            label,
            state="failed",
            quote="Invented sentence that is absent from the source.",
        ),
    )
    unknown_job = retained_job(label)
    unknown_job["steps"][1]["output"]["citations"][0]["chunk_id"] = "unknown"
    unknown = score_case(label, unknown_job)
    abstain_job = retained_job(label)
    abstain_job["steps"][1]["output"]["draft_disposition"] = None
    abstain = score_case(label, abstain_job)
    pre_schema_failure = retained_job(label, state="failed")
    pre_schema_failure["steps"] = []
    failed = score_case(label, pre_schema_failure)
    metrics = aggregate([good, unsupported, unknown, abstain, failed])
    assert metrics["completed_runs"] == 3
    assert metrics["disposition_agreement"] == 2 / 5
    assert metrics["citation_validity"] == 2 / 4
    assert metrics["fabricated_quote_rate"] == 1 / 4
    assert metrics["unknown_citation_ids"] == 1
    assert metrics["abstentions"] == 2
    assert metrics["confusion_matrix"]["confirmed"]["abstained_or_failed"] == 3
    assert aggregate([failed])["citation_validity"] is None


def test_complete_gate_and_per_model_groups_cannot_hide_partial_or_mock_results():
    dataset = corpus()
    jobs = {label.id: retained_job(label) for label in dataset.cases}
    mocked = scorecard(dataset, jobs, execution_mode="test_transport")
    assert mocked["metrics"]["disposition_agreement"] == 1
    assert mocked["gate"]["draft_preparation_quality_passed"] is False
    assert mocked["gate"]["checks"]["live_provider_measurement"] is False
    live = scorecard(dataset, jobs, execution_mode="live_provider")
    assert live["gate"]["draft_preparation_quality_passed"] is True
    assert live["gate"]["autopilot_enabled"] is False
    assert len(live["categories"]) == 10
    unsigned = dict(live)
    digest = unsigned.pop("scorecard_sha256")
    assert sha(unsigned) == digest
    jobs[dataset.cases[0].id]["payload"]["model"] = "other-model"
    mixed = scorecard(dataset, jobs, execution_mode="live_provider")
    assert len(mixed["models"]) == 2
    assert not mixed["gate"]["draft_preparation_quality_passed"]
    jobs.pop(dataset.cases[0].id)
    with pytest.raises(ValueError, match="Every label"):
        scorecard(dataset, jobs, execution_mode="live_provider")


def responder(calls):
    def respond(request):
        assert str(request.url) == GROQ_URL
        wire = json.loads(request.content)
        schema = wire["response_format"]["json_schema"]["schema"]
        assert set(schema["required"]) == set(schema["properties"])
        assert "default" not in schema["properties"]["draft_disposition"]
        context = json.loads(wire["messages"][1]["content"])
        encoded = json.dumps(context)
        for excluded in (
            "expected_disposition",
            "label_rationale",
            "label_reference",
            "label_author",
            "category",
        ):
            assert excluded not in context
        assert "synthetic-scenario-v1" not in encoded
        assert context["case"]["disposition"] == ""
        description = context["case"]["description"]
        if any(word in description for word in ("acknowledges", "admits")):
            prediction = "confirmed"
        elif any(
            word in description for word in ("duplicates", "fully explains", "namesake")
        ):
            prediction = "false_positive"
        else:
            prediction = "insufficient_evidence"
        quote = context["citation_quotes"][0]
        calls.append(context)
        return httpx.Response(
            200,
            json={
                "model": wire["model"],
                "system_fingerprint": "test-fingerprint",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": json.dumps(
                                {
                                    "summary": "Synthetic deterministic test response for the isolated replay harness.",
                                    "recommendation": "investigate",
                                    "draft_disposition": prediction,
                                    "findings": [
                                        "Review the supplied synthetic evidence."
                                    ],
                                    "missing_evidence": [],
                                    "citations": [
                                        {
                                            "chunk_id": quote["chunk_id"],
                                            "quote": quote["quote_id"],
                                        }
                                    ],
                                    "limitations": [
                                        "Deterministic test transport, not live model performance."
                                    ],
                                }
                            )
                        },
                    }
                ],
            },
        )

    return respond


def test_fifty_case_replay_uses_real_runner_hidden_labels_budgets_and_retained_runs(
    tmp_path,
):
    calls = []
    settings = Settings(
        _env_file=None,
        database_path=tmp_path / "untouched-pilot.db",
        groq_api_key="test-evaluation-key",
        groq_model="test-model",
        agent_daily_runs=50,
    )
    destination = tmp_path / "replay"
    report = asyncio.run(
        replay(
            corpus(),
            settings,
            destination,
            transport=httpx.MockTransport(responder(calls)),
        )
    )
    assert len(calls) == 50
    assert report["metrics"]["labeled_cases"] == 50
    assert report["metrics"]["completed_runs"] == 50
    assert report["metrics"]["citation_validity"] == 1
    assert report["metrics"]["fabricated_quote_rate"] == 0
    assert report["metrics"]["disposition_agreement"] == 1
    assert not report["gate"]["draft_preparation_quality_passed"]
    assert report["execution_mode"] == "test_transport"
    assert not settings.database_path.exists()
    assert len(list(destination.glob("run-*.json"))) == 50
    assert json.loads((destination / "scorecard.json").read_text()) == report
    store = Store(destination / "data" / "evaluation.db")
    assert Operations(store).verify_audit()["valid"]
    assert all(
        case["status"] == "open" and case["disposition"] == ""
        for case in Operations(store).list("case")
    )
    assert all(
        len(AgentEngine.get(store, row["job_id"])["steps"]) >= 5
        for row in report["cases"]
    )
    with pytest.raises(FileExistsError):
        asyncio.run(replay(corpus(), settings, destination))


def test_replay_preflight_refuses_budget_key_historical_and_oversized_input(tmp_path):
    settings = Settings(_env_file=None, groq_api_key="test-key", agent_daily_runs=30)
    output = tmp_path / "not-created"
    with pytest.raises(ValueError, match="budget"):
        asyncio.run(replay(corpus(), settings, output))
    assert not output.exists()
    settings = settings.model_copy(
        update={
            "agent_daily_runs": 50,
            "groq_api_key": Settings(_env_file=None).groq_api_key,
        }
    )
    with pytest.raises(ValueError, match="GROQ_API_KEY"):
        asyncio.run(replay(corpus(), settings, output))
    historical = corpus().model_copy(update={"origin": "historical"})
    with pytest.raises(ValueError, match="Historical"):
        asyncio.run(replay(historical, settings, output))
    large = tmp_path / "oversized.json"
    large.write_bytes(b" " * 4_000_001)
    with pytest.raises(ValueError, match="4 MB"):
        load_dataset(large)


def test_replay_preserves_sqlcipher_mode_with_a_separate_installation_key(tmp_path):
    calls = []
    settings = Settings(
        _env_file=None,
        groq_api_key="test-evaluation-key",
        database_encryption="sqlcipher4",
    )
    dataset = corpus().model_copy(update={"cases": corpus().cases[:1]})
    destination = tmp_path / "encrypted-replay"
    report = asyncio.run(
        replay(
            dataset,
            settings,
            destination,
            transport=httpx.MockTransport(responder(calls)),
        )
    )
    assert report["metrics"]["completed_runs"] == 1
    assert (destination / "private-installation-key").is_file()
    assert (
        not (destination / "data" / "evaluation.db")
        .read_bytes()
        .startswith(b"SQLite format 3")
    )
    assert (
        not (destination / "data" / "identity.db")
        .read_bytes()
        .startswith(b"SQLite format 3")
    )


@pytest.mark.parametrize(
    "status,code",
    [
        (400, "ai_request_rejected"),
        (401, "groq_access_denied"),
        (429, "groq_rate_limited"),
    ],
)
def test_systemic_provider_failures_stop_once_preserve_failed_run_and_publish_no_partial_card(
    tmp_path, status, code
):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            status, json={"error": {"message": "Synthetic provider failure"}}
        )

    settings = Settings(
        _env_file=None, groq_api_key="test-evaluation-key", agent_daily_runs=50
    )
    destination = tmp_path / "stopped-replay"
    with pytest.raises(RuntimeError, match="no partial scorecard"):
        asyncio.run(
            replay(
                corpus(), settings, destination, transport=httpx.MockTransport(handler)
            )
        )
    assert len(calls) == 1
    assert not (destination / "scorecard.json").exists()
    stopped = json.loads((destination / "replay-stopped.json").read_text())
    assert stopped["error_code"] == code
    assert stopped["retained_runs"] == 1
    failed = json.loads(next(destination.glob("run-*.json")).read_text())
    assert failed["state"] == "failed"
    assert failed["payload"]["error"]["code"] == code


def test_cli_help_and_preflight_do_not_create_workspace(tmp_path):
    help_result = subprocess.run(
        [sys.executable, str(ROOT / "evaluate_agents.py"), "--help"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert help_result.returncode == 0
    assert "--daily-run-budget" in help_result.stdout
    output = tmp_path / "cli-output"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "evaluate_agents.py"),
            "--dataset",
            str(DATASET),
            "--output",
            str(output),
            "--daily-run-budget",
            "1",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 1
    assert json.loads(result.stderr)["error_type"] == "ValueError"
    assert not output.exists()
