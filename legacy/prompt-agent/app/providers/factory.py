from __future__ import annotations

from app.providers.base import ModelConfig, PrivacyConfig
from app.providers.mock import MockProvider
from app.providers.ollama import OllamaProvider
from app.providers.openai_compatible import OpenAICompatibleProvider


def active_provider_name(model: ModelConfig, privacy: PrivacyConfig) -> str:
    if model.provider == "mock":
        return "mock"
    if model.provider == "ollama":
        return "ollama"
    if model.provider == "anthropic":
        if privacy.local_only or not privacy.allow_cloud_model or not model.api_key:
            return "mock"
        return "anthropic"
    if model.provider in {"openai_compatible", "deepseek"}:
        if privacy.local_only or not privacy.allow_cloud_model or not model.api_key:
            return "mock"
        return model.provider
    return "mock"


def build_provider(model: ModelConfig, privacy: PrivacyConfig):
    active = active_provider_name(model, privacy)
    if active == "ollama":
        return OllamaProvider(model)
    if active == "anthropic":
        from app.providers.anthropic_provider import AnthropicProvider
        return AnthropicProvider(model)
    if active in {"openai_compatible", "deepseek"}:
        return OpenAICompatibleProvider(model)
    return MockProvider()

