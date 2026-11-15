from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App settings, read from environment variables or a .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str | None = None
    claude_model: str = "claude-opus-5-5"
    claude_effort: str = "medium"
    max_output_tokens: int = 16000

    # Used only to estimate cost per run (USD per million tokens).
    price_input_per_mtok: float = 4.0
    price_output_per_mtok: float = 20.0

    # Research limits
    max_pages: int = 4
    max_chars_per_page: int = 6000
    fetch_timeout_seconds: float = 15.0

    # Reviewer loop
    max_revisions: int = 2
    approve_score: int = 8

    cors_origins: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
