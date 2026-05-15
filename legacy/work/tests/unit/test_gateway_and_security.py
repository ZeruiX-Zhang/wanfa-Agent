from __future__ import annotations

from pydantic import BaseModel

from llm_gateway import ChatMessage, get_gateway
from security import mask_pii


class TinySchema(BaseModel):
    value: str


def test_llm_gateway_mock_chat_and_embedding():
    gateway = get_gateway()
    response = gateway.chat([ChatMessage(role="user", content="hello gateway")])
    assert response.provider == "mock"
    assert response.trace.latency_ms >= 0
    embedding = gateway.embedding(["hello gateway"])
    assert embedding.embeddings
    assert len(embedding.embeddings[0]) == 128


def test_structured_output_parse_failure_is_safe():
    parsed, response = get_gateway().structured_output([ChatMessage(role="user", content="not json")], TinySchema)
    assert parsed is None
    assert response.trace.status in {"parse_failed", "completed"}


def test_pii_masking():
    masked = mask_pii({"email": "alice@example.com", "phone": "+1-555-010-1234"})
    assert "alice@example.com" not in str(masked)
    assert "+1-555-010-1234" not in str(masked)
