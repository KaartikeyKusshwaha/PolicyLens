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
        
        if not settings.openai_api_key or settings.openai_api_key == "OPENROUTER_API_KEY_PLACEHOLDER":
            logger.warning("API key not set. LLM calls will use fallback logic.")
            self.client = None
        else:
            # Initialize OpenRouter client (OpenAI-compatible)
            self.client = OpenAI(
                api_key=settings.openai_api_key,
                base_url=settings.api_base_url,
                default_headers={
                    "HTTP-Referer": "https://policylens.app",
                    "X-Title": "PolicyLens"
                }
            )
            logger.info(f"LLM client initialized with OpenRouter, model: {self.model}")
    
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
                {"role": "system", "content": "You are an expert compliance analyst specializing in AML and KYC regulations. Always respond in JSON format."},
                {"role": "user", "content": prompt}
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            stream=False
        )
        
        import json
        content = response.choices[0].message.content
        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            # If not valid JSON, create a structured response
            result = {
                "verdict": "NEEDS_REVIEW",
                "risk_level": "MEDIUM",
                "risk_score": 0.5,
                "reasoning": content,
                "confidence": 0.7
            }
        return result
    
    def answer_query(
        self,
        query: str,
        policy_context: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Answer a compliance query using retrieved policies"""
        
        if not self.client:
            logger.warning("No API client initialized - using fallback")
            return self._fallback_answer(query, policy_context)
        
        logger.info(f"Processing query with LLM: {query[:100]}...")
        
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
            logger.info("Calling OpenRouter API...")
            result = self._query_llm_with_retry(prompt)
            logger.info("Successfully received response from LLM")
            return result
            
        except Exception as e:
            logger.error(f"Error in LLM query answering: {type(e).__name__}: {str(e)}")
            logger.warning("Falling back to rule-based answer")
            # Fallback to rule-based answer
            return self._fallback_answer(query, policy_context)
    
    @retry_with_backoff(max_retries=3, initial_delay=1.0, backoff_factor=2.0)
    def _query_llm_with_retry(self, prompt: str) -> Dict[str, Any]:
        """Call LLM for query answering with retry logic"""
        # DeepSeek API is OpenAI-compatible
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are an expert compliance analyst. Always respond in JSON format."},
                {"role": "user", "content": prompt}
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            stream=False
        )
        
        import json
        content = response.choices[0].message.content
        # Try to parse as JSON, if it fails, wrap it
        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            result = {"answer": content, "confidence": 0.8}
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
        """Provide a query-aware fallback answer when LLM is unavailable"""
        
        if not policy_context:
            return {
                "answer": f"I don't have sufficient policy information to answer your question: '{query}'. Please ensure policies are uploaded to the system.",
                "confidence": 0.0
            }
        
        # Extract keywords from query for better context matching
        query_lower = query.lower()
        keywords = set(query_lower.split())
        
        # Build a more relevant answer based on query content
        answer_parts = [f"**Question:** {query}\n\n**Answer:**\n\n"]
        
        # Add relevant policy excerpts with better context
        for i, policy in enumerate(policy_context[:3], 1):
            relevance = policy.get('relevance_score', 0)
            answer_parts.append(
                f"{i}. According to **{policy['doc_title']}** (v{policy['version']}):\n"
            )
            
            if policy.get('section'):
                answer_parts.append(f"   *Section: {policy['section']}*\n\n")
            
            # Show the policy text
            policy_text = policy['text']
            if len(policy_text) > 400:
                policy_text = policy_text[:400] + "..."
            
            answer_parts.append(f"   {policy_text}\n\n")
            answer_parts.append(f"   *(Relevance: {relevance:.1%})*\n\n")
        
        # Add query-specific guidance based on keywords
        if any(word in query_lower for word in ['threshold', 'limit', 'amount', 'how much']):
            answer_parts.append("\n**Note:** Check the specific thresholds and limits mentioned in the policies above.\n")
        elif any(word in query_lower for word in ['country', 'countries', 'where', 'location']):
            answer_parts.append("\n**Note:** Pay attention to country-specific restrictions and requirements mentioned above.\n")
        elif any(word in query_lower for word in ['document', 'documentation', 'required', 'need']):
            answer_parts.append("\n**Note:** Review the documentation requirements specified in the relevant policies.\n")
        elif any(word in query_lower for word in ['sanction', 'prohibited', 'restricted', 'banned']):
            answer_parts.append("\n**Note:** Carefully review the sanctions and restrictions outlined in the policies.\n")
        
        answer_parts.append(
            f"\n---\n*This answer is based on policy search results. "
            f"For AI-powered analysis with deeper insights, please configure an OpenRouter API key.*"
        )
        
        return {
            "answer": "".join(answer_parts),
            "confidence": min(0.7, policy_context[0].get('relevance_score', 0.5) if policy_context else 0.3)
        }
