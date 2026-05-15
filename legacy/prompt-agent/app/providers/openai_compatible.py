from __future__ import annotations

import json
import urllib.error
import urllib.request

from app.providers.base import ModelConfig


class OpenAICompatibleProvider:
    label = "OpenAI-compatible"

    def __init__(self, config: ModelConfig) -> None:
        self.config = config

    def generate(self, messages: list[dict[str, str]], options: dict[str, object] | None = None) -> str:
        options = options or {}
        base_url = self.config.base_url.rstrip("/")
        if not base_url:
            raise RuntimeError("OpenAI-compatible base_url is required.")
        if not self.config.api_key:
            raise RuntimeError("API key is required for this provider.")
        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": float(options.get("temperature", 0.2)),
            "max_tokens": int(options.get("max_tokens", 1400)),
        }
        request = urllib.request.Request(
            f"{base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=float(options.get("timeout", 45))) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"Provider HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Provider connection failed: {exc.reason}") from exc
        return str(body["choices"][0]["message"]["content"])

