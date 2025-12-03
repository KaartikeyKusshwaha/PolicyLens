from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # API Configuration - Groq (Free Llama Access)
    openai_api_key: str = "GROQ_API_KEY_PLACEHOLDER"
    api_base_url: str = "https://api.groq.com/openai/v1"
    
    # Milvus Configuration
    milvus_host: str = "localhost"
    milvus_port: int = 19530
    
    # Model Configuration
    embedding_model: str = "all-MiniLM-L6-v2"  # Local embeddings
    llm_model: str = "llama-3.1-8b-instant"
    llm_temperature: float = 0.1
    max_tokens: int = 2000
    
    # Application Configuration
    api_port: int = 8000
    chunk_size: int = 600
    chunk_overlap: int = 100
    top_k_results: int = 5
    
    # Risk Scoring Thresholds
    high_risk_threshold: float = 0.75
    medium_risk_threshold: float = 0.45
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
