from __future__ import annotations

from typing import Any, TypeVar

import httpx
from pydantic import BaseModel

from workflow_core.core.config import settings
from workflow_core.security.policies import redact_secrets

T = TypeVar("T", bound=BaseModel)


class StructuredLLMClient:
    """OpenAI-compatible structured output client.

    The demo workflows use deterministic rule-based fallback by default so the
    project can run without a real model key. This adapter is intentionally
    small and can replace the fallback classifiers later.
    """

    def enabled(self) -> bool:
        return bool(settings.llm_base_url and settings.llm_api_key and settings.llm_model)

    def chat_json_schema(self, messages: list[dict[str, str]], schema: type[T]) -> T | None:
        if not self.enabled():
            return None
        url = settings.llm_base_url.rstrip("/") + "/chat/completions"
        payload: dict[str, Any] = {
            "model": settings.llm_model,
            "messages": messages,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema.__name__,
                    "schema": schema.model_json_schema(),
                    "strict": True,
                },
            },
        }
        with httpx.Client(timeout=settings.request_timeout_seconds, trust_env=False) as client:
            response = client.post(
                url,
                headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                json=payload,
            )
        response.raise_for_status()
        data = redact_secrets(response.json())
        content = data["choices"][0]["message"]["content"]
        return schema.model_validate_json(content)


llm_client = StructuredLLMClient()


