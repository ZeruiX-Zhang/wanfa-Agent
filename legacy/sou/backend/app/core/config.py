from __future__ import annotations

from functools import lru_cache

from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    log_level: str = "INFO"
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    database_url: str = "sqlite:///./intel_agent.db"
    redis_url: str = "redis://localhost:6379/0"
    qdrant_url: str | None = None
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    llm_provider: str = "openai"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"

    brave_search_api_key: str | None = None
    tavily_api_key: str | None = None
    github_token: str | None = None
    product_hunt_token: str | None = None
    coingecko_api_key: str | None = None

    amazon_sp_api_client_id: str | None = None
    amazon_sp_api_client_secret: str | None = None
    amazon_sp_api_refresh_token: str | None = None
    amazon_sp_api_region: str = "NA"

    http_timeout_seconds: float = 15.0
    external_max_bytes: int = 2_000_000

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_cors(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def public_api_base_url(self) -> AnyHttpUrl | None:
        return None


@lru_cache
def get_settings() -> Settings:
    return Settings()
