from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SPORTSLOT_", env_file=".env", extra="ignore")

    environment: str = "development"
    gcp_project: str = "sport-slot-dev"
    base_domain: str = "sportbook.chandraailabs.com"
    admin_host: str = "admin.sportbook.chandraailabs.com"
    dev_tenant_slug: str | None = None
    log_level: str = "INFO"
    rate_limit: str = "30/minute"


@lru_cache
def get_settings() -> Settings:
    return Settings()
