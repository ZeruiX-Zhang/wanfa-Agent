from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx

from rag_core.rag.settings import env_int


class LLMClientError(RuntimeError):
    def __init__(self, category: str, message: str) -> None:
        super().__init__(message)
        self.category = category


@dataclass
class LLMModelConfig:
    provider: str = "mock"
    base_url: str = ""
    model: str = "mock-prompt-model"
    api_key: str = ""
    temperature: float = 0.2
    max_tokens: int = 512
    timeout: float = field(default_factory=lambda: float(os.getenv("LLM_TIMEOUT_SECONDS", "60")))
    max_retries: int = field(default_factory=lambda: env_int("LLM_MAX_RETRIES", 3))


@dataclass
class LLMResponse:
    text: str
    model: str
    request_id: str
    trace_id: str
    token_usage: dict[str, int] = field(default_factory=dict)
    cost_estimate: str = "unknown"


MODEL_PRICES_PER_1K: dict[str, tuple[float, float]] = {
    "mock-prompt-model": (0.0, 0.0),
}


class LLMClient:
    def __init__(self, config: LLMModelConfig | None = None) -> None:
        self.config = config or LLMModelConfig()

    def generate(
        self,
        prompt: str,
        system_prompt: str = "You are a helpful assistant.",
        trace_id: str | None = None,
    ) -> LLMResponse:
        request_id = str(uuid.uuid4())
        trace_id = trace_id or str(uuid.uuid4())
        if self.config.provider == "mock" or not self.config.base_url:
            return LLMResponse(
                text=f"Mock response: {prompt[:400]}",
                model=self.config.model,
                request_id=request_id,
                trace_id=trace_id,
                token_usage=self._estimate_usage(prompt),
                cost_estimate="0",
            )

        last_error: LLMClientError | None = None
        for attempt in range(self.config.max_retries + 1):
            try:
                response = self._post(
                    "/chat/completions",
                    {
                        "model": self.config.model,
                        "temperature": self.config.temperature,
                        "max_tokens": self.config.max_tokens,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt},
                        ],
                    },
                )
                data = response.json()
                text = data["choices"][0]["message"]["content"]
                usage = data.get("usage") or self._estimate_usage(prompt + text)
                return LLMResponse(
                    text=str(text),
                    model=self.config.model,
                    request_id=request_id,
                    trace_id=trace_id,
                    token_usage={key: int(value) for key, value in usage.items() if isinstance(value, int)},
                    cost_estimate=self._estimate_cost(usage),
                )
            except LLMClientError as exc:
                last_error = exc
                if exc.category in {"auth_error", "invalid_response"}:
                    break
            except httpx.TimeoutException as exc:
                last_error = LLMClientError("timeout", str(exc))
            except httpx.HTTPStatusError as exc:
                last_error = self._classify_status(exc)
                if last_error.category == "auth_error":
                    break
            except (httpx.RequestError, KeyError, IndexError, TypeError, ValueError) as exc:
                category = "invalid_response" if isinstance(exc, (KeyError, IndexError, TypeError, ValueError)) else "provider_error"
                last_error = LLMClientError(category, str(exc))
            if attempt < self.config.max_retries:
                time.sleep(min(2**attempt * 0.25, 2.0))
        assert last_error is not None
        raise last_error

    def embed(self, texts: list[str], trace_id: str | None = None) -> dict[str, Any]:
        del trace_id
        batch_size = env_int("EMBEDDING_BATCH_SIZE", 64)
        timeout = float(os.getenv("EMBEDDING_TIMEOUT_SECONDS", "60"))
        return {
            "provider": self.config.provider,
            "model": self.config.model,
            "batch_size": batch_size,
            "timeout": timeout,
            "embeddings": [],
            "skipped_reason": "external embedding provider is not configured",
            "input_count": len(texts),
        }

    def _post(self, path: str, payload: dict[str, Any]) -> httpx.Response:
        headers = {"Authorization": f"Bearer {self.config.api_key}"} if self.config.api_key else {}
        with httpx.Client(timeout=self.config.timeout) as client:
            response = client.post(f"{self.config.base_url.rstrip('/')}{path}", headers=headers, json=payload)
            response.raise_for_status()
            return response

    def _classify_status(self, exc: httpx.HTTPStatusError) -> LLMClientError:
        status = exc.response.status_code
        if status in {401, 403}:
            return LLMClientError("auth_error", str(exc))
        if status == 429:
            return LLMClientError("rate_limit", str(exc))
        return LLMClientError("provider_error", str(exc))

    def _estimate_usage(self, text: str) -> dict[str, int]:
        tokens = max(len(text.split()), 1)
        return {"prompt_tokens": tokens, "completion_tokens": 0, "total_tokens": tokens}

    def _estimate_cost(self, usage: dict[str, Any]) -> str:
        prices = MODEL_PRICES_PER_1K.get(self.config.model)
        if not prices:
            return "unknown"
        prompt_price, completion_price = prices
        prompt_cost = float(usage.get("prompt_tokens", 0)) / 1000 * prompt_price
        completion_cost = float(usage.get("completion_tokens", 0)) / 1000 * completion_price
        return f"{prompt_cost + completion_cost:.6f}"


