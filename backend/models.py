from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class PolicySource(str, Enum):
    INTERNAL = "internal"
    OFAC = "ofac"
    FATF = "fatf"
    RBI = "rbi"
    EU_AML = "eu_aml"


class PolicyTopic(str, Enum):
    AML = "aml"
    KYC = "kyc"
    SANCTIONS = "sanctions"
    FRAUD = "fraud"
    GENERAL = "general"


class RiskLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    ACCEPTABLE = "acceptable"


class DecisionVerdict(str, Enum):
    FLAG = "flag"
    NEEDS_REVIEW = "needs_review"
    ACCEPTABLE = "acceptable"


class PolicyDocument(BaseModel):
    doc_id: str
    title: str
    content: str
    source: PolicySource
    topic: PolicyTopic
    version: str = "1.0"
    valid_from: datetime = Field(default_factory=datetime.now)
    valid_to: Optional[datetime] = None
    is_active: bool = True
    metadata: Dict[str, Any] = {}


class PolicyChunk(BaseModel):
    chunk_id: str
    doc_id: str
    text: str
    embedding: Optional[List[float]] = None
    doc_title: str
    section: Optional[str] = None
    source: PolicySource
    topic: PolicyTopic
    version: str
    valid_from: datetime
    valid_to: Optional[datetime] = None
    is_active: bool = True


class Transaction(BaseModel):
    transaction_id: str
    amount: float
    currency: str
    sender: str
    receiver: str
    sender_country: Optional[str] = None
    receiver_country: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    description: Optional[str] = None
    metadata: Dict[str, Any] = {}


class PolicyCitation(BaseModel):
    doc_id: str
    doc_title: str
    section: Optional[str] = None
    text: str
    relevance_score: float
    version: str


class SimilarCase(BaseModel):
    case_id: str
    transaction_id: str
    similarity_score: float
    decision: DecisionVerdict
    reasoning: str
    timestamp: datetime


class ComplianceDecision(BaseModel):
    transaction_id: str
    verdict: DecisionVerdict
    risk_level: RiskLevel
    risk_score: float
    reasoning: str
    policy_citations: List[PolicyCitation]
    similar_cases: List[SimilarCase] = []
    confidence: float
    timestamp: datetime = Field(default_factory=datetime.now)
    reviewed_by: Optional[str] = None
    override_notes: Optional[str] = None


class TransactionEvaluationRequest(BaseModel):
    transaction: Transaction


class TransactionEvaluationResponse(BaseModel):
    decision: ComplianceDecision
    trace_id: str
    processing_time_ms: float


class PolicyUploadRequest(BaseModel):
    title: str
    content: str
    source: PolicySource
    topic: PolicyTopic
    version: str = "1.0"
    metadata: Dict[str, Any] = {}


class PolicyUpdateNotification(BaseModel):
    doc_id: str
    old_version: str
    new_version: str
    changes_detected: List[str]
    impacted_transactions: int
    timestamp: datetime = Field(default_factory=datetime.now)


class FeedbackRequest(BaseModel):
    transaction_id: str
    decision_id: str
    corrected_verdict: DecisionVerdict
    corrected_reasoning: str
    reviewer_notes: str
    reviewer_id: str


class QueryRequest(BaseModel):
    query: str
    topic: Optional[PolicyTopic] = None
    top_k: int = 5


class QueryResponse(BaseModel):
    query: str
    answer: str
    citations: List[PolicyCitation]
    confidence: float
