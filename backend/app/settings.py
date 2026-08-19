from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    pi_web_api_url: str = ""
    pi_verify_tls: bool = True
    pi_timeout_seconds: float = 15.0
    tag_config_path: str = "config/fcc-tags.local.json"

    # Optional TRAVIS bridge. Standalone FCC Assistant does not depend on it.
    # When enabled, the bridge must remain loopback-only and TRAVIS must enforce
    # the FCC data policy (no external transmission of process evidence).
    travis_ai_url: str = "http://127.0.0.1:8765"
    travis_ai_timeout_seconds: float = 120.0
    prefer_travis_ai: bool = False

    # Default standalone intelligence path: bundled llama.cpp + GGUF model.
    local_ai_runtime: str = "llama_cpp"
    local_ai_url: str = "http://127.0.0.1:8081"
    local_ai_model_name: str = "embedded-local-model"
    local_ai_timeout_seconds: float = 180.0
    local_ai_binary_path: str = "runtime/bin/llama-server"
    local_ai_model_path: str = "models/default.gguf"
    local_ai_context_size: int = 4096
    local_ai_threads: int = 0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="FCC_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
