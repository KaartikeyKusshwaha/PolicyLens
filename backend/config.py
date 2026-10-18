from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent


class Settings(BaseSettings):
    groq_api_key: SecretStr = SecretStr("")
    groq_model: str = "openai/gpt-oss-20b"
    database_path: Path = ROOT / "data" / "policylens-v2.db"
    sanctions_max_age_hours: int = Field(default=24, ge=1, le=168)
    cookie_secure: bool = False
    allowed_hosts: str = "127.0.0.1,localhost,testserver"
    session_hours: int = Field(default=12, ge=1, le=48)
    agent_daily_runs: int = Field(default=30, ge=1, le=1000)
    agent_max_context_chars: int = Field(default=18000, ge=4000, le=24000)
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
