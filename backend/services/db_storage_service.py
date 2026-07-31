import json
import logging
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pathlib import Path

from database import SessionLocal
from models_db import DBDecision, DBTransaction, DBFeedback, DBLatency, DBExternalData

logger = logging.getLogger(__name__)

class DatabaseStorageService:
    """SQLAlchemy based storage for decisions and feedback, replacing the file-based StorageService."""
    
    def __init__(self, storage_dir: str = "data"):
        # Keeping storage_dir for compatibility with generic JSON file saves
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.metrics_file = self.storage_dir / "metrics.json"
        logger.info("Database storage service initialized")

    def store_decision(self, trace_id: str, decision_data: Dict[str, Any]) -> bool:
        """Store a compliance decision"""
        db = SessionLocal()
        try:
            txn_id = (
                decision_data.get("transaction", {}).get("transaction_id")
                or decision_data.get("transaction_id")
                or f"unknown_{uuid.uuid4().hex[:8]}"
            )

            existing_tx = db.query(DBTransaction).filter(DBTransaction.id == txn_id).first()
            if not existing_tx:
                txn = decision_data.get("transaction", {})
                new_tx = DBTransaction(
                    id=txn_id,
                    amount=txn.get("amount", 0.0),
                    currency=txn.get("currency", "USD"),
                    sender=txn.get("sender", "unknown"),
                    receiver=txn.get("receiver", "unknown"),
                    sender_country=txn.get("sender_country"),
                    receiver_country=txn.get("receiver_country"),
                    description=txn.get("description"),
                    metadata_json=txn.get("metadata", {})
                )
                db.add(new_tx)
                db.commit()

            dec = decision_data.get("decision", decision_data)

            new_decision = DBDecision(
                id=trace_id,
                transaction_id=txn_id,
                verdict=dec.get("verdict", "needs_review"),
                risk_level=dec.get("risk_level", "medium"),
                risk_score=dec.get("risk_score", 50.0),
                reasoning=dec.get("reasoning", ""),
                policy_citations=json.loads(json.dumps(dec.get("policy_citations", []), default=str)),
                similar_cases=json.loads(json.dumps(dec.get("similar_cases", []), default=str)),
                confidence=dec.get("confidence", 0.0),
                reviewed_by=dec.get("reviewed_by"),
                override_notes=dec.get("override_notes")
            )
            db.add(new_decision)
            db.commit()
            logger.info(f"Decision stored in DB: {trace_id}")
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Error storing decision {trace_id} in DB: {e}")
            return False
        finally:
            db.close()

    def get_decision(self, trace_id: str) -> Optional[Dict[str, Any]]:
        db = SessionLocal()
        try:
            decision = db.query(DBDecision).filter(DBDecision.id == trace_id).first()
            if not decision:
                return None
            return self._format_decision(decision)
        except Exception as e:
            logger.error(f"Error retrieving decision {trace_id}: {e}")
            return None
        finally:
            db.close()

    def list_decisions(self, limit: int = 100, skip: int = 0) -> List[Dict[str, Any]]:
        db = SessionLocal()
        try:
            decisions = db.query(DBDecision).order_by(DBDecision.stored_at.desc()).offset(skip).limit(limit).all()
            return [self._format_decision(d) for d in decisions]
        except Exception as e:
            logger.error(f"Error listing decisions from DB: {e}")
            return []
        finally:
            db.close()

    def get_all_decisions(self) -> List[Dict[str, Any]]:
        db = SessionLocal()
        try:
            decisions = db.query(DBDecision).all()
            return [self._format_decision(d) for d in decisions]
        except Exception as e:
            logger.error(f"Error loading all decisions from DB: {e}")
            return []
        finally:
            db.close()

    def _format_decision(self, d: DBDecision) -> Dict[str, Any]:
        """Convert DB model to dictionary matching the existing API response structure"""
        return {
            "trace_id": d.id,
            "stored_at": d.stored_at.isoformat() if d.stored_at else None,
            "decision": {
                "transaction_id": d.transaction_id,
                "verdict": d.verdict,
                "risk_level": d.risk_level,
                "risk_score": d.risk_score,
                "reasoning": d.reasoning,
                "policy_citations": d.policy_citations,
                "similar_cases": d.similar_cases,
                "confidence": d.confidence,
                "reviewed_by": d.reviewed_by,
                "override_notes": d.override_notes,
                "timestamp": d.timestamp.isoformat() if d.timestamp else None,
            },
            "transaction": {
                "transaction_id": d.transaction.id if d.transaction else d.transaction_id,
                "amount": d.transaction.amount if d.transaction else 0,
                "currency": d.transaction.currency if d.transaction else "",
                "sender": d.transaction.sender if d.transaction else "",
                "receiver": d.transaction.receiver if d.transaction else "",
                "sender_country": d.transaction.sender_country if d.transaction else "",
                "receiver_country": d.transaction.receiver_country if d.transaction else "",
            } if d.transaction else {}
        }

    def store_feedback(self, feedback_data: Dict[str, Any]) -> bool:
        db = SessionLocal()
        try:
            new_fb = DBFeedback(
                id=uuid.uuid4().hex,
                transaction_id=feedback_data.get("transaction_id", "unknown"),
                decision_id=feedback_data.get("decision_id", "unknown"),
                corrected_verdict=feedback_data.get("corrected_verdict", ""),
                corrected_reasoning=feedback_data.get("corrected_reasoning", ""),
                reviewer_notes=feedback_data.get("reviewer_notes", ""),
                reviewer_id=feedback_data.get("reviewer_id", "")
            )
            db.add(new_fb)
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Error storing feedback in DB: {e}")
            return False
        finally:
            db.close()

    def get_feedback_for_transaction(self, transaction_id: str) -> List[Dict[str, Any]]:
        db = SessionLocal()
        try:
            feedbacks = db.query(DBFeedback).filter(DBFeedback.transaction_id == transaction_id).order_by(DBFeedback.submitted_at.desc()).all()
            return [self._format_feedback(f) for f in feedbacks]
        except Exception as e:
            logger.error(f"Error retrieving feedback for {transaction_id}: {e}")
            return []
        finally:
            db.close()

    def list_all_feedback(self, limit: int = 100) -> List[Dict[str, Any]]:
        db = SessionLocal()
        try:
            feedbacks = db.query(DBFeedback).order_by(DBFeedback.submitted_at.desc()).limit(limit).all()
            return [self._format_feedback(f) for f in feedbacks]
        except Exception as e:
            logger.error(f"Error listing feedback from DB: {e}")
            return []
        finally:
            db.close()

    def _format_feedback(self, f: DBFeedback) -> Dict[str, Any]:
        return {
            "transaction_id": f.transaction_id,
            "decision_id": f.decision_id,
            "corrected_verdict": f.corrected_verdict,
            "corrected_reasoning": f.corrected_reasoning,
            "reviewer_notes": f.reviewer_notes,
            "reviewer_id": f.reviewer_id,
            "submitted_at": f.submitted_at.isoformat() if f.submitted_at else None
        }

    def save_json(self, data: Dict[str, Any], relative_path: str) -> bool:
        """Generic JSON save (e.g. for reports) - file-based"""
        try:
            target_path = self.storage_dir / relative_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with open(target_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str)
            return True
        except Exception as e:
            logger.error(f"Error saving JSON: {e}")
            return False

    def store_metrics(self, metrics_data: Dict[str, Any]) -> bool:
        """Persist overarching system metrics as a single JSON blob."""
        try:
            metrics_data["last_updated"] = datetime.now().isoformat()
            with open(self.metrics_file, 'w', encoding='utf-8') as f:
                json.dump(metrics_data, f, indent=2, default=str)
            return True
        except Exception as e:
            logger.error(f"Error storing metrics: {e}")
            return False

    def load_metrics(self) -> Optional[Dict[str, Any]]:
        try:
            if not self.metrics_file.exists():
                return None
            with open(self.metrics_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None

    def store_latency_data(self, operation_type: str, latency_ms: float, transaction_id: str = None) -> bool:
        db = SessionLocal()
        try:
            lat = DBLatency(
                operation_type=operation_type,
                latency_ms=latency_ms,
                transaction_id=transaction_id
            )
            db.add(lat)
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Error storing latency data: {e}")
            return False
        finally:
            db.close()

    def get_latency_statistics(self, operation_type: str = None, hours: int = None) -> Dict[str, Any]:
        db = SessionLocal()
        try:
            query = db.query(DBLatency.latency_ms)
            if operation_type:
                query = query.filter(DBLatency.operation_type == operation_type)
            if hours is not None:
                cutoff = datetime.utcnow() - timedelta(hours=hours)
                query = query.filter(DBLatency.timestamp >= cutoff)

            latencies = [row[0] for row in query.all()]

            if not latencies:
                return {"count": 0, "avg_ms": 0, "min_ms": 0, "max_ms": 0}

            sorted_latencies = sorted(latencies)
            count = len(sorted_latencies)

            return {
                "count": count,
                "avg_ms": round(sum(sorted_latencies) / count, 2),
                "min_ms": round(sorted_latencies[0], 2),
                "max_ms": round(sorted_latencies[-1], 2),
                "p50_ms": round(sorted_latencies[int(count * 0.5)], 2),
                "p95_ms": round(sorted_latencies[int(count * 0.95)], 2),
                "p99_ms": round(sorted_latencies[int(count * 0.99)], 2)
            }
        except Exception as e:
            logger.error(f"Error getting latency statistics: {e}")
            return {"count": 0, "avg_ms": 0, "min_ms": 0, "max_ms": 0}
        finally:
            db.close()

    def get_statistics(self) -> Dict[str, Any]:
        db = SessionLocal()
        try:
            dec_count = db.query(DBDecision).count()
            fb_count = db.query(DBFeedback).count()
            return {
                "total_decisions": dec_count,
                "total_feedback": fb_count,
                "storage_path": "sqlite:// (DB)"
            }
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {"total_decisions": 0, "total_feedback": 0, "storage_path": "error"}
        finally:
            db.close()

    def get_external_data_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        db = SessionLocal()
        try:
            history = db.query(DBExternalData).order_by(DBExternalData.timestamp.desc()).limit(limit).all()
            return [{
                "source": h.source,
                "status": h.status,
                "records_fetched": h.records_fetched,
                "message": h.message,
                "timestamp": h.timestamp.isoformat() if h.timestamp else None
            } for h in history]
        except Exception as e:
            logger.error(f"Error getting external data history: {e}")
            return []
        finally:
            db.close()

    def store_external_data_fetch(self, source: str, status: str, records_fetched: int, message: str = ""):
        db = SessionLocal()
        try:
            ext = DBExternalData(
                source=source,
                status=status,
                records_fetched=records_fetched,
                message=message
            )
            db.add(ext)
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Error storing external data fetch: {e}")
        finally:
            db.close()
