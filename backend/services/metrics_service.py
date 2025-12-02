from typing import Dict, Any, List
from datetime import datetime, timedelta
from collections import defaultdict, deque
import logging
import threading

logger = logging.getLogger(__name__)


class MetricsService:
    """In-memory metrics tracking for monitoring"""
    
    def __init__(self, demo_mode=False):
        self.lock = threading.Lock()
        self.demo_mode = demo_mode
        
        # Counters - initialize with demo data if in demo mode
        if demo_mode:
            self.total_evaluations = 3
            self.total_queries = 0
            self.total_policy_uploads = 3  # Show 3 demo policies as uploads
            self.total_feedback = 0
        else:
            self.total_evaluations = 0
            self.total_queries = 0
            self.total_policy_uploads = 0
            self.total_feedback = 0
        
        # Decision verdicts
        self.verdicts = defaultdict(int)  # FLAG, NEEDS_REVIEW, ACCEPTABLE
        self.risk_levels = defaultdict(int)  # HIGH, MEDIUM, LOW
        
        # Latency tracking (keep last 1000 measurements)
        self.evaluation_latencies = deque(maxlen=1000)
        self.query_latencies = deque(maxlen=1000)
        self.embedding_latencies = deque(maxlen=1000)
        
        # Error tracking
        self.errors = defaultdict(int)
        
        # Hourly decision tracking (last 24 hours)
        self.hourly_decisions = deque(maxlen=24)
        self._init_hourly_tracking()
        
        logger.info("Metrics service initialized")
    
    def _init_hourly_tracking(self):
        """Initialize hourly buckets"""
        now = datetime.now()
        for i in range(24):
            hour = (now - timedelta(hours=23-i)).replace(minute=0, second=0, microsecond=0)
            self.hourly_decisions.append({
                "hour": hour.isoformat(),
                "count": 0
            })
    
    def record_evaluation(self, verdict: str, risk_level: str, latency_ms: float):
        """Record a transaction evaluation"""
        with self.lock:
            self.total_evaluations += 1
            self.verdicts[verdict] += 1
            self.risk_levels[risk_level] += 1
            self.evaluation_latencies.append(latency_ms)
            
            # Update hourly tracking
            current_hour = datetime.now().replace(minute=0, second=0, microsecond=0)
            if self.hourly_decisions and self.hourly_decisions[-1]["hour"] == current_hour.isoformat():
                self.hourly_decisions[-1]["count"] += 1
            else:
                self.hourly_decisions.append({
                    "hour": current_hour.isoformat(),
                    "count": 1
                })
    
    def record_query(self, latency_ms: float):
        """Record a compliance query"""
        with self.lock:
            self.total_queries += 1
            self.query_latencies.append(latency_ms)
    
    def record_policy_upload(self):
        """Record a policy upload"""
        with self.lock:
            self.total_policy_uploads += 1
    
    def record_feedback(self):
        """Record feedback submission"""
        with self.lock:
            self.total_feedback += 1
    
    def record_embedding_latency(self, latency_ms: float):
        """Record embedding generation latency"""
        with self.lock:
            self.embedding_latencies.append(latency_ms)
    
    def record_error(self, error_type: str):
        """Record an error"""
        with self.lock:
            self.errors[error_type] += 1
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics snapshot"""
        with self.lock:
            return {
                "counters": {
                    "total_evaluations": self.total_evaluations,
                    "total_queries": self.total_queries,
                    "total_policy_uploads": self.total_policy_uploads,
                    "total_feedback": self.total_feedback
                },
                "decisions": {
                    "by_verdict": dict(self.verdicts),
                    "by_risk_level": dict(self.risk_levels)
                },
                "latency": {
                    "evaluation": self._calculate_latency_stats(self.evaluation_latencies),
                    "query": self._calculate_latency_stats(self.query_latencies),
                    "embedding": self._calculate_latency_stats(self.embedding_latencies)
                },
                "errors": dict(self.errors),
                "hourly_activity": list(self.hourly_decisions)
            }
    
    def _calculate_latency_stats(self, latencies: deque) -> Dict[str, float]:
        """Calculate latency statistics"""
        if not latencies:
            return {
                "count": 0,
                "avg_ms": 0.0,
                "min_ms": 0.0,
                "max_ms": 0.0,
                "p50_ms": 0.0,
                "p95_ms": 0.0,
                "p99_ms": 0.0
            }
        
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
    
    def reset_metrics(self):
        """Reset all metrics (useful for testing)"""
        with self.lock:
            self.total_evaluations = 0
            self.total_queries = 0
            self.total_policy_uploads = 0
            self.total_feedback = 0
            self.verdicts.clear()
            self.risk_levels.clear()
            self.evaluation_latencies.clear()
            self.query_latencies.clear()
            self.embedding_latencies.clear()
            self.errors.clear()
            self._init_hourly_tracking()
            logger.info("Metrics reset")
