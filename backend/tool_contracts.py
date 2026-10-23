"""One permission registry for HTTP, MCP, CLI and SDK discovery/execution."""

from typing import Literal

from pydantic import Field

from models import Citation, Input
from control_tuning import DraftInput, TuningInput


class SearchPolicy(Input):
    query: str = Field(min_length=3, max_length=1000)
    topic: Literal["aml", "kyc", "sanctions", "fraud", "general"] | None = None


class ControlRef(Input):
    control_id: str = Field(min_length=1, max_length=100)


class CaseRef(Input):
    case_id: str = Field(min_length=1, max_length=100)


class AlertQuery(Input):
    case_id: str | None = Field(default=None, max_length=100)
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0, le=100000)


class VerifyEvidence(Input):
    run_id: str = Field(min_length=1, max_length=100)
    citations: list[Citation] = Field(min_length=1, max_length=20)


class ReviewTask(CaseRef):
    instructions: str = Field(min_length=10, max_length=2000)


class Playbook(Input):
    kind: Literal[
        "investigation", "screening", "policy_analyst", "policy_change", "report"
    ]
    target_id: str = Field(min_length=1, max_length=100)


class RunRef(Input):
    run_id: str = Field(min_length=1, max_length=100)


class RunControl(RunRef):
    action: Literal["pause", "resume", "cancel"]


TOOLS = {
    "simulate_control_tuning": (
        "draft",
        TuningInput,
        "Compare supplied numeric thresholds against a caller-specified historical match-count target. This measures workload, not detection accuracy.",
    ),
    "draft_control_tuning": (
        "request-approval",
        DraftInput,
        "Pin a tuning simulation and create a threshold-change draft. Independent human review is required; no activation occurs.",
    ),
    "search_policy": (
        "read",
        SearchPolicy,
        "Search policy excerpts with source and version references.",
    ),
    "get_control": ("read", ControlRef, "Read a control and its approval history."),
    "simulate_control": (
        "draft",
        ControlRef,
        "Run a historical simulation without activating controls or creating live alerts.",
    ),
    "list_alerts": ("read", AlertQuery, "Read a bounded page of recorded alerts."),
    "get_case_context": (
        "read",
        CaseRef,
        "Read case evidence, customer context and recorded agent work.",
    ),
    "draft_investigation_brief": (
        "draft",
        CaseRef,
        "Queue a cited investigation draft through the existing runner.",
    ),
    "verify_evidence": (
        "read",
        VerifyEvidence,
        "Verify quotations against the run's collected policy snapshot.",
    ),
    "create_review_task": (
        "request-approval",
        ReviewTask,
        "Request human review; this never approves or closes anything.",
    ),
    "export_case_pack": (
        "read",
        CaseRef,
        "Export recorded case evidence and an audit checkpoint.",
    ),
    "run_playbook": (
        "draft",
        Playbook,
        "Queue an investigation, screening, policy analyst, policy-change or report playbook.",
    ),
    "get_agent_run": (
        "read",
        RunRef,
        "Read a recorded run, steps and its draft result.",
    ),
    "control_agent_run": (
        "draft",
        RunControl,
        "Pause, resume or cancel this agent key's own run.",
    ),
}


def catalog(scopes=None):
    return [
        {
            "name": name,
            "class": category,
            "description": description,
            "input_schema": schema.model_json_schema(),
        }
        for name, (category, schema, description) in TOOLS.items()
        if scopes is None or name in scopes
    ]
