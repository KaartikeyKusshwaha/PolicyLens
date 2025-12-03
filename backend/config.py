from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # API Configuration
    openai_api_key: str = "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"
    api_base_url: str = "https://openrouter.ai/api/v1"
    
    # Milvus Configuration
    milvus_host: str = "localhost"
    milvus_port: int = 19530
    
    # Model Configuration
    embedding_model: str = "all-MiniLM-L6-v2"  # Local embeddings
    llm_model: str = "google/gemma-3n-e4b-it:free"
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
