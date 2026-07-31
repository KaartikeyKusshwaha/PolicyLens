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
        
        key = settings.openai_api_key or ""
        is_placeholder = not key or "placeholder" in key.lower() or key.startswith("sk-your")
        if is_placeholder:
            raise RuntimeError(
                "LLM API key not configured. Add your Groq key to .env: "
                "OPENAI_API_KEY=gsk_... (free at console.groq.com)"
            )
        # Initialize Groq-compatible client (OpenAI SDK)
        self.client = OpenAI(
            api_key=key,
            base_url=settings.api_base_url,
            default_headers={
                "HTTP-Referer": "https://policylens.app",
                "X-Title": "PolicyLens"
            }
        )
        logger.info(f"LLM client initialized with model: {self.model}")
    
    def evaluate_transaction(
        self,
        transaction: Dict[str, Any],
        policy_context: List[Dict[str, Any]],
        similar_cases: List[Dict[str, Any]] = []
    ) -> Dict[str, Any]:
        """Evaluate a transaction against policies using LLM"""
        
        
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
            raise
    
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
            raise
    
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
    
    # _fallback_evaluation and _fallback_answer removed — real Groq API is required.
