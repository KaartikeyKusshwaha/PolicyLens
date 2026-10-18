from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent


class Settings(BaseSettings):
    groq_api_key: SecretStr = SecretStr("")
    groq_model: str = "openai/gpt-oss-20b"
    database_path: Path = ROOT / "data" / "policylens-v2.db"
    sanctions_max_age_hours: int = Field(default=24, ge=1, le=168)
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
