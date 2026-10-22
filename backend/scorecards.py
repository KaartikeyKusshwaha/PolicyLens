"""Offline replay datasets and deterministic scoring. Labels never enter agent context."""

import hashlib
from typing import Literal

from pydantic import Field, model_validator

from models import Input, PolicyInput
from operations import canonical
from product_models import CustomerInput, MonitorTransaction
from providers import PROMPT_VERSION
from store import now

MAX_DATASET_BYTES = 4_000_000
DISPOSITIONS = ("confirmed", "false_positive", "insufficient_evidence")


def sha(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


class ReplayTransaction(MonitorTransaction):
    # Rebound to the isolated customer's ID; no tenant database is selected by input.
    customer_id: str = "replay"


class LabeledCase(Input):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,80}$")
    category: str = Field(min_length=3, max_length=100)
    customer: CustomerInput
    title: str = Field(min_length=5, max_length=180)
    description: str = Field(min_length=10, max_length=4000)
    transactions: list[ReplayTransaction] = Field(default_factory=list, max_length=50)
    expected_disposition: Literal[
        "confirmed", "false_positive", "insufficient_evidence"
    ]
    label_reference: str = Field(min_length=3, max_length=500)
    label_rationale: str = Field(min_length=20, max_length=2000)


class Dataset(Input):
    schema_version: Literal["policylens.agent-evaluation.v1"]
    title: str = Field(min_length=5, max_length=160)
    origin: Literal["synthetic", "historical"]
    label_author: str = Field(min_length=3, max_length=200)
    limitations: list[str] = Field(min_length=1, max_length=12)
    policy: PolicyInput
    cases: list[LabeledCase] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def bounded_unique(self):
        if len({case.id for case in self.cases}) != len(self.cases):
            raise ValueError(
                "Case IDs must be unique; repeated labels cannot inflate scores."
            )
        if len({case.customer.external_id for case in self.cases}) != len(self.cases):
            raise ValueError(
                "Each replay case needs a distinct synthetic customer reference."
            )
        transactions = [
            txn.external_id for case in self.cases for txn in case.transactions
        ]
        if len(set(transactions)) != len(transactions):
            raise ValueError(
                "Replay transaction references must be unique across the dataset."
            )
        if len(canonical(self.model_dump(mode="json")).encode()) > MAX_DATASET_BYTES:
            raise ValueError("The complete dataset exceeds the 4 MB bound.")
        return self


def score_case(label, job):
    """Score retained drafts even when the normal verifier rejects their citations."""
    steps = {item["step"]: item["output"] for item in job.get("steps", [])}
    payload = job["payload"]
    draft = steps.get("draft_analysis", {})
    context = steps.get("collect_evidence", {})
    chunks = {item["chunk_id"]: item for item in context.get("policies", [])}
    valid = unsupported = unknown = 0
    citations = draft.get("citations", [])
    for citation in citations:
        chunk = chunks.get(citation["chunk_id"])
        quote = " ".join(citation["quote"].split())
        if chunk is None:
            unknown += 1
        elif not quote or quote not in " ".join(chunk["text"].split()):
            unsupported += 1
        else:
            valid += 1
    predicted = draft.get("draft_disposition")
    completed = job["state"] == "completed"
    identity = {
        "model": payload.get("model"),
        "model_revision": payload.get("model_revision"),
        "prompt_version": payload.get("prompt_version"),
        "provider_identity": steps.get("model_identity"),
    }
    return {
        "case_id": label.id,
        "category": label.category,
        "job_id": job["id"],
        "state": job["state"],
        "error_code": payload.get("error", {}).get("code"),
        "provider_error_code": payload.get("error", {}).get("provider_error_code"),
        "identity": identity,
        "job_sha256": sha(job),
        "context_sha256": sha(context),
        "expected_disposition": label.expected_disposition,
        "draft_disposition": predicted,
        "abstained": predicted is None,
        "retained_draft": bool(draft),
        "agreement": completed and predicted == label.expected_disposition,
        "citation_count": len(citations),
        "valid_citations": valid,
        "unsupported_quotes": unsupported,
        "unknown_citation_ids": unknown,
        "fully_cited_completion": completed
        and bool(citations)
        and valid == len(citations),
    }


def aggregate(rows):
    count = len(rows)
    citations = sum(row["citation_count"] for row in rows)
    valid = sum(row["valid_citations"] for row in rows)
    unsupported = sum(row["unsupported_quotes"] for row in rows)
    confusion = {
        expected: {**dict.fromkeys(DISPOSITIONS, 0), "abstained_or_failed": 0}
        for expected in DISPOSITIONS
    }
    for row in rows:
        predicted = row["draft_disposition"]
        if row["state"] != "completed" or predicted not in DISPOSITIONS:
            predicted = "abstained_or_failed"
        confusion[row["expected_disposition"]][predicted] += 1
    return {
        "labeled_cases": count,
        "completed_runs": sum(row["state"] == "completed" for row in rows),
        "fully_cited_completions": sum(row["fully_cited_completion"] for row in rows),
        "abstentions": sum(row["abstained"] for row in rows),
        "runs_without_retained_draft": sum(not row["retained_draft"] for row in rows),
        "citation_count": citations,
        "valid_citations": valid,
        "unsupported_quotes": unsupported,
        "unknown_citation_ids": sum(row["unknown_citation_ids"] for row in rows),
        "citation_validity": valid / citations if citations else None,
        "fabricated_quote_rate": unsupported / citations if citations else None,
        "disposition_agreement": sum(row["agreement"] for row in rows) / count,
        "confusion_matrix": confusion,
    }


def scorecard(dataset, jobs, *, execution_mode):
    if execution_mode not in ("live_provider", "test_transport"):
        raise ValueError("An explicit execution mode is required.")
    if set(jobs) != {case.id for case in dataset.cases}:
        raise ValueError(
            "Every label must have exactly one retained run; no partial scorecard."
        )
    rows = [score_case(case, jobs[case.id]) for case in dataset.cases]
    if len({row["job_id"] for row in rows}) != len(rows):
        raise ValueError("The same run cannot be scored as multiple cases.")
    groups = {}
    for row in rows:
        groups.setdefault(canonical(row["identity"]), []).append(row)
    models = [
        {"identity": group[0]["identity"], "metrics": aggregate(group)}
        for group in groups.values()
    ]
    metrics = aggregate(rows)
    categories = {
        category: aggregate([row for row in rows if row["category"] == category])
        for category in sorted({row["category"] for row in rows})
    }
    checks = {
        "at_least_50_labeled_cases": len(rows) >= 50,
        "single_model_and_prompt": len(models) == 1,
        "current_prompt": all(
            row["identity"]["prompt_version"] == PROMPT_VERSION for row in rows
        ),
        "all_runs_completed_and_cited": metrics["fully_cited_completions"] == len(rows),
        "zero_unsupported_or_unknown_quotes": metrics["unsupported_quotes"] == 0
        and metrics["unknown_citation_ids"] == 0,
        "agreement_at_least_80_percent": metrics["disposition_agreement"] >= 0.8,
        "live_provider_measurement": execution_mode == "live_provider",
    }
    result = {
        "schema": "policylens.agent-scorecard.v1",
        "generated_at": now(),
        "dataset_sha256": sha(dataset.model_dump(mode="json")),
        "dataset_title": dataset.title,
        "data_origin": dataset.origin,
        "label_author": dataset.label_author,
        "execution_mode": execution_mode,
        "metrics": metrics,
        "models": models,
        "categories": categories,
        "cases": rows,
        "gate": {
            "checks": checks,
            "draft_preparation_quality_passed": all(checks.values()),
            "autopilot_enabled": False,
        },
        "limitations": [
            *dataset.limitations,
            "Agreement counts failures and abstentions in the full labeled-case denominator. Labels are supplied judgments, not regulatory truth.",
            "Citation validity checks exact whitespace-normalized source excerpts and IDs, not whether quotations support every narrative inference.",
            "Fabricated-quote rate means known-source quotations absent from that source. Unknown IDs are reported separately. Provider rejections before a draft is retained have no observable quotation denominator; they remain failed runs.",
            "Scores concern post-schema, resolved-quotation drafts, not raw model token hallucination rates. Quote-ID constrained generation changes that measurement.",
            "The 80% gate is an engineering threshold, not a validated legal or model-risk standard. Passing does not enable autopilot or authorize decisions.",
            "Provider-unreported revisions do not establish immutable model weights. Synthetic labels are scenario-author labels, not real analyst dispositions.",
        ],
    }
    result["scorecard_sha256"] = sha(result)
    return result
