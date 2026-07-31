from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from database import Base
import datetime

class DBPolicy(Base):
    __tablename__ = "policies"

    id = Column(String, primary_key=True, index=True) # Maps to doc_id
    title = Column(String, index=True)
    content = Column(String)
    source = Column(String, index=True)
    topic = Column(String, index=True)
    version = Column(String, default="1.0")
    valid_from = Column(DateTime, default=datetime.datetime.utcnow)
    valid_to = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    metadata_json = Column(JSON, default=dict)

class DBTransaction(Base):
    __tablename__ = "transactions"

    id = Column(String, primary_key=True, index=True) # Maps to transaction_id
    amount = Column(Float)
    currency = Column(String)
    sender = Column(String)
    receiver = Column(String)
    sender_country = Column(String, nullable=True)
    receiver_country = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    description = Column(String, nullable=True)
    metadata_json = Column(JSON, default=dict)

    decisions = relationship("DBDecision", back_populates="transaction")

class DBDecision(Base):
    __tablename__ = "decisions"

    id = Column(String, primary_key=True, index=True) # Maps to trace_id
    transaction_id = Column(String, ForeignKey("transactions.id"))
    verdict = Column(String, index=True)
    risk_level = Column(String, index=True)
    risk_score = Column(Float)
    reasoning = Column(String)
    policy_citations = Column(JSON, default=list)
    similar_cases = Column(JSON, default=list)
    confidence = Column(Float)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    reviewed_by = Column(String, nullable=True)
    override_notes = Column(String, nullable=True)
    stored_at = Column(DateTime, default=datetime.datetime.utcnow)

    transaction = relationship("DBTransaction", back_populates="decisions")

class DBFeedback(Base):
    __tablename__ = "feedback"

    id = Column(String, primary_key=True, index=True)
    transaction_id = Column(String, index=True)
    decision_id = Column(String, index=True)
    corrected_verdict = Column(String)
    corrected_reasoning = Column(String)
    reviewer_notes = Column(String)
    reviewer_id = Column(String)
    submitted_at = Column(DateTime, default=datetime.datetime.utcnow)

class DBLatency(Base):
    __tablename__ = "latencies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    operation_type = Column(String, index=True)
    latency_ms = Column(Float)
    transaction_id = Column(String, nullable=True)

class DBExternalData(Base):
    __tablename__ = "external_data_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String, index=True)
    status = Column(String)
    records_fetched = Column(Integer)
    message = Column(String)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
