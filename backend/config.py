from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # OpenAI Configuration
    openai_api_key: str = ""
    
    # Milvus Configuration
    milvus_host: str = "localhost"
    milvus_port: int = 19530
    
    # Model Configuration
    embedding_model: str = "text-embedding-3-large"
    llm_model: str = "gpt-4-turbo-preview"
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
