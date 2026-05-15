from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Enterprise RAG Agent Demo"
    app_env: str = "local"
    log_level: str = "INFO"

    chunk_size: int = Field(default=800, ge=100)
    chunk_overlap: int = Field(default=120, ge=0)

    chat_api_key: str = ""
    chat_base_url: str = ""
    chat_model: str = ""

    embedding_api_key: str = ""
    embedding_base_url: str = ""
    embedding_model: str = ""
    demo_embeddings_enabled: bool = True
    local_embedding_dimensions: int = Field(default=384, ge=32, le=4096)

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_chat_model: str = "deepseek-v4-flash"

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_chat_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_timeout_seconds: int = Field(default=60, ge=1)
    llm_max_retries: int = Field(default=2, ge=0, le=5)
    http_trust_env: bool = False

    @property
    def project_root(self) -> Path:
        return PROJECT_ROOT

    @property
    def chunks_path(self) -> Path:
        return self.project_root / "data" / "processed" / "enterprise_kb" / "chunks.jsonl"

    @property
    def resolved_chat_api_key(self) -> str:
        return self.chat_api_key or self.deepseek_api_key or self.openai_api_key

    @property
    def resolved_chat_base_url(self) -> str:
        if self.chat_base_url:
            return self.chat_base_url
        if self.deepseek_api_key:
            return self.deepseek_base_url
        return self.openai_base_url

    @property
    def resolved_chat_model(self) -> str:
        if self.chat_model:
            return self.chat_model
        if self.deepseek_api_key:
            return self.deepseek_chat_model
        return self.openai_chat_model

    @property
    def resolved_embedding_api_key(self) -> str:
        return self.embedding_api_key or self.openai_api_key

    @property
    def resolved_embedding_base_url(self) -> str:
        return self.embedding_base_url or self.openai_base_url

    @property
    def resolved_embedding_model(self) -> str:
        return self.embedding_model or self.openai_embedding_model


settings = Settings()
