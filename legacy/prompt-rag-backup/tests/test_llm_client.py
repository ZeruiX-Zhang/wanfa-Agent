from __future__ import annotations

from app.llm.llm_client import LLMClient


def test_llm_client_supports_separate_chat_and_embedding_config():
    client = LLMClient(
        chat_api_key="deepseek-key",
        chat_base_url="https://api.deepseek.com",
        chat_model="deepseek-v4-pro",
        embedding_api_key="embedding-key",
        embedding_base_url="https://embedding.example.com/v1",
        embedding_model="embedding-model",
    )

    assert client.chat_api_key == "deepseek-key"
    assert client.chat_base_url == "https://api.deepseek.com"
    assert client.chat_model == "deepseek-v4-pro"
    assert client.trust_env is False
    assert client.embedding_api_key == "embedding-key"
    assert client.embedding_base_url == "https://embedding.example.com/v1"
    assert client.embedding_model == "embedding-model"


def test_llm_client_local_demo_embeddings_are_deterministic():
    client = LLMClient(
        embedding_api_key="",
        embedding_model="local-demo-embedding",
        local_embedding_dimensions=64,
    )

    first = client.embed_texts(["\u4f01\u4e1a\u5ba2\u6237 P1 SLA \u662f\u4ec0\u4e48\uff1f"])[0]
    second = client.embed_texts(["\u4f01\u4e1a\u5ba2\u6237 P1 SLA \u662f\u4ec0\u4e48\uff1f"])[0]

    assert first == second
    assert len(first) == 64
    assert any(value != 0.0 for value in first)
