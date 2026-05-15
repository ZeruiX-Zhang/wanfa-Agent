from __future__ import annotations

from app.models.schemas import ProviderPreset


def list_provider_presets() -> list[ProviderPreset]:
    return [
        ProviderPreset(
            id="mock",
            label="本地模拟模型",
            vendor="mock",
            provider="mock",
            base_url="",
            model="mock-prompt-model",
            api_key_env="OPENAI_API_KEY",
            local_only=True,
            allow_cloud_model=False,
        ),
        ProviderPreset(
            id="deepseek",
            label="DeepSeek",
            vendor="deepseek",
            provider="deepseek",
            base_url="https://api.deepseek.com/v1",
            model="deepseek-chat",
            api_key_env="DEEPSEEK_API_KEY",
            local_only=False,
            allow_cloud_model=True,
        ),
        ProviderPreset(
            id="openai-compatible",
            label="OpenAI-compatible",
            vendor="custom",
            provider="openai_compatible",
            base_url="",
            model="",
            api_key_env="OPENAI_API_KEY",
            local_only=False,
            allow_cloud_model=True,
        ),
        ProviderPreset(
            id="ollama",
            label="Ollama",
            vendor="ollama",
            provider="ollama",
            base_url="http://localhost:11434",
            model="llama3.1",
            api_key_env="",
            local_only=True,
            allow_cloud_model=False,
        ),
        ProviderPreset(
            id="claude-sonnet",
            label="Claude Sonnet 4.6",
            vendor="anthropic",
            provider="anthropic",
            base_url="",
            model="claude-sonnet-4-6",
            api_key_env="ANTHROPIC_API_KEY",
            local_only=False,
            allow_cloud_model=True,
        ),
        ProviderPreset(
            id="claude-haiku",
            label="Claude Haiku 4.5",
            vendor="anthropic",
            provider="anthropic",
            base_url="",
            model="claude-haiku-4-5-20251001",
            api_key_env="ANTHROPIC_API_KEY",
            local_only=False,
            allow_cloud_model=True,
        ),
    ]

