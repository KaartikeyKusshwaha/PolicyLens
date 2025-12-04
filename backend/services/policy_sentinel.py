from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
from difflib import SequenceMatcher
from services.milvus_service import MilvusService
from services.storage_service import StorageService

logger = logging.getLogger(__name__)


class PolicySentinel:
    """Monitors policy changes and triggers re-evaluations"""
    
    def __init__(self, milvus_service: MilvusService, storage_service: StorageService):
        self.milvus_service = milvus_service
        self.storage_service = storage_service
    
    def detect_policy_change(self, old_doc_id: str, new_doc_id: str, old_text: str, new_text: str) -> Dict[str, Any]:
        """Detect and analyze changes between policy versions"""
        
        # Calculate similarity ratio
        similarity = SequenceMatcher(None, old_text, new_text).ratio()
        change_magnitude = 1.0 - similarity
        
        # Detect specific changes
        changes = {
            "old_doc_id": old_doc_id,
            "new_doc_id": new_doc_id,
            "similarity_ratio": round(similarity, 4),
            "change_magnitude": round(change_magnitude, 4),
            "timestamp": datetime.now().isoformat(),
            "change_type": self._classify_change(change_magnitude),
            "sections_affected": self._detect_affected_sections(old_text, new_text)
        }
        
        logger.info(f"Policy change detected: {change_magnitude:.2%} difference between versions")
        
        # Store change record
        self._store_change_record(changes)
        
        return changes
    
    def _classify_change(self, magnitude: float) -> str:
        """Classify the magnitude of change"""
        if magnitude < 0.05:
            return "MINOR"
        elif magnitude < 0.20:
            return "MODERATE"
        else:
            return "MAJOR"
    
    def _detect_affected_sections(self, old_text: str, new_text: str) -> List[str]:
        """Detect which sections were affected by changes"""
        affected = []
        
        # Simple section detection based on common patterns
        import re
        section_pattern = r'^(?:Section|Article|Chapter|\d+\.?\d*)\s+([^\n:]+)'
        
        old_sections = set(re.findall(section_pattern, old_text, re.MULTILINE | re.IGNORECASE))
        new_sections = set(re.findall(section_pattern, new_text, re.MULTILINE | re.IGNORECASE))
        
        # Sections removed or modified
        for section in old_sections:
            if section not in new_sections:
                affected.append(f"Removed: {section}")
        
        # Sections added
        for section in new_sections:
            if section not in old_sections:
                affected.append(f"Added: {section}")
        
        return affected if affected else ["Content-level changes detected"]
    
    def identify_impacted_decisions(self, doc_id: str) -> List[str]:
        """Identify past decisions that used this policy"""
        try:
            # Get all stored decisions
            decisions = self.storage_service.list_decisions(limit=1000)
            
            impacted_decision_ids = []
            
            for decision in decisions:
                # Check if this policy was cited in the decision
                citations = decision.get("reasoning", {}).get("citations", [])
                
                for citation in citations:
                    if citation.get("doc_id") == doc_id:
                        impacted_decision_ids.append(decision.get("trace_id"))
                        break
            
            logger.info(f"Found {len(impacted_decision_ids)} decisions impacted by policy {doc_id}")
            return impacted_decision_ids
        
        except Exception as e:
            logger.error(f"Error identifying impacted decisions: {e}")
            return []
    
    def trigger_re_evaluation(self, decision_ids: List[str]) -> Dict[str, Any]:
        """Trigger re-evaluation for impacted decisions"""
        
        re_evaluation_queue = {
            "timestamp": datetime.now().isoformat(),
            "total_decisions": len(decision_ids),
            "decision_ids": decision_ids,
            "status": "QUEUED",
            "message": f"Re-evaluation queued for {len(decision_ids)} decisions"
        }
        
        # Store re-evaluation queue
        self._store_re_evaluation_queue(re_evaluation_queue)
        
        logger.info(f"Queued {len(decision_ids)} decisions for re-evaluation")
        
        return re_evaluation_queue
    
    def generate_change_impact_report(self, change_data: Dict[str, Any], impacted_decisions: List[str]) -> Dict[str, Any]:
        """Generate comprehensive change impact report"""
        
        report = {
            "report_id": f"IMPACT_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "generated_at": datetime.now().isoformat(),
            "policy_change": change_data,
            "impact_summary": {
                "decisions_affected": len(impacted_decisions),
                "change_magnitude": change_data.get("change_magnitude"),
                "change_type": change_data.get("change_type"),
                "requires_re_evaluation": change_data.get("change_magnitude", 0) > 0.10
            },
            "affected_decision_ids": impacted_decisions[:50],  # Limit to first 50
            "recommendations": self._generate_recommendations(change_data, len(impacted_decisions))
        }
        
        # Store impact report
        self._store_impact_report(report)
        
        logger.info(f"Generated change impact report: {report['report_id']}")
        
        return report
    
    def _generate_recommendations(self, change_data: Dict[str, Any], num_impacted: int) -> List[str]:
        """Generate recommendations based on change analysis"""
        recommendations = []
        
        change_type = change_data.get("change_type")
        
        if change_type == "MAJOR":
            recommendations.append("CRITICAL: Major policy change detected - immediate review required")
            recommendations.append(f"Re-evaluate all {num_impacted} affected decisions")
            recommendations.append("Consider notifying compliance team of significant policy update")
        elif change_type == "MODERATE":
            recommendations.append("IMPORTANT: Moderate policy change - review recommended")
            recommendations.append(f"Consider re-evaluating {num_impacted} affected decisions")
        else:
            recommendations.append("Minor policy update - monitoring suggested")
        
        if num_impacted > 100:
            recommendations.append("High impact: Large number of decisions affected - prioritize review")
        
        return recommendations
    
    def _store_change_record(self, change_data: Dict[str, Any]):
        """Store policy change record"""
        try:
            filename = f"policy_change_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            filepath = self.storage_service.storage_dir / "policy_changes" / filename
            filepath.parent.mkdir(exist_ok=True)
            
            import json
            with open(filepath, 'w') as f:
                json.dump(change_data, f, indent=2, default=str)
            
            logger.info(f"Stored policy change record: {filename}")
        except Exception as e:
            logger.error(f"Error storing change record: {e}")
    
    def _store_re_evaluation_queue(self, queue_data: Dict[str, Any]):
        """Store re-evaluation queue"""
        try:
            filename = f"re_eval_queue_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            filepath = self.storage_service.storage_dir / "re_evaluation" / filename
            filepath.parent.mkdir(exist_ok=True)
            
            import json
            with open(filepath, 'w') as f:
                json.dump(queue_data, f, indent=2, default=str)
            
            logger.info(f"Stored re-evaluation queue: {filename}")
        except Exception as e:
            logger.error(f"Error storing re-evaluation queue: {e}")
    
    def _store_impact_report(self, report: Dict[str, Any]):
        """Store impact report"""
        try:
            filename = f"{report['report_id']}.json"
            filepath = self.storage_service.storage_dir / "impact_reports" / filename
            filepath.parent.mkdir(exist_ok=True)
            
            import json
            with open(filepath, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            
            logger.info(f"Stored impact report: {filename}")
        except Exception as e:
            logger.error(f"Error storing impact report: {e}")
    
    def get_recent_changes(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent policy changes"""
        try:
            changes_dir = self.storage_service.storage_dir / "policy_changes"
            if not changes_dir.exists():
                return []
            
            change_files = sorted(
                changes_dir.glob("*.json"),
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )
            
            changes = []
            import json
            for file_path in change_files[:limit]:
                with open(file_path, 'r') as f:
                    changes.append(json.load(f))
            
            return changes
        except Exception as e:
            logger.error(f"Error retrieving recent changes: {e}")
            return []
    
    def get_impact_reports(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent impact reports"""
        try:
            reports_dir = self.storage_service.storage_dir / "impact_reports"
            if not reports_dir.exists():
                return []
            
            report_files = sorted(
                reports_dir.glob("*.json"),
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )
            
            reports = []
            import json
            for file_path in report_files[:limit]:
                with open(file_path, 'r') as f:
                    reports.append(json.load(f))
            
            return reports
        except Exception as e:
            logger.error(f"Error retrieving impact reports: {e}")
            return []
