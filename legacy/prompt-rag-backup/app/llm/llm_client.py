from __future__ import annotations

import hashlib
import math
import re
import time
from typing import Any

import httpx

from app.core.config import settings
from app.core.errors import AppError


class LLMClient:
    """Small OpenAI-compatible client used by all LLM and embedding calls."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        chat_api_key: str | None = None,
        chat_base_url: str | None = None,
        chat_model: str | None = None,
        embedding_api_key: str | None = None,
        embedding_base_url: str | None = None,
        embedding_model: str | None = None,
        demo_embeddings_enabled: bool | None = None,
        local_embedding_dimensions: int | None = None,
        timeout_seconds: int | None = None,
        max_retries: int | None = None,
        trust_env: bool | None = None,
    ) -> None:
        legacy_api_key = api_key if api_key is not None else None
        legacy_base_url = base_url.rstrip("/") if base_url is not None else None
        self.chat_api_key = chat_api_key if chat_api_key is not None else legacy_api_key or settings.resolved_chat_api_key
        self.chat_base_url = (chat_base_url or legacy_base_url or settings.resolved_chat_base_url).rstrip("/")
        self.chat_model = chat_model or settings.resolved_chat_model
        self.embedding_api_key = (
            embedding_api_key if embedding_api_key is not None else legacy_api_key or settings.resolved_embedding_api_key
        )
        self.embedding_base_url = (embedding_base_url or legacy_base_url or settings.resolved_embedding_base_url).rstrip("/")
        self.embedding_model = embedding_model or settings.resolved_embedding_model
        self.demo_embeddings_enabled = (
            demo_embeddings_enabled if demo_embeddings_enabled is not None else settings.demo_embeddings_enabled
        )
        self.local_embedding_dimensions = local_embedding_dimensions or settings.local_embedding_dimensions
        self.timeout_seconds = timeout_seconds or settings.openai_timeout_seconds
        self.max_retries = max_retries if max_retries is not None else settings.llm_max_retries
        self.trust_env = trust_env if trust_env is not None else settings.http_trust_env

    def _headers(self, api_key: str, env_hint: str, code: str) -> dict[str, str]:
        if not api_key:
            raise AppError(f"{env_hint} is not configured in .env", status_code=503, code=code)
        return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    def chat(self, messages: list[dict[str, str]], temperature: float = 0.2) -> str:
        payload: dict[str, Any] = {
            "model": self.chat_model,
            "messages": messages,
            "temperature": temperature,
        }
        response = self._post_with_retries(
            url=f"{self.chat_base_url}/chat/completions",
            headers=self._headers(self.chat_api_key, "CHAT_API_KEY or DEEPSEEK_API_KEY", "chat_not_configured"),
            payload=payload,
            error_prefix="LLM chat request failed",
            error_code="llm_request_failed",
        )
        data = response.json()
        return data["choices"][0]["message"]["content"]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if self._use_local_demo_embeddings():
            return [self._local_demo_embedding(text) for text in texts]

        payload: dict[str, Any] = {"model": self.embedding_model, "input": texts}
        response = self._post_with_retries(
            url=f"{self.embedding_base_url}/embeddings",
            headers=self._headers(
                self.embedding_api_key,
                "EMBEDDING_API_KEY or OPENAI_API_KEY",
                "embedding_not_configured",
            ),
            payload=payload,
            error_prefix="Embedding request failed",
            error_code="embedding_request_failed",
        )
        data = response.json()
        return [item["embedding"] for item in data["data"]]

    def _post_with_retries(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        error_prefix: str,
        error_code: str,
    ) -> httpx.Response:
        last_error: httpx.HTTPError | None = None
        attempts = max(1, self.max_retries + 1)
        with httpx.Client(timeout=self.timeout_seconds, trust_env=self.trust_env) as client:
            for attempt in range(attempts):
                try:
                    response = client.post(url, headers=headers, json=payload)
                    response.raise_for_status()
                    return response
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code < 500:
                        raise AppError(f"{error_prefix}: {exc}", status_code=502, code=error_code) from exc
                    last_error = exc
                except httpx.TransportError as exc:
                    last_error = exc

                if attempt < attempts - 1:
                    time.sleep(0.3 * (attempt + 1))

        raise AppError(
            f"{error_prefix} after {attempts} attempt(s): {last_error}",
            status_code=502,
            code=error_code,
        ) from last_error

    def _use_local_demo_embeddings(self) -> bool:
        return self.embedding_model == "local-demo-embedding" or (
            self.demo_embeddings_enabled and not self.embedding_api_key
        )

    def _local_demo_embedding(self, text: str) -> list[float]:
        dimensions = self.local_embedding_dimensions
        vector = [0.0] * dimensions
        for token in self._tokenize_for_demo_embedding(text):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % dimensions
            weight = 1.0 + min(len(token), 8) * 0.05
            vector[index] += weight

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0.0:
            return vector
        return [value / norm for value in vector]

    def _tokenize_for_demo_embedding(self, text: str) -> list[str]:
        lowered = text.lower()
        tokens = re.findall(r"[a-z0-9]+", lowered)
        for segment in re.findall(r"[\u4e00-\u9fff]+", lowered):
            for size in range(1, 5):
                tokens.extend(segment[index : index + size] for index in range(0, len(segment) - size + 1))
        if not tokens and text.strip():
            tokens.append(text.strip()[:64])
        return tokens
