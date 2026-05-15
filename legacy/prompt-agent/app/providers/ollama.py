from __future__ import annotations

import json
import urllib.error
import urllib.request

from app.providers.base import ModelConfig


class OllamaProvider:
    label = "Ollama"

    def __init__(self, config: ModelConfig) -> None:
        self.config = config

    def generate(self, messages: list[dict[str, str]], options: dict[str, object] | None = None) -> str:
        options = options or {}
        base_url = (self.config.base_url or "http://localhost:11434").rstrip("/")
        payload = {
            "model": self.config.model or "llama3.1",
            "messages": messages,
            "stream": False,
            "options": {"temperature": float(options.get("temperature", 0.2))},
        }
        request = urllib.request.Request(
            f"{base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=float(options.get("timeout", 45))) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Ollama connection failed: {exc.reason}") from exc
        return str(body.get("message", {}).get("content", ""))

