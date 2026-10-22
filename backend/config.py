from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent


class Settings(BaseSettings):
    groq_api_key: SecretStr = SecretStr("")
    groq_model: str = "openai/gpt-oss-20b"
    groq_model_revision: str = Field(
        default="provider-unreported", min_length=1, max_length=100
    )
    pseudonymize_model_calls: bool = False
    pseudonymization_scope: str = "interactive"
    database_path: Path = ROOT / "data" / "policylens-v2.db"
    security_key_path: Path | None = None
    sanctions_max_age_hours: int = Field(default=24, ge=1, le=168)
    cookie_secure: bool = False
    deployment_mode: Literal["local", "public"] = "local"
    allowed_hosts: str = "127.0.0.1,localhost,testserver"
    session_hours: int = Field(default=12, ge=1, le=48)
    agent_daily_runs: int = Field(default=30, ge=1, le=1000)
    agent_max_context_chars: int = Field(default=18000, ge=4000, le=24000)
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    @model_validator(mode="after")
    def deployment_boundaries(self):
        hosts = [host.strip() for host in self.allowed_hosts.split(",") if host.strip()]
        if not hosts or any(
            "*" in host or "://" in host or "/" in host for host in hosts
        ):
            raise ValueError(
                "ALLOWED_HOSTS must contain explicit hostnames without wildcards, schemes, or paths."
            )
        if self.deployment_mode == "public" and not self.cookie_secure:
            raise ValueError("Public deployment requires COOKIE_SECURE=true and HTTPS.")
        return self
