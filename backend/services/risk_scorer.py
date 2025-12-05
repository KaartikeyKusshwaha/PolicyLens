"""
Risk Scoring Service with Case-Based Reasoning
Combines policy compliance with historical case similarity for enhanced risk assessment
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import numpy as np

logger = logging.getLogger(__name__)


class RiskScorer:
    """Advanced risk scoring using historical case comparison"""
    
    def __init__(self, milvus_service, embedding_service, storage_service):
        self.milvus = milvus_service
        self.embeddings = embedding_service
        self.storage = storage_service
        self.cases_collection = "compliance_cases"
        
    def calculate_composite_risk(
        self,
        transaction: Dict[str, Any],
        policy_analysis: Dict[str, Any],
        similarity_weight: float = 0.3
    ) -> Dict[str, Any]:
        """
        Calculate composite risk score combining policy analysis and case similarity
        
        Args:
            transaction: Transaction data
            policy_analysis: Result from compliance engine
            similarity_weight: Weight for case similarity (0.0-1.0)
            
        Returns:
            Enhanced risk assessment with historical context
        """
        try:
            # Base risk from policy analysis
            policy_risk = policy_analysis.get("risk_score", 0.0)
            
            # Get similar historical cases
            similar_cases = self._find_similar_cases(transaction, top_k=5)
            
            # Calculate case-based risk
            case_risk = self._calculate_case_risk(similar_cases)
            
            # Combine scores
            composite_score = (
                (1 - similarity_weight) * policy_risk +
                similarity_weight * case_risk
            )
            
            # Determine verdict based on composite score
            verdict = self._determine_verdict(composite_score)
            
            # Build risk factors
            risk_factors = self._identify_risk_factors(
                transaction, 
                policy_analysis, 
                similar_cases
            )
            
            return {
                "composite_risk_score": round(composite_score, 3),
                "policy_risk_score": round(policy_risk, 3),
                "case_similarity_risk": round(case_risk, 3),
                "verdict": verdict,
                "similar_cases_found": len(similar_cases),
                "risk_factors": risk_factors,
                "similar_cases": similar_cases[:3],  # Top 3 for context
                "confidence": self._calculate_confidence(similar_cases, policy_risk),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Risk scoring failed: {e}")
            # Fallback to policy-only risk
            return {
                "composite_risk_score": policy_analysis.get("risk_score", 0.0),
                "policy_risk_score": policy_analysis.get("risk_score", 0.0),
                "case_similarity_risk": 0.0,
                "verdict": policy_analysis.get("verdict", "REVIEW"),
                "similar_cases_found": 0,
                "risk_factors": [],
                "error": str(e)
            }
    
    def _find_similar_cases(
        self, 
        transaction: Dict[str, Any], 
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Find historically similar transactions"""
        try:
            if not self.milvus or not self.milvus.connected:
                return []
            
            # Create transaction description for embedding
            description = self._transaction_to_text(transaction)
            
            # Generate embedding
            query_embedding = self.embeddings.embed_text(description)
            
            # Search Milvus cases collection
            results = self.milvus.search_cases(
                query_embedding=query_embedding,
                top_k=top_k,
                filter_expr="verdict in ['FLAG', 'REVIEW']"  # Only flagged cases
            )
            
            # Enrich with stored decision data
            enriched_cases = []
            for result in results:
                case_id = result.get("case_id")
                similarity = result.get("distance", 0.0)
                
                # Convert distance to similarity score (assuming cosine distance)
                similarity_score = 1 - similarity
                
                enriched_cases.append({
                    "case_id": case_id,
                    "similarity_score": round(similarity_score, 3),
                    "verdict": result.get("verdict"),
                    "risk_score": result.get("risk_score"),
                    "reason": result.get("reason", "Historical case match"),
                    "metadata": result.get("metadata", {})
                })
            
            return enriched_cases
            
        except Exception as e:
            logger.warning(f"Case similarity search failed: {e}")
            return []
    
    def _calculate_case_risk(self, similar_cases: List[Dict[str, Any]]) -> float:
        """Calculate risk score from similar historical cases"""
        if not similar_cases:
            return 0.5  # Neutral risk if no cases found
        
        # Weighted average of similar case risk scores
        total_weight = 0
        weighted_risk = 0
        
        for case in similar_cases:
            similarity = case.get("similarity_score", 0)
            case_risk = case.get("risk_score", 0.5)
            
            # Weight by similarity (more similar = more weight)
            weight = similarity ** 2  # Square to emphasize high similarity
            weighted_risk += weight * case_risk
            total_weight += weight
        
        if total_weight > 0:
            return weighted_risk / total_weight
        return 0.5
    
    def _determine_verdict(self, composite_score: float) -> str:
        """Determine verdict from composite risk score"""
        if composite_score >= 0.75:
            return "FLAG"
        elif composite_score >= 0.45:
            return "REVIEW"
        else:
            return "CLEAR"
    
    def _identify_risk_factors(
        self,
        transaction: Dict[str, Any],
        policy_analysis: Dict[str, Any],
        similar_cases: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """Identify specific risk factors from analysis and cases"""
        factors = []
        
        # Amount-based risk
        amount = transaction.get("amount", 0)
        if amount > 50000:
            factors.append({
                "factor": "High Transaction Amount",
                "value": f"${amount:,.2f}",
                "severity": "high" if amount > 100000 else "medium"
            })
        
        # Policy violations
        citations = policy_analysis.get("citations", [])
        if citations:
            factors.append({
                "factor": "Policy Violations Detected",
                "value": f"{len(citations)} policies cited",
                "severity": "high"
            })
        
        # Historical pattern matching
        if similar_cases:
            flagged_cases = [c for c in similar_cases if c.get("verdict") == "FLAG"]
            if flagged_cases:
                avg_similarity = np.mean([c.get("similarity_score", 0) for c in flagged_cases])
                factors.append({
                    "factor": "Similar Flagged Transactions",
                    "value": f"{len(flagged_cases)} cases (avg similarity: {avg_similarity:.2%})",
                    "severity": "high" if avg_similarity > 0.8 else "medium"
                })
        
        # Country risk
        country = transaction.get("country", "").upper()
        high_risk_countries = ["IR", "KP", "SY", "CU"]  # Example list
        if country in high_risk_countries:
            factors.append({
                "factor": "High-Risk Country",
                "value": country,
                "severity": "high"
            })
        
        # Transaction type risk
        tx_type = transaction.get("type", "").upper()
        if tx_type in ["WIRE_TRANSFER", "CASH"]:
            factors.append({
                "factor": "High-Risk Transaction Type",
                "value": tx_type,
                "severity": "medium"
            })
        
        return factors
    
    def _calculate_confidence(
        self, 
        similar_cases: List[Dict[str, Any]], 
        policy_risk: float
    ) -> str:
        """Calculate confidence level in risk assessment"""
        if not similar_cases:
            return "medium"  # Only policy-based
        
        # High confidence if we have similar cases and consistent signals
        avg_similarity = np.mean([c.get("similarity_score", 0) for c in similar_cases])
        
        if avg_similarity > 0.7 and len(similar_cases) >= 3:
            return "high"
        elif avg_similarity > 0.5:
            return "medium"
        else:
            return "low"
    
    def _transaction_to_text(self, transaction: Dict[str, Any]) -> str:
        """Convert transaction to text description for embedding"""
        parts = []
        
        # Amount and type
        amount = transaction.get("amount", 0)
        tx_type = transaction.get("type", "transaction")
        parts.append(f"{tx_type} of ${amount:,.2f}")
        
        # Parties
        if "sender" in transaction:
            parts.append(f"from {transaction['sender']}")
        if "receiver" in transaction:
            parts.append(f"to {transaction['receiver']}")
        
        # Location
        if "country" in transaction:
            parts.append(f"in {transaction['country']}")
        
        # Description
        if "description" in transaction:
            parts.append(f"described as: {transaction['description']}")
        
        return " ".join(parts)
    
    def store_case_for_learning(
        self, 
        decision_id: str,
        transaction: Dict[str, Any],
        verdict: str,
        risk_score: float,
        reasoning: str
    ) -> bool:
        """
        Store a decision as a case in Milvus for future similarity matching
        
        Args:
            decision_id: Unique decision identifier
            transaction: Transaction data
            verdict: Final verdict
            risk_score: Calculated risk score
            reasoning: Explanation for the decision
            
        Returns:
            Success status
        """
        try:
            if not self.milvus or not self.milvus.connected:
                logger.warning("Milvus not connected, skipping case storage")
                return False
            
            # Only store flagged or reviewed cases for learning
            if verdict not in ["FLAG", "REVIEW"]:
                return True  # Success but not stored
            
            # Create case description
            description = self._transaction_to_text(transaction)
            
            # Generate embedding
            embedding = self.embeddings.embed_text(description)
            
            # Prepare case data
            case_data = {
                "case_id": decision_id,
                "embedding": embedding,
                "verdict": verdict,
                "risk_score": risk_score,
                "reason": reasoning[:500],  # Truncate for storage
                "metadata": {
                    "amount": transaction.get("amount", 0),
                    "type": transaction.get("type", "unknown"),
                    "country": transaction.get("country", "unknown"),
                    "timestamp": datetime.now().isoformat()
                }
            }
            
            # Insert into Milvus
            self.milvus.insert_case(case_data)
            
            logger.info(f"Stored case {decision_id} for future learning")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store case: {e}")
            return False
    
    def get_risk_statistics(self) -> Dict[str, Any]:
        """Get statistics about stored cases and risk patterns"""
        try:
            all_decisions = self.storage.get_all_decisions()
            
            if not all_decisions:
                return {
                    "total_cases": 0,
                    "flagged_cases": 0,
                    "average_risk_score": 0.0,
                    "verdict_distribution": {}
                }
            
            # Calculate statistics
            flagged = [d for d in all_decisions if d.get("verdict") == "FLAG"]
            reviewed = [d for d in all_decisions if d.get("verdict") == "REVIEW"]
            cleared = [d for d in all_decisions if d.get("verdict") == "CLEAR"]
            
            avg_risk = np.mean([d.get("risk_score", 0) for d in all_decisions])
            
            return {
                "total_cases": len(all_decisions),
                "flagged_cases": len(flagged),
                "reviewed_cases": len(reviewed),
                "cleared_cases": len(cleared),
                "average_risk_score": round(avg_risk, 3),
                "verdict_distribution": {
                    "FLAG": len(flagged),
                    "REVIEW": len(reviewed),
                    "CLEAR": len(cleared)
                },
                "high_risk_percentage": round(len(flagged) / len(all_decisions) * 100, 1)
            }
            
        except Exception as e:
            logger.error(f"Failed to get risk statistics: {e}")
            return {"error": str(e)}
