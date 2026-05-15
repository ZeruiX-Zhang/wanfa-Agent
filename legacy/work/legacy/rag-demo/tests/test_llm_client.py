from __future__ import annotations

import httpx
import pytest

from app.llm.llm_client import LLMClient, LLMClientError, LLMModelConfig


def test_mock_llm_returns_usage_and_trace_id() -> None:
    response = LLMClient().generate("hello world", trace_id="trace-1")

    assert response.text.startswith("Mock response")
    assert response.trace_id == "trace-1"
    assert response.request_id
    assert response.token_usage["total_tokens"] >= 1
    assert response.cost_estimate == "0"


def test_llm_timeout_is_classified(monkeypatch: pytest.MonkeyPatch) -> None:
    client = LLMClient(
        LLMModelConfig(provider="openai_compatible", base_url="https://example.test", api_key="key", max_retries=0)
    )

    def raise_timeout(path: str, payload: dict[str, object]) -> httpx.Response:
        del path, payload
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(client, "_post", raise_timeout)

    with pytest.raises(LLMClientError) as exc:
        client.generate("hello")

    assert exc.value.category == "timeout"


def test_llm_provider_error_is_classified(monkeypatch: pytest.MonkeyPatch) -> None:
    client = LLMClient(
        LLMModelConfig(provider="openai_compatible", base_url="https://example.test", api_key="key", max_retries=0)
    )

    def raise_provider_error(path: str, payload: dict[str, object]) -> httpx.Response:
        del path, payload
        raise httpx.RequestError("provider unavailable")

    monkeypatch.setattr(client, "_post", raise_provider_error)

    with pytest.raises(LLMClientError) as exc:
        client.generate("hello")

    assert exc.value.category == "provider_error"

