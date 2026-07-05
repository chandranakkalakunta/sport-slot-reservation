from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/src/sport_slot/config.py → parents[2] == backend/
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SPORTSLOT_", env_file=str(_ENV_FILE), extra="ignore"
    )

    environment: str = "development"
    gcp_project: str = "sport-slot-dev"
    base_domain: str = "slotsense.chandraailabs.com"
    admin_host: str = "admin.slotsense.chandraailabs.com"
    log_level: str = "INFO"
    rate_limit: str = "30/minute"
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_auth: str | None = None
    resend_api_key: str | None = None
    email_from_addr: str = "no-reply@mail.chandraailabs.com"
    tasks_queue: str = "notifications"
    tasks_location: str = "asia-south1"
    worker_base_url: str | None = None
    tasks_invoker_sa: str | None = None
    reset_token_ttl_seconds: int = 3600
    reset_cooldown_seconds: int = 900
    reset_continue_url: str = "https://slotsense.chandraailabs.com/reset"
    welcome_login_url: str = "https://slotsense.chandraailabs.com/signin"
    vertex_project: str = "sport-slot-dev"
    vertex_location: str = "asia-south1"
    agent_model: str = "gemini-2.5-flash"
    agent_output_guard_enabled: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
