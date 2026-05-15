from __future__ import annotations

import hashlib
import json
import math
import os
import time
from collections.abc import Generator
from pathlib import Path
from typing import Any, TypeVar
from uuid import uuid4

import httpx
from pydantic import BaseModel, ValidationError

from llm_gateway.config import ROOT_DIR, prompt_version, resolve_model
from llm_gateway.models import ChatMessage, EmbeddingResponse, LLMResponse, ModelCallTrace, RerankResult, TokenUsage


T = TypeVar("T", bound=BaseModel)


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4) if text else 0


def _normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def _mock_embedding(text: str, dimensions: int = 128) -> list[float]:
    vector = [0.0] * dimensions
    for token in text.lower().split():
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        vector[index] += 1.0 if digest[4] % 2 == 0 else -1.0
    return _normalize(vector)


def _cosine(left: list[float], right: list[float]) -> float:
    size = min(len(left), len(right))
    return sum(left[index] * right[index] for index in range(size))


class LLMGateway:
    def __init__(self, log_path: Path | None = None) -> None:
        self.log_path = log_path or ROOT_DIR / "storage" / "traces" / "llm_calls.jsonl"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def chat(
        self,
        messages: list[ChatMessage | dict[str, str]],
        *,
        model: str | None = None,
        trace_id: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        selected, model_entry, provider = resolve_model(model, "chat")
        normalized_messages = [message if isinstance(message, ChatMessage) else ChatMessage.model_validate(message) for message in messages]
        return self._call_chat(
            normalized_messages,
            selected=selected,
            model_entry=model_entry,
            provider=provider,
            trace_id=trace_id,
            operation="chat",
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def stream_chat(
        self,
        messages: list[ChatMessage | dict[str, str]],
        *,
        model: str | None = None,
        trace_id: str | None = None,
    ) -> Generator[str, None, None]:
        response = self.chat(messages, model=model, trace_id=trace_id)
        for token in response.content.split():
            yield token + " "

    def structured_output(
        self,
        messages: list[ChatMessage | dict[str, str]],
        schema: type[T],
        *,
        model: str | None = None,
        trace_id: str | None = None,
    ) -> tuple[T | None, LLMResponse]:
        response = self.chat(messages, model=model, trace_id=trace_id)
        try:
            payload = json.loads(response.content)
            return schema.model_validate(payload), response
        except (json.JSONDecodeError, ValidationError) as exc:
            response.trace.status = "parse_failed"
            response.trace.error = str(exc)
            self._record(response.trace)
            return None, response

    def tool_call(
        self,
        messages: list[ChatMessage | dict[str, str]],
        tools: list[dict[str, Any]],
        *,
        model: str | None = None,
        trace_id: str | None = None,
    ) -> LLMResponse:
        tool_names = ", ".join(str(tool.get("name") or tool.get("function", {}).get("name")) for tool in tools)
        augmented = [
            *messages,
            {"role": "system", "content": f"Available tools: {tool_names}. Return a JSON tool call only."},
        ]
        return self.chat(augmented, model=model, trace_id=trace_id)

    def embedding(
        self,
        texts: list[str],
        *,
        model: str | None = None,
        trace_id: str | None = None,
    ) -> EmbeddingResponse:
        selected, model_entry, provider = resolve_model(model, "embedding")
        start = time.perf_counter()
        try:
            if provider["name"] == "mock":
                dimensions = int(model_entry.get("dimensions") or 128)
                embeddings = [_mock_embedding(text, dimensions) for text in texts]
            else:
                embeddings = self._embedding_http(texts, selected, provider)
            trace = self._trace(
                trace_id=trace_id,
                provider=provider["name"],
                model=selected,
                operation="embedding",
                started=start,
                input_text="\n".join(texts),
                output_text="",
            )
            response = EmbeddingResponse(embeddings=embeddings, model=selected, provider=provider["name"], trace=trace)
            self._record(trace)
            return response
        except Exception as exc:
            trace = self._trace(trace_id=trace_id, provider=provider["name"], model=selected, operation="embedding", started=start, input_text="\n".join(texts), output_text="", status="failed", error=str(exc))
            self._record(trace)
            raise

    def rerank(
        self,
        query: str,
        documents: list[str],
        *,
        model: str | None = None,
        trace_id: str | None = None,
        top_n: int | None = None,
    ) -> list[RerankResult]:
        selected, _, provider = resolve_model(model, "rerank")
        start = time.perf_counter()
        query_vector = _mock_embedding(query)
        ranked = [
            RerankResult(index=index, score=_cosine(query_vector, _mock_embedding(document)), document=document)
            for index, document in enumerate(documents)
        ]
        ranked.sort(key=lambda item: item.score, reverse=True)
        if top_n:
            ranked = ranked[:top_n]
        trace = self._trace(
            trace_id=trace_id,
            provider=provider["name"],
            model=selected,
            operation="rerank",
            started=start,
            input_text=query + "\n" + "\n".join(documents),
            output_text=json.dumps([item.model_dump() for item in ranked]),
        )
        self._record(trace)
        return ranked

    def _call_chat(
        self,
        messages: list[ChatMessage],
        *,
        selected: str,
        model_entry: dict[str, Any],
        provider: dict[str, Any],
        trace_id: str | None,
        operation: str,
        temperature: float | None,
        max_tokens: int | None,
    ) -> LLMResponse:
        start = time.perf_counter()
        input_text = "\n".join(f"{message.role}: {message.content}" for message in messages)
        try:
            if provider["name"] == "mock":
                content = self._mock_chat(messages, operation=operation)
                raw: dict[str, Any] = {"mock": True}
            else:
                content, raw = self._chat_http(messages, selected, provider, temperature, max_tokens)
            trace = self._trace(trace_id=trace_id, provider=provider["name"], model=selected, operation=operation, started=start, input_text=input_text, output_text=content)
            response = LLMResponse(content=content, model=selected, provider=provider["name"], trace=trace, raw=raw)
            self._record(trace)
            return response
        except Exception as exc:
            trace = self._trace(trace_id=trace_id, provider=provider["name"], model=selected, operation=operation, started=start, input_text=input_text, output_text="", status="failed", error=str(exc))
            self._record(trace)
            fallback = self._mock_chat(messages, operation=operation)
            trace.status = "fallback"
            return LLMResponse(content=fallback, model=selected, provider="mock", trace=trace, raw={"fallback_error": str(exc)})

    def _chat_http(
        self,
        messages: list[ChatMessage],
        model: str,
        provider: dict[str, Any],
        temperature: float | None,
        max_tokens: int | None,
    ) -> tuple[str, dict[str, Any]]:
        api_key_env = str(provider.get("api_key_env") or "")
        api_key = os.getenv(api_key_env)
        if not api_key:
            raise RuntimeError(f"Missing API key env: {api_key_env}")
        payload = {
            "model": model,
            "messages": [message.model_dump() for message in messages],
            "temperature": temperature if temperature is not None else float(provider.get("temperature", 0.2)),
            "max_tokens": max_tokens if max_tokens is not None else int(provider.get("max_tokens", 1200)),
        }
        url = str(provider.get("base_url") or "").rstrip("/") + "/chat/completions"
        timeout = float(provider.get("timeout") or 30)
        max_retries = int(provider.get("max_retries") or 0)
        last_exc: Exception | None = None
        for _ in range(max_retries + 1):
            try:
                with httpx.Client(timeout=timeout, trust_env=False) as client:
                    response = client.post(url, headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, json=payload)
                response.raise_for_status()
                data = response.json()
                content = str(data.get("choices", [{}])[0].get("message", {}).get("content") or "")
                return content, data
            except Exception as exc:
                last_exc = exc
        raise RuntimeError(str(last_exc))

    def _embedding_http(self, texts: list[str], model: str, provider: dict[str, Any]) -> list[list[float]]:
        api_key_env = str(provider.get("api_key_env") or "")
        api_key = os.getenv(api_key_env)
        if not api_key:
            raise RuntimeError(f"Missing API key env: {api_key_env}")
        url = str(provider.get("base_url") or "").rstrip("/") + "/embeddings"
        with httpx.Client(timeout=float(provider.get("timeout") or 30), trust_env=False) as client:
            response = client.post(url, headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, json={"model": model, "input": texts})
        response.raise_for_status()
        data = response.json()
        return [item["embedding"] for item in data.get("data", [])]

    def _mock_chat(self, messages: list[ChatMessage], *, operation: str) -> str:
        user_text = " ".join(message.content for message in messages if message.role == "user").strip()
        if operation == "tool_call":
            return json.dumps({"name": "search_knowledge_base", "arguments": {"query": user_text}}, ensure_ascii=False)
        if "json" in user_text.lower() or "sqlplan" in user_text.lower():
            return "{}"
        return f"[mock:{operation}] {user_text[:600]}" if user_text else f"[mock:{operation}]"

    def _trace(
        self,
        *,
        trace_id: str | None,
        provider: str,
        model: str,
        operation: str,
        started: float,
        input_text: str,
        output_text: str,
        status: str = "completed",
        error: str | None = None,
    ) -> ModelCallTrace:
        input_tokens = _estimate_tokens(input_text)
        output_tokens = _estimate_tokens(output_text)
        return ModelCallTrace(
            trace_id=trace_id or f"trace_{uuid4().hex[:12]}",
            provider=provider,
            model=model,
            operation=operation,
            prompt_version=prompt_version(),
            latency_ms=round((time.perf_counter() - started) * 1000, 3),
            token_usage=TokenUsage(input_tokens=input_tokens, output_tokens=output_tokens, total_tokens=input_tokens + output_tokens, estimated_cost=0.0),
            status=status,
            error=error,
        )

    def _record(self, trace: ModelCallTrace) -> None:
        with self.log_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(trace.model_dump(mode="json"), ensure_ascii=False) + "\n")


_gateway: LLMGateway | None = None


def get_gateway() -> LLMGateway:
    global _gateway
    if _gateway is None:
        _gateway = LLMGateway()
    return _gateway
