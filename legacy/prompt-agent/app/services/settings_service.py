from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.models.schemas import ModelSettingsRequest, ModelSettingsResponse, ProviderInfo
from app.providers.base import ModelConfig, PrivacyConfig
from app.providers.factory import active_provider_name


class SettingsService:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or settings.settings_path

    def get_model_settings(self) -> tuple[ModelConfig, PrivacyConfig]:
        raw = self._load()
        api_key_env = str(raw.get("api_key_env") or "OPENAI_API_KEY")
        api_key = str(raw.get("api_key") or os.getenv(api_key_env, ""))
        model = ModelConfig(
            vendor=str(raw.get("vendor") or "mock"),
            provider=str(raw.get("provider") or "mock"),
            base_url=str(raw.get("base_url") or ""),
            model=str(raw.get("model") or "mock-prompt-model"),
            api_key_env=api_key_env,
            api_key=api_key,
        )
        privacy = PrivacyConfig(
            local_only=bool(raw.get("local_only", True)),
            allow_cloud_model=bool(raw.get("allow_cloud_model", False)),
            redact_sensitive_info=bool(raw.get("redact_sensitive_info", True)),
            personal_wiki_enabled=bool(raw.get("personal_wiki_enabled", True)),
            allow_cloud_personal_summary=bool(raw.get("allow_cloud_personal_summary", False)),
            allow_cloud_sensitive_personal=bool(raw.get("allow_cloud_sensitive_personal", False)),
        )
        return model, privacy

    def describe(self) -> ModelSettingsResponse:
        model, privacy = self.get_model_settings()
        active = active_provider_name(model, privacy)
        label = {
            "mock": "本地模拟模型",
            "ollama": "Ollama",
            "deepseek": "DeepSeek",
            "openai_compatible": "OpenAI-compatible",
        }.get(active, "本地模拟模型")
        return ModelSettingsResponse(
            vendor=model.vendor,
            provider=model.provider,
            base_url=model.base_url,
            model=model.model,
            api_key_env=model.api_key_env,
            has_api_key=bool(model.api_key),
            local_only=privacy.local_only,
            allow_cloud_model=privacy.allow_cloud_model,
            redact_sensitive_info=privacy.redact_sensitive_info,
            personal_wiki_enabled=privacy.personal_wiki_enabled,
            allow_cloud_personal_summary=privacy.allow_cloud_personal_summary,
            allow_cloud_sensitive_personal=privacy.allow_cloud_sensitive_personal,
            active_provider=active,
            provider_label=label,
        )

    def provider_info(self) -> ProviderInfo:
        described = self.describe()
        return ProviderInfo(
            vendor=described.vendor,
            provider=described.provider,
            active_provider=described.active_provider,
            model=described.model,
            label=described.provider_label,
        )

    def update_model_settings(self, request: ModelSettingsRequest) -> ModelSettingsResponse:
        raw = self._load()
        incoming = request.model_dump(exclude_none=True)
        api_key = incoming.pop("api_key", None)
        raw.update(incoming)
        if api_key:
            raw["api_key"] = api_key
        if request.provider == "mock":
            raw["api_key"] = ""
            raw["local_only"] = True
            raw["allow_cloud_model"] = False
        self._save(raw)
        return self.describe()

    def sanitize_error(self, message: str) -> str:
        model, _ = self.get_model_settings()
        sanitized = message
        for secret in [model.api_key, os.getenv(model.api_key_env, "")]:
            if secret:
                sanitized = sanitized.replace(secret, "[redacted]")
        return sanitized

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            parsed = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _save(self, raw: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

