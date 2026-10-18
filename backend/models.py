from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Input(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class PolicyInput(Input):
    title: str = Field(min_length=3, max_length=180)
    content: str = Field(min_length=50, max_length=300_000)
    topic: Literal["aml", "kyc", "sanctions", "fraud", "general"] = "general"
    version: str = Field(default="1.0", min_length=1, max_length=30)
    source_url: str = Field(default="", max_length=1000)

    @field_validator("source_url")
    @classmethod
    def source_is_link(cls, value):
        if value and not value.startswith(("https://", "http://")):
            raise ValueError("Use an http or https source link.")
        return value


class Transaction(Input):
    transaction_id: str = Field(min_length=1, max_length=100)
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    sender: str = Field(min_length=2, max_length=200)
    receiver: str = Field(min_length=2, max_length=200)
    sender_country: str = Field(min_length=2, max_length=100)
    receiver_country: str = Field(min_length=2, max_length=100)
    description: str = Field(min_length=10, max_length=2000)


class EvaluationRequest(Input):
    transaction: Transaction


class QueryInput(Input):
    query: str = Field(min_length=5, max_length=2000)
    topic: Literal["aml", "kyc", "sanctions", "fraud", "general"] | None = None


class Citation(Input):
    chunk_id: str
    quote: str = Field(min_length=15, max_length=1500)


class Answer(Input):
    answer: str = Field(min_length=20, max_length=10000)
    citations: list[Citation] = Field(min_length=1, max_length=8)
    limitations: list[str] = Field(max_length=10)


class Assessment(Input):
    verdict: Literal["flag", "needs_review", "acceptable"]
    risk_score: int = Field(ge=0, le=100)
    reasoning: str = Field(min_length=30, max_length=10000)
    citations: list[Citation] = Field(min_length=1, max_length=8)
    risk_factors: list[str] = Field(max_length=12)
    limitations: list[str] = Field(min_length=1, max_length=10)


class ReviewInput(Input):
    verdict: Literal["flag", "needs_review", "acceptable"]
    reviewer: str = Field(min_length=2, max_length=100)
    notes: str = Field(min_length=10, max_length=3000)
