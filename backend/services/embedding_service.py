from openai import OpenAI
from typing import List, Optional
import logging
from config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(self):
        self.client = None
        self.model = settings.embedding_model
        self.use_openai = self.model.startswith("text-embedding")
        
        if self.use_openai:
            if not settings.openai_api_key:
                logger.warning("OpenAI API key not set. Embeddings will fail.")
            else:
                self.client = OpenAI(api_key=settings.openai_api_key)
        else:
            # Local embeddings with sentence-transformers
            from sentence_transformers import SentenceTransformer
            self.local_model = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("Using local sentence-transformers model")
    
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text"""
        if self.use_openai:
            return self._generate_openai_embedding(text)
        else:
            return self._generate_local_embedding(text)
    
    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts"""
        if self.use_openai:
            return [self._generate_openai_embedding(text) for text in texts]
        else:
            return self._generate_local_embeddings(texts)
    
    def _generate_openai_embedding(self, text: str) -> List[float]:
        """Generate embedding using OpenAI API"""
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Error generating OpenAI embedding: {e}")
            # Return a dummy embedding for MVP fallback
            return [0.0] * 1536
    
    def _generate_local_embedding(self, text: str) -> List[float]:
        """Generate embedding using local model"""
        try:
            embedding = self.local_model.encode(text, convert_to_tensor=False)
            # Pad to 1536 dimensions for consistency
            padded = list(embedding) + [0.0] * (1536 - len(embedding))
            return padded[:1536]
        except Exception as e:
            logger.error(f"Error generating local embedding: {e}")
            return [0.0] * 1536
    
    def _generate_local_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts using local model"""
        try:
            embeddings = self.local_model.encode(texts, convert_to_tensor=False)
            # Pad to 1536 dimensions
            padded_embeddings = []
            for embedding in embeddings:
                padded = list(embedding) + [0.0] * (1536 - len(embedding))
                padded_embeddings.append(padded[:1536])
            return padded_embeddings
        except Exception as e:
            logger.error(f"Error generating local embeddings: {e}")
            return [[0.0] * 1536 for _ in texts]
