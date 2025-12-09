"""
Batch Re-evaluation Service
Enables bulk re-evaluation of past transactions when policies change
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor
from models import Transaction

logger = logging.getLogger(__name__)


class BatchProcessor:
    """Service for batch re-evaluation of transactions"""
    
    def __init__(self, compliance_engine, storage_service):
        self.compliance_engine = compliance_engine
        self.storage = storage_service
        self.executor = ThreadPoolExecutor(max_workers=5)
        
    async def reevaluate_all_decisions(
        self, 
        filter_by: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Re-evaluate all stored decisions
        
        Args:
            filter_by: Optional filters (e.g., {"verdict": "FLAG", "date_from": "2024-01-01"})
            
        Returns:
            Summary of re-evaluation results
        """
        try:
            # Get all decisions from storage
            all_decisions = self.storage.get_all_decisions()
            
            if not all_decisions:
                return {
                    "status": "completed",
                    "total_decisions": 0,
                    "re_evaluated": 0,
                    "verdicts_changed": 0,
                    "changes": []
                }
            
            # Apply filters if provided
            decisions_to_process = self._apply_filters(all_decisions, filter_by)
            
            logger.info(f"Starting batch re-evaluation of {len(decisions_to_process)} decisions")
            
            # Track changes
            changes = []
            verdicts_changed = 0
            successfully_evaluated = 0
            
            # Re-evaluate each decision
            for idx, old_decision in enumerate(decisions_to_process, 1):
                try:
                    # Extract original transaction data
                    transaction = old_decision.get("transaction", {})
                    
                    if not transaction:
                        logger.warning(f"Skipping decision {old_decision.get('decision_id')} - no transaction data")
                        continue
                    
                    # Re-evaluate with current policies
                    try:
                        tx_model = Transaction(**transaction)
                    except Exception:
                        # If schema mismatch, try passing through
                        tx_model = Transaction.model_validate(transaction)

                    new_eval = self.compliance_engine.evaluate_transaction(tx_model)
                    
                    successfully_evaluated += 1
                    
                    # Compare verdicts
                    old_verdict = (old_decision.get("decision") or {}).get("verdict")
                    new_verdict = new_eval.get("decision").verdict.value if new_eval.get("decision") else None
                    
                    if old_verdict != new_verdict:
                        verdicts_changed += 1
                        changes.append({
                            "transaction_id": transaction.get("transaction_id"),
                            "decision_id": old_decision.get("trace_id") or old_decision.get("decision_id"),
                            "old_verdict": old_verdict,
                            "new_verdict": new_verdict,
                            "old_risk_score": (old_decision.get("decision") or {}).get("risk_score"),
                            "new_risk_score": new_eval.get("decision").risk_score if new_eval.get("decision") else None,
                            "re_evaluation_date": datetime.now().isoformat(),
                            "reason_for_change": self._analyze_change_reason(old_decision, new_eval)
                        })
                    
                    # Log progress every 10 decisions
                    if idx % 10 == 0:
                        logger.info(f"Progress: {idx}/{len(decisions_to_process)} decisions processed")
                        
                except Exception as e:
                    logger.error(f"Error re-evaluating decision {old_decision.get('decision_id')}: {e}")
                    continue
            
            summary = {
                "status": "completed",
                "total_decisions": len(all_decisions),
                "filtered_decisions": len(decisions_to_process),
                "re_evaluated": successfully_evaluated,
                "verdicts_changed": verdicts_changed,
                "changes": changes,
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"Batch re-evaluation completed: {successfully_evaluated} processed, {verdicts_changed} changed")
            
            return summary
            
        except Exception as e:
            logger.error(f"Batch re-evaluation failed: {e}")
            return {
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def reevaluate_by_policy(self, policy_id: str) -> Dict[str, Any]:
        """
        Re-evaluate decisions that were influenced by a specific policy
        
        Args:
            policy_id: ID of the policy that changed
            
        Returns:
            Summary of affected decisions
        """
        try:
            all_decisions = self.storage.get_all_decisions()
            affected_decisions = []
            
            # Find decisions that used this policy
            for decision in all_decisions:
                decision_block = decision.get("decision", {})
                citations = decision_block.get("policy_citations", [])
                policy_ids = [c.get("doc_id") for c in citations if c.get("doc_id")]
                
                if policy_id in policy_ids:
                    affected_decisions.append(decision)
            
            logger.info(f"Found {len(affected_decisions)} decisions affected by policy {policy_id}")
            
            # Re-evaluate affected decisions
            filter_by = {"trace_ids": [d.get("trace_id") or d.get("decision_id") for d in affected_decisions]}
            return await self.reevaluate_all_decisions(filter_by)
            
        except Exception as e:
            logger.error(f"Policy-based re-evaluation failed: {e}")
            return {"status": "failed", "error": str(e)}
    
    def get_reevaluation_candidates(
        self, 
        days_old: int = 30,
        verdict_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Identify decisions that are candidates for re-evaluation
        
        Args:
            days_old: Consider decisions older than this many days
            verdict_filter: Filter by specific verdict (FLAG, REVIEW, CLEAR)
            
        Returns:
            List of decisions that should be re-evaluated
        """
        try:
            all_decisions = self.storage.get_all_decisions()
            candidates = []
            
            cutoff_date = datetime.now().timestamp() - (days_old * 24 * 60 * 60)
            
            for decision in all_decisions:
                # Prefer stored_at at top-level, fallback to decision.timestamp
                ts_iso = decision.get("stored_at") or (decision.get("decision", {}).get("timestamp"))
                try:
                    timestamp = datetime.fromisoformat(ts_iso).timestamp() if ts_iso else 0
                except Exception:
                    timestamp = 0
                verdict = (decision.get("decision") or {}).get("verdict")
                
                # Check age
                if timestamp < cutoff_date:
                    # Check verdict filter
                    if verdict_filter is None or (verdict or '').lower() == verdict_filter.lower():
                        candidates.append({
                            "decision_id": decision.get("trace_id") or decision.get("decision_id"),
                            "transaction_id": decision.get("transaction", {}).get("transaction_id"),
                            "verdict": verdict,
                            "age_days": int((datetime.now().timestamp() - timestamp) / 86400),
                            "risk_score": (decision.get("decision") or {}).get("risk_score"),
                            "reason": f"Decision is {int((datetime.now().timestamp() - timestamp) / 86400)} days old"
                        })
            
            logger.info(f"Identified {len(candidates)} re-evaluation candidates")
            return candidates
            
        except Exception as e:
            logger.error(f"Error identifying candidates: {e}")
            return []
    
    def _apply_filters(
        self, 
        decisions: List[Dict[str, Any]], 
        filters: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Apply filters to decision list"""
        if not filters:
            return decisions
        
        filtered = decisions
        
        # Filter by verdict
        if "verdict" in filters:
            filtered = [d for d in filtered if d.get("verdict") == filters["verdict"]]
        
        # Filter by decision IDs (trace IDs)
        if "trace_ids" in filters:
            trace_ids = set([tid for tid in filters["trace_ids"] if tid])
            filtered = [d for d in filtered if (d.get("trace_id") or d.get("decision_id")) in trace_ids]
        
        # Filter by date range
        if "date_from" in filters:
            from_timestamp = datetime.fromisoformat(filters["date_from"]).timestamp()
            filtered = [d for d in filtered if d.get("timestamp", 0) >= from_timestamp]
        
        if "date_to" in filters:
            to_timestamp = datetime.fromisoformat(filters["date_to"]).timestamp()
            filtered = [d for d in filtered if d.get("timestamp", 0) <= to_timestamp]
        
        return filtered
    
    def _analyze_change_reason(
        self, 
        old_decision: Dict[str, Any], 
        new_result: Dict[str, Any]
    ) -> str:
        """Analyze why a verdict changed"""
        reasons = []
        
        # Compare risk scores
        old_risk = (old_decision.get("decision") or {}).get("risk_score", 0)
        new_risk = (new_result.get("decision").risk_score if new_result.get("decision") else 0)
        
        if abs(new_risk - old_risk) > 0.1:
            if new_risk > old_risk:
                reasons.append(f"Risk score increased from {old_risk:.2f} to {new_risk:.2f}")
            else:
                reasons.append(f"Risk score decreased from {old_risk:.2f} to {new_risk:.2f}")
        
        # Compare number of citations
        old_citations = len((old_decision.get("decision") or {}).get("policy_citations", []))
        new_citations = len((new_result.get("decision").policy_citations if new_result.get("decision") else []) or [])
        
        if old_citations != new_citations:
            reasons.append(f"Policy citations changed from {old_citations} to {new_citations}")
        
        # Compare reasoning
        old_reasoning = (old_decision.get("decision") or {}).get("reasoning", "")
        new_reasoning = (new_result.get("decision").reasoning if new_result.get("decision") else "")
        
        if old_reasoning != new_reasoning:
            reasons.append("Policy reasoning updated")
        
        return " | ".join(reasons) if reasons else "Policy updates affected decision criteria"
    
    def generate_impact_report(
        self, 
        reevaluation_summary: Dict[str, Any]
    ) -> str:
        """
        Generate a human-readable impact report
        
        Args:
            reevaluation_summary: Result from reevaluate_all_decisions
            
        Returns:
            Formatted report string
        """
        changes = reevaluation_summary.get("changes", [])
        
        report = [
            "=" * 60,
            "BATCH RE-EVALUATION IMPACT REPORT",
            "=" * 60,
            f"Timestamp: {reevaluation_summary.get('timestamp', 'N/A')}",
            f"Total Decisions: {reevaluation_summary.get('total_decisions', 0)}",
            f"Re-evaluated: {reevaluation_summary.get('re_evaluated', 0)}",
            f"Verdicts Changed: {reevaluation_summary.get('verdicts_changed', 0)}",
            "",
            "VERDICT CHANGES:",
            "-" * 60
        ]
        
        if not changes:
            report.append("No verdict changes detected")
        else:
            for idx, change in enumerate(changes, 1):
                report.extend([
                    f"\n{idx}. Transaction: {change.get('transaction_id')}",
                    f"   Old Verdict: {change.get('old_verdict')} (Risk: {change.get('old_risk_score', 0):.2f})",
                    f"   New Verdict: {change.get('new_verdict')} (Risk: {change.get('new_risk_score', 0):.2f})",
                    f"   Reason: {change.get('reason_for_change')}"
                ])
        
        report.append("\n" + "=" * 60)
        
        return "\n".join(report)
