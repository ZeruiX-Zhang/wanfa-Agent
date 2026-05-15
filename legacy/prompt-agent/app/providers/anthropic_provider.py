from __future__ import annotations

import json

import httpx

from app.providers.base import ModelConfig

DEFAULT_MODEL = "claude-sonnet-4-6"
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


class AnthropicProvider:
    label = "Anthropic Claude"

    def __init__(self, config: ModelConfig) -> None:
        self.config = config

    def generate(self, messages: list[dict[str, str]], options: dict[str, object] | None = None) -> str:
        options = options or {}
        api_key = self.config.api_key
        if not api_key:
            raise RuntimeError("Anthropic API key is required.")

        model = self.config.model or DEFAULT_MODEL
        max_tokens = int(options.get("max_tokens", 1600))
        timeout = float(options.get("timeout", 45))

        # Extract system message and convert remaining messages
        system_content = ""
        anthropic_messages: list[dict[str, str]] = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                system_content = content
            else:
                anthropic_messages.append({"role": role, "content": content})

        payload: dict[str, object] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": anthropic_messages,
        }
        if system_content:
            payload["system"] = system_content

        headers = {
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }

        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.post(ANTHROPIC_API_URL, headers=headers, content=json.dumps(payload))
        except httpx.TimeoutException as exc:
            raise RuntimeError("Anthropic API request timed out.") from exc
        except httpx.RequestError as exc:
            raise RuntimeError(f"Anthropic API connection failed: {exc}") from exc

        if resp.status_code != 200:
            detail = resp.text[:400]
            raise RuntimeError(f"Anthropic API error {resp.status_code}: {detail}")

        body = resp.json()
        try:
            return str(body["content"][0]["text"])
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Unexpected Anthropic response shape: {body}") from exc
