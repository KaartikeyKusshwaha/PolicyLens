from typing import List, Dict, Any
import uuid
from datetime import datetime
import time
import logging
from models import (
    Transaction, ComplianceDecision, DecisionVerdict, RiskLevel,
    PolicyCitation, SimilarCase
)
from services.embedding_service import EmbeddingService
from services.milvus_service import MilvusService
from services.llm_service import LLMService
from config import settings

logger = logging.getLogger(__name__)


class ComplianceEngine:
    def __init__(
        self,
        embedding_service: EmbeddingService,
        milvus_service: MilvusService,
        llm_service: LLMService
    ):
        self.embedding_service = embedding_service
        self.milvus_service = milvus_service
        self.llm_service = llm_service
    
    def evaluate_transaction(self, transaction: Transaction) -> Dict[str, Any]:
        """Evaluate a transaction against compliance policies"""
        
        start_time = time.time()
        trace_id = str(uuid.uuid4())
        
        logger.info(f"[{trace_id}] Evaluating transaction: {transaction.transaction_id}")
        
        # Step 1: Create transaction embedding
        transaction_text = self._transaction_to_text(transaction)
        transaction_embedding = self.embedding_service.generate_embedding(transaction_text)
        
        # Step 2: Retrieve relevant policies
        relevant_policies = self.milvus_service.search_similar_policies(
            query_embedding=transaction_embedding,
            top_k=settings.top_k_results,
            active_only=True
        )
        
        logger.info(f"[{trace_id}] Retrieved {len(relevant_policies)} relevant policies")
        
        # Step 3: Retrieve similar historical cases
        similar_cases = self.milvus_service.search_similar_cases(
            query_embedding=transaction_embedding,
            top_k=3
        )
        
        logger.info(f"[{trace_id}] Found {len(similar_cases)} similar cases")
        
        # Step 4: LLM evaluation
        transaction_dict = transaction.model_dump()
        llm_result = self.llm_service.evaluate_transaction(
            transaction=transaction_dict,
            policy_context=relevant_policies,
            similar_cases=similar_cases
        )
        
        # Step 5: Build compliance decision
        policy_citations = [
            PolicyCitation(
                doc_id=policy["doc_id"],
                doc_title=policy["doc_title"],
                section=policy.get("section"),
                text=policy["text"][:500],  # Truncate for display
                relevance_score=policy["relevance_score"],
                version=policy["version"]
            )
            for policy in relevant_policies
        ]
        
        similar_case_objects = [
            SimilarCase(
                case_id=case["case_id"],
                transaction_id=case["transaction_id"],
                similarity_score=case["similarity_score"],
                decision=DecisionVerdict(case["decision"].lower()),
                reasoning=case["reasoning"],
                timestamp=case["timestamp"]
            )
            for case in similar_cases
        ]
        
        decision = ComplianceDecision(
            transaction_id=transaction.transaction_id,
            verdict=DecisionVerdict(llm_result["verdict"].lower()),
            risk_level=RiskLevel(llm_result["risk_level"].lower()),
            risk_score=llm_result["risk_score"],
            reasoning=llm_result["reasoning"],
            policy_citations=policy_citations,
            similar_cases=similar_case_objects,
            confidence=llm_result["confidence"]
        )
        
        # Step 6: Store this case for future reference
        case_id = str(uuid.uuid4())
        self.milvus_service.insert_compliance_case({
            "case_id": case_id,
            "transaction_id": transaction.transaction_id,
            "embedding": transaction_embedding,
            "decision": decision.verdict.value,
            "reasoning": decision.reasoning,
            "risk_score": decision.risk_score,
            "timestamp": datetime.now()
        })
        
        processing_time = (time.time() - start_time) * 1000
        
        logger.info(
            f"[{trace_id}] Decision: {decision.verdict.value} "
            f"(risk: {decision.risk_score:.2f}) in {processing_time:.0f}ms"
        )
        
        return {
            "decision": decision,
            "trace_id": trace_id,
            "processing_time_ms": processing_time
        }
    
    def answer_compliance_query(
        self, 
        query: str, 
        topic: str = None
    ) -> Dict[str, Any]:
        """Answer a compliance-related query"""
        
        # Generate query embedding
        query_embedding = self.embedding_service.generate_embedding(query)
        
        # Retrieve relevant policies
        relevant_policies = self.milvus_service.search_similar_policies(
            query_embedding=query_embedding,
            top_k=settings.top_k_results,
            topic=topic,
            active_only=True
        )
        
        # Get LLM answer
        llm_result = self.llm_service.answer_query(
            query=query,
            policy_context=relevant_policies
        )
        
        # Build citations
        policy_citations = [
            PolicyCitation(
                doc_id=policy["doc_id"],
                doc_title=policy["doc_title"],
                section=policy.get("section"),
                text=policy["text"][:500],
                relevance_score=policy["relevance_score"],
                version=policy["version"]
            )
            for policy in relevant_policies
        ]
        
        return {
            "query": query,
            "answer": llm_result["answer"],
            "citations": policy_citations,
            "confidence": llm_result["confidence"]
        }
    
    def _transaction_to_text(self, transaction: Transaction) -> str:
        """Convert transaction to text for embedding"""
        return (
            f"Transaction {transaction.transaction_id}: "
            f"{transaction.currency} {transaction.amount} "
            f"from {transaction.sender} ({transaction.sender_country or 'Unknown'}) "
            f"to {transaction.receiver} ({transaction.receiver_country or 'Unknown'}). "
            f"Description: {transaction.description or 'N/A'}"
        )
