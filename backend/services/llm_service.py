from openai import OpenAI
from typing import List, Dict, Any
import logging
import sys
import os
from config import settings

# Add utils to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.retry import retry_with_backoff

logger = logging.getLogger(__name__)


class LLMService:
    def __init__(self):
        self.model = settings.llm_model
        self.temperature = settings.llm_temperature
        self.max_tokens = settings.max_tokens
        
        if not settings.openai_api_key:
            logger.warning("API key not set. LLM calls will use fallback logic.")
            self.client = None
        else:
            # OpenRouter requires additional headers
            self.client = OpenAI(
                api_key=settings.openai_api_key,
                base_url=settings.api_base_url,
                default_headers={
                    "HTTP-Referer": "https://policylens.app",
                    "X-Title": "PolicyLens"
                }
            )
    
    def evaluate_transaction(
        self,
        transaction: Dict[str, Any],
        policy_context: List[Dict[str, Any]],
        similar_cases: List[Dict[str, Any]] = []
    ) -> Dict[str, Any]:
        """Evaluate a transaction against policies using LLM"""
        
        if not self.client:
            return self._fallback_evaluation(transaction, policy_context)
        
        # Build context from retrieved policies
        policy_text = self._format_policy_context(policy_context)
        cases_text = self._format_similar_cases(similar_cases)
        transaction_text = self._format_transaction(transaction)
        
        prompt = f"""You are a compliance analyst evaluating financial transactions against AML/KYC policies.

**Transaction Details:**
{transaction_text}

**Relevant Policies:**
{policy_text}

**Similar Historical Cases:**
{cases_text}

**Task:**
Analyze this transaction and provide:
1. Verdict: Choose from [FLAG, NEEDS_REVIEW, ACCEPTABLE]
2. Risk Level: Choose from [HIGH, MEDIUM, LOW, ACCEPTABLE]
3. Risk Score: A number between 0.0 and 1.0
4. Reasoning: Detailed explanation citing specific policies
5. Confidence: Your confidence level (0.0 to 1.0)

Respond in JSON format:
{{
  "verdict": "FLAG|NEEDS_REVIEW|ACCEPTABLE",
  "risk_level": "HIGH|MEDIUM|LOW|ACCEPTABLE",
  "risk_score": 0.0-1.0,
  "reasoning": "detailed explanation with policy citations",
  "confidence": 0.0-1.0
}}"""
        
        try:
            result = self._call_llm_with_retry(prompt)
            return result
            
        except Exception as e:
            logger.error(f"Error in LLM evaluation: {e}")
            return self._fallback_evaluation(transaction, policy_context)
    
    @retry_with_backoff(max_retries=3, initial_delay=1.0, backoff_factor=2.0)
    def _call_llm_with_retry(self, prompt: str) -> Dict[str, Any]:
        """Call LLM with retry logic"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are an expert compliance analyst specializing in AML and KYC regulations."},
                {"role": "user", "content": prompt}
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            response_format={"type": "json_object"}
        )
        
        import json
        result = json.loads(response.choices[0].message.content)
        return result
    
    def answer_query(
        self,
        query: str,
        policy_context: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Answer a compliance query using retrieved policies"""
        
        if not self.client:
            return self._fallback_answer(query, policy_context)
        
        policy_text = self._format_policy_context(policy_context)
        
        prompt = f"""You are a compliance expert answering questions about AML/KYC policies.

**Question:**
{query}

**Relevant Policies:**
{policy_text}

Provide a clear, concise answer based on the policies above. Cite specific policy sections in your response.

Respond in JSON format:
{{
  "answer": "your detailed answer with policy citations",
  "confidence": 0.0-1.0
}}"""
        
        try:
            result = self._query_llm_with_retry(prompt)
            return result
            
        except Exception as e:
            logger.error(f"Error in LLM query answering: {e}")
            # Fallback to rule-based answer
            return self._fallback_answer(query, policy_context)
    
    @retry_with_backoff(max_retries=3, initial_delay=1.0, backoff_factor=2.0)
    def _query_llm_with_retry(self, prompt: str) -> Dict[str, Any]:
        """Call LLM for query answering with retry logic"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are an expert compliance analyst."},
                {"role": "user", "content": prompt}
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            response_format={"type": "json_object"}
        )
        
        import json
        result = json.loads(response.choices[0].message.content)
        return result
    
    def _format_policy_context(self, policies: List[Dict[str, Any]]) -> str:
        """Format policy chunks for LLM context"""
        formatted = []
        for i, policy in enumerate(policies, 1):
            formatted.append(
                f"[Policy {i}] {policy['doc_title']}\n"
                f"Section: {policy.get('section', 'N/A')}\n"
                f"Source: {policy['source']} | Version: {policy['version']}\n"
                f"Content: {policy['text']}\n"
                f"Relevance: {policy['relevance_score']:.2f}\n"
            )
        return "\n---\n".join(formatted)
    
    def _format_similar_cases(self, cases: List[Dict[str, Any]]) -> str:
        """Format similar cases for LLM context"""
        if not cases:
            return "No similar historical cases found."
        
        formatted = []
        for i, case in enumerate(cases, 1):
            formatted.append(
                f"[Case {i}] Transaction: {case['transaction_id']}\n"
                f"Decision: {case['decision']} | Risk Score: {case['risk_score']:.2f}\n"
                f"Reasoning: {case['reasoning']}\n"
                f"Similarity: {case['similarity_score']:.2f}\n"
            )
        return "\n---\n".join(formatted)
    
    def _format_transaction(self, transaction: Dict[str, Any]) -> str:
        """Format transaction details for LLM"""
        return (
            f"ID: {transaction['transaction_id']}\n"
            f"Amount: {transaction['currency']} {transaction['amount']}\n"
            f"Sender: {transaction['sender']} ({transaction.get('sender_country', 'Unknown')})\n"
            f"Receiver: {transaction['receiver']} ({transaction.get('receiver_country', 'Unknown')})\n"
            f"Description: {transaction.get('description', 'N/A')}\n"
            f"Timestamp: {transaction['timestamp']}\n"
        )
    
    def _fallback_evaluation(
        self,
        transaction: Dict[str, Any],
        policy_context: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Simple rule-based fallback when LLM is unavailable"""
        
        # Simple heuristics
        amount = transaction['amount']
        high_risk_countries = ['North Korea', 'Iran', 'Syria']
        
        risk_score = 0.0
        
        # Large amounts
        if amount > 10000:
            risk_score += 0.3
        if amount > 50000:
            risk_score += 0.2
        
        # High-risk countries
        if transaction.get('sender_country') in high_risk_countries:
            risk_score += 0.4
        if transaction.get('receiver_country') in high_risk_countries:
            risk_score += 0.4
        
        # Policy context relevance
        if policy_context and policy_context[0]['relevance_score'] > 0.8:
            risk_score += 0.2
        
        risk_score = min(risk_score, 1.0)
        
        if risk_score >= settings.high_risk_threshold:
            verdict = "FLAG"
            risk_level = "HIGH"
        elif risk_score >= settings.medium_risk_threshold:
            verdict = "NEEDS_REVIEW"
            risk_level = "MEDIUM"
        else:
            verdict = "ACCEPTABLE"
            risk_level = "LOW"
        
        reasoning = f"Rule-based evaluation: Amount={amount}, Countries={transaction.get('sender_country')}->{transaction.get('receiver_country')}"
        
        return {
            "verdict": verdict,
            "risk_level": risk_level,
            "risk_score": risk_score,
            "reasoning": reasoning,
            "confidence": 0.6
        }
    
    def _fallback_answer(
        self,
        query: str,
        policy_context: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Provide a fallback answer when LLM is unavailable"""
        
        if not policy_context:
            return {
                "answer": "I don't have sufficient policy information to answer this question. Please ensure policies are uploaded to the system.",
                "confidence": 0.0
            }
        
        # Build answer from top relevant policies
        answer_parts = [f"Based on the available policies, here's what I found:\n"]
        
        for i, policy in enumerate(policy_context[:3], 1):
            answer_parts.append(
                f"\n{i}. From '{policy['doc_title']}' ({policy['source']}, v{policy['version']}):\n"
                f"   {policy['text'][:300]}..."
            )
        
        answer_parts.append(
            f"\n\nNote: This is a basic policy excerpt. For detailed compliance guidance, "
            f"please configure an AI API key for advanced analysis."
        )
        
        return {
            "answer": "".join(answer_parts),
            "confidence": 0.5
        }
