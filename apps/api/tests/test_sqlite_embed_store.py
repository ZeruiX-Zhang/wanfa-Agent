"""Unit tests for ``SqliteEmbedVectorStore`` (Task 4.3).

Covers Requirement 8.1 (little-endian float32 storage + cosine search),
8.4 / 8.6 (offline mode falls back to TF-IDF with no outbound call).
"""

from __future__ import annotations

import sqlite3

import pytest

from apps.api.app.knowledge_core import KnowledgeCore
from apps.api.app.vector_store import (
    SqliteEmbedVectorStore,
    decode_vector,
    encode_vector,
)


def _core(tmp_path) -> KnowledgeCore:
    return KnowledgeCore(path=tmp_path / "kc.sqlite3")


def _absorb_with_vector(core, *, tenant_id, title, body, vector):
    item = core.absorb(
        tenant_id=tenant_id,
        title=title,
        body=body,
        source_kind="direct_import",
    )
    with sqlite3.connect(core.path) as db:
        db.execute(
            "update knowledge_items set vector = ? where id = ?",
            (encode_vector(vector), item.id),
        )
        db.commit()
    return item


def test_vector_roundtrip_is_little_endian_float32() -> None:
    values = [1.0, -0.5, 0.25, 0.0]
    blob = encode_vector(values)
    assert len(blob) == 4 * len(values)  # float32 == 4 bytes
    assert decode_vector(blob) == pytest.approx(values)


def test_search_returns_cosine_ranked(tmp_path, monkeypatch) -> None:
    """Cosine search ranks items by similarity to the query embedding."""

    monkeypatch.setenv("REALITY_OS_EMBED_MODE", "online")
    core = _core(tmp_path)
    tenant = "tnt_embed"

    item_a = _absorb_with_vector(
        core, tenant_id=tenant, title="A", body="alpha body content here",
        vector=[1.0, 0.0, 0.0],
    )
    item_b = _absorb_with_vector(
        core, tenant_id=tenant, title="B", body="beta body content here",
        vector=[0.0, 1.0, 0.0],
    )
    item_c = _absorb_with_vector(
        core, tenant_id=tenant, title="C", body="gamma body content here",
        vector=[0.7, 0.7, 0.0],
    )

    store = SqliteEmbedVectorStore(core, embedder=lambda _q: [1.0, 0.0, 0.0])
    assert store.embed_available() is True

    results = store.search(tenant_id=tenant, query="anything", limit=3)
    ids = [item.id for item, _ in results]
    # Query [1,0,0]: A cos=1.0, C cos≈0.707, B cos=0.0.
    assert ids == [item_a.id, item_c.id, item_b.id]

    scores = [score for _, score in results]
    assert scores == sorted(scores, reverse=True)
    assert scores[0] == pytest.approx(1.0)


def test_offline_mode_falls_back_to_tfidf(tmp_path, monkeypatch) -> None:
    """In ``offline`` mode the embedder is never called (Property 19)."""

    monkeypatch.setenv("REALITY_OS_EMBED_MODE", "offline")
    core = _core(tmp_path)
    tenant = "tnt_embed_off"
    _absorb_with_vector(
        core, tenant_id=tenant, title="A", body="searchable alpha content",
        vector=[1.0, 0.0],
    )

    calls: list[str] = []

    def _embedder(query: str):
        calls.append(query)
        return [1.0, 0.0]

    store = SqliteEmbedVectorStore(core, embedder=_embedder)
    assert store.embed_available() is False

    results = store.search(tenant_id=tenant, query="searchable alpha", limit=5)
    # No outbound embed call happened — TF-IDF fallback only (R8.6).
    assert calls == []
    assert isinstance(results, list)
