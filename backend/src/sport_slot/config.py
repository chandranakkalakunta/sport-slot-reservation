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
    base_domain: str = "sportbook.chandraailabs.com"
    admin_host: str = "admin.sportbook.chandraailabs.com"
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


@lru_cache
def get_settings() -> Settings:
    return Settings()
