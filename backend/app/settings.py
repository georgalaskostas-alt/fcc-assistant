from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    pi_web_api_url: str = ""
    pi_verify_tls: bool = True
    pi_timeout_seconds: float = 15.0
    tag_config_path: str = "config/fcc-tags.local.json"

    local_ai_url: str = "http://127.0.0.1:11434"
    local_ai_model: str = ""
    local_ai_timeout_seconds: float = 120.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="FCC_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
