from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal

from pydantic import Field, field_validator, model_validator

from models import Citation, Input


class CustomerInput(Input):
    external_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=3, max_length=180)
    kind: Literal["individual", "company"] = "individual"
    country: str = Field(pattern=r"^[A-Z]{2}$")
    address: str = Field(default="", max_length=500)
    risk_tier: Literal["low", "medium", "high"] = "medium"
    kyc_status: Literal["pending", "verified", "expired"] = "pending"
    lei: str = Field(default="", pattern=r"^$|^[A-Z0-9]{18}[0-9]{2}$")
    notes: str = Field(default="", max_length=3000)


class MonitorTransaction(Input):
    external_id: str = Field(min_length=1, max_length=100)
    customer_id: str = Field(min_length=1, max_length=100)
    amount: Decimal = Field(gt=0, max_digits=16, decimal_places=2)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    counterparty: str = Field(min_length=3, max_length=180)
    counterparty_country: str = Field(pattern=r"^[A-Z]{2}$")
    account_reference: str = Field(default="", max_length=100)
    description: str = Field(min_length=5, max_length=2000)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("occurred_at")
    @classmethod
    def timezone_required(cls, value):
        if value.tzinfo is None:
            raise ValueError("Include a timezone, for example 2026-10-19T10:00:00Z.")
        if value > datetime.now(timezone.utc):
            raise ValueError("Transaction time cannot be in the future.")
        return value.astimezone(timezone.utc)


class RuleInput(Input):
    title: str = Field(min_length=3, max_length=160)
    kind: Literal["amount", "velocity", "aggregate", "corridor", "kyc"]
    policy_id: str = Field(min_length=1, max_length=100)
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    threshold: Decimal = Field(
        default=Decimal("10000"), ge=1, max_digits=16, decimal_places=2
    )
    window_hours: int = Field(default=24, ge=1, le=720)
    countries: list[str] = Field(default_factory=list, max_length=40)
    priority: Literal["low", "medium", "high", "critical"] = "medium"
    description: str = Field(min_length=10, max_length=2000)

    @field_validator("countries")
    @classmethod
    def countries_are_iso(cls, value):
        if any(len(c) != 2 or not c.isalpha() or c != c.upper() for c in value):
            raise ValueError("Use uppercase ISO country codes.")
        return list(dict.fromkeys(value))

    @model_validator(mode="after")
    def check_kind(self):
        if (
            self.kind == "velocity"
            and self.threshold != self.threshold.to_integral_value()
        ):
            raise ValueError("Velocity threshold must be an integer count.")
        if self.kind == "corridor" and not self.countries:
            raise ValueError("Select at least one destination country.")
        return self


class CaseInput(Input):
    customer_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=5, max_length=180)
    priority: Literal["low", "medium", "high", "critical"] = "medium"
    description: str = Field(min_length=10, max_length=4000)


class CaseAction(Input):
    action: Literal["assign", "start", "escalate", "resolve", "reopen", "note", "task"]
    notes: str = Field(min_length=5, max_length=4000)
    assignee_id: str = Field(default="", max_length=100)
    disposition: Literal["", "confirmed", "false_positive", "insufficient_evidence"] = (
        ""
    )
    due_at: datetime | None = None


class AgentStart(Input):
    kind: Literal[
        "investigation", "screening", "policy_analyst", "policy_change", "report"
    ]
    target_id: str = Field(min_length=1, max_length=100)


class AgentControl(Input):
    action: Literal["pause", "resume", "cancel"]


class InvestigationBrief(Input):
    summary: str = Field(min_length=30, max_length=6000)
    recommendation: Literal["investigate", "escalate", "review_for_closure"]
    findings: list[str] = Field(min_length=1, max_length=12)
    missing_evidence: list[str] = Field(max_length=12)
    citations: list[Citation] = Field(min_length=1, max_length=6)
    limitations: list[str] = Field(min_length=1, max_length=8)


class Obligation(Input):
    obligation: str = Field(min_length=15, max_length=1000)
    control_kind: Literal[
        "amount", "velocity", "aggregate", "corridor", "kyc", "manual"
    ]
    citation: Citation
    requires_human_interpretation: bool


class PolicyAnalysis(Input):
    summary: str = Field(min_length=20, max_length=4000)
    obligations: list[Obligation] = Field(min_length=1, max_length=8)
    limitations: list[str] = Field(min_length=1, max_length=8)


class WorkspacePreferences(Input):
    enabled_sources: list[Literal["ofac", "un", "uk"]] = Field(
        min_length=1, max_length=3
    )
    monitoring_enabled: bool = False
    monitoring_interval_hours: int = Field(default=6, ge=6, le=72)

    @field_validator("enabled_sources")
    @classmethod
    def unique_sources(cls, value):
        return list(dict.fromkeys(value))


class NamedWorkspace(Input):
    name: str = Field(min_length=3, max_length=100)


class IntegrationInput(Input):
    name: str = Field(min_length=3, max_length=100)


class RuleAction(Input):
    action: Literal["approve", "disable"]
    notes: str = Field(min_length=10, max_length=2000)


class ImpactAction(Input):
    action: Literal["approve", "dismiss"]
    notes: str = Field(min_length=10, max_length=2000)
