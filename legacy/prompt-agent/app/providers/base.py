from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class ModelConfig:
    vendor: str = "mock"
    provider: str = "mock"
    base_url: str = ""
    model: str = "mock-prompt-model"
    api_key_env: str = "OPENAI_API_KEY"
    api_key: str = ""


@dataclass
class PrivacyConfig:
    local_only: bool = True
    allow_cloud_model: bool = False
    redact_sensitive_info: bool = True
    personal_wiki_enabled: bool = True
    allow_cloud_personal_summary: bool = False
    allow_cloud_sensitive_personal: bool = False


class ModelProvider(Protocol):
    label: str

    def generate(self, messages: list[dict[str, str]], options: dict[str, object] | None = None) -> str:
        ...

