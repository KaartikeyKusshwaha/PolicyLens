import json
import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class StorageService:
    """Simple file-based storage for decisions and feedback"""
    
    def __init__(self, storage_dir: str = "data"):
        self.storage_dir = Path(storage_dir)
        self.decisions_dir = self.storage_dir / "decisions"
        self.feedback_dir = self.storage_dir / "feedback"
        self.metrics_file = self.storage_dir / "metrics.json"
        
        # Create directories
        self.decisions_dir.mkdir(parents=True, exist_ok=True)
        self.feedback_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Storage service initialized at {self.storage_dir}")
    
    def store_decision(self, trace_id: str, decision_data: Dict[str, Any]) -> bool:
        """Store a compliance decision"""
        try:
            file_path = self.decisions_dir / f"{trace_id}.json"
            
            # Add storage timestamp
            decision_data["stored_at"] = datetime.now().isoformat()
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(decision_data, f, indent=2, default=str)
            
            logger.info(f"Decision stored: {trace_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error storing decision {trace_id}: {e}")
            return False
    
    def get_decision(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a decision by trace ID"""
        try:
            file_path = self.decisions_dir / f"{trace_id}.json"
            
            if not file_path.exists():
                return None
            
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
                
        except Exception as e:
            logger.error(f"Error retrieving decision {trace_id}: {e}")
            return None
    
    def list_decisions(self, limit: int = 100, skip: int = 0) -> List[Dict[str, Any]]:
        """List recent decisions"""
        try:
            decision_files = sorted(
                self.decisions_dir.glob("*.json"),
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )
            
            decisions = []
            for file_path in decision_files[skip:skip + limit]:
                with open(file_path, 'r', encoding='utf-8') as f:
                    decisions.append(json.load(f))
            
            return decisions
            
        except Exception as e:
            logger.error(f"Error listing decisions: {e}")
            return []
    
    def store_feedback(self, feedback_data: Dict[str, Any]) -> bool:
        """Store human feedback"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            transaction_id = feedback_data.get("transaction_id", "unknown")
            file_path = self.feedback_dir / f"{transaction_id}_{timestamp}.json"
            
            feedback_data["submitted_at"] = datetime.now().isoformat()
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(feedback_data, f, indent=2, default=str)
            
            logger.info(f"Feedback stored for transaction {transaction_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error storing feedback: {e}")
            return False
    
    def get_feedback_for_transaction(self, transaction_id: str) -> List[Dict[str, Any]]:
        """Get all feedback for a specific transaction"""
        try:
            feedback_files = self.feedback_dir.glob(f"{transaction_id}_*.json")
            
            feedback_list = []
            for file_path in feedback_files:
                with open(file_path, 'r', encoding='utf-8') as f:
                    feedback_list.append(json.load(f))
            
            return sorted(feedback_list, key=lambda x: x.get("submitted_at", ""), reverse=True)
            
        except Exception as e:
            logger.error(f"Error retrieving feedback for {transaction_id}: {e}")
            return []
    
    def list_all_feedback(self, limit: int = 100) -> List[Dict[str, Any]]:
        """List recent feedback"""
        try:
            feedback_files = sorted(
                self.feedback_dir.glob("*.json"),
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )
            
            feedback_list = []
            for file_path in feedback_files[:limit]:
                with open(file_path, 'r', encoding='utf-8') as f:
                    feedback_list.append(json.load(f))
            
            return feedback_list
            
        except Exception as e:
            logger.error(f"Error listing feedback: {e}")
            return []
    
    def store_metrics(self, metrics_data: Dict[str, Any]) -> bool:
        """Store metrics to disk"""
        try:
            metrics_data["last_updated"] = datetime.now().isoformat()
            
            with open(self.metrics_file, 'w', encoding='utf-8') as f:
                json.dump(metrics_data, f, indent=2, default=str)
            
            return True
            
        except Exception as e:
            logger.error(f"Error storing metrics: {e}")
            return False
    
    def store_latency_data(self, operation_type: str, latency_ms: float, transaction_id: str = None) -> bool:
        """Store individual latency measurement for analysis"""
        try:
            latency_file = self.storage_dir / "latencies.jsonl"
            
            latency_record = {
                "timestamp": datetime.now().isoformat(),
                "operation_type": operation_type,
                "latency_ms": latency_ms,
                "transaction_id": transaction_id
            }
            
            # Append to JSONL file (one JSON object per line)
            with open(latency_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(latency_record, default=str) + '\n')
            
            return True
            
        except Exception as e:
            logger.error(f"Error storing latency data: {e}")
            return False
    
    def get_latency_statistics(self, operation_type: str = None, hours: int = None) -> Dict[str, Any]:
        """Get latency statistics from stored data
        
        Args:
            operation_type: Filter by operation type ('evaluation' or 'query'). If None, returns all.
            hours: Number of hours to look back. If None, returns all-time data.
        """
        try:
            latency_file = self.storage_dir / "latencies.jsonl"
            
            if not latency_file.exists():
                return {"count": 0, "avg_ms": 0, "min_ms": 0, "max_ms": 0}
            
            cutoff_time = datetime.now() - timedelta(hours=hours) if hours is not None else None
            latencies = []
            
            with open(latency_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        record = json.loads(line.strip())
                        record_time = datetime.fromisoformat(record["timestamp"])
                        
                        # Filter by time and operation type
                        if cutoff_time is None or record_time >= cutoff_time:
                            if operation_type is None or record["operation_type"] == operation_type:
                                latencies.append(record["latency_ms"])
                    except (json.JSONDecodeError, KeyError, ValueError):
                        continue
            
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
    
    def load_metrics(self) -> Optional[Dict[str, Any]]:
        """Load metrics from disk"""
        try:
            if not self.metrics_file.exists():
                return None
            
            with open(self.metrics_file, 'r', encoding='utf-8') as f:
                return json.load(f)
                
        except Exception as e:
            logger.error(f"Error loading metrics: {e}")
            return None
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get storage statistics"""
        try:
            decision_count = len(list(self.decisions_dir.glob("*.json")))
            feedback_count = len(list(self.feedback_dir.glob("*.json")))
            
            return {
                "total_decisions": decision_count,
                "total_feedback": feedback_count,
                "storage_path": str(self.storage_dir)
            }
            
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {
                "total_decisions": 0,
                "total_feedback": 0,
                "storage_path": str(self.storage_dir)
            }
