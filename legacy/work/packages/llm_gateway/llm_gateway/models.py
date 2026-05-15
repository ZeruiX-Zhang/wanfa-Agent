from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str


class TokenUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost: float = 0.0


class ModelCallTrace(BaseModel):
    trace_id: str
    provider: str
    model: str
    operation: str
    prompt_version: str = "v1"
    latency_ms: float = 0.0
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    status: str = "completed"
    error: str | None = None
    created_at: str = Field(default_factory=utc_now)


class LLMResponse(BaseModel):
    content: str
    model: str
    provider: str
    trace: ModelCallTrace
    raw: dict[str, Any] = Field(default_factory=dict)


class EmbeddingResponse(BaseModel):
    embeddings: list[list[float]]
    model: str
    provider: str
    trace: ModelCallTrace


class RerankResult(BaseModel):
    index: int
    score: float
    document: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolCallRequest(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
