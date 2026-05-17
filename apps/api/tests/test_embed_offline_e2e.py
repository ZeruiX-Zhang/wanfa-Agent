"""Integration test — embedder offline mode makes no outbound call (Task 6.10).

Covers R8.6 / R18.3: with ``REALITY_OS_EMBED_MODE=offline`` the embed
store never invokes the embedder (a stand-in for the outbound embedding
request) and degrades to the deterministic TF-IDF path.
"""

from __future__ import annotations

from apps.api.app.knowledge_core import KnowledgeCore
from apps.api.app.vector_store import SqliteEmbedVectorStore


def test_embed_offline_no_outbound_request(tmp_path, monkeypatch) -> None:
    """Offline mode keeps the embedder (the outbound proxy) dormant."""

    monkeypatch.setenv("REALITY_OS_EMBED_MODE", "offline")

    core = KnowledgeCore(path=tmp_path / "kc.sqlite3")
    tenant = "tnt-embed-offline-e2e"
    for idx in range(3):
        core.absorb(
            tenant_id=tenant,
            title=f"Note {idx}",
            body=f"Document {idx} discussing retrieval, indexing and ranking.",
            source_kind="direct_import",
        )

    outbound_calls: list[str] = []

    def _embedder(text: str) -> list[float]:
        # Stands in for an outbound embedding API request.
        outbound_calls.append(text)
        return [1.0, 0.0, 0.0]

    store = SqliteEmbedVectorStore(core, embedder=_embedder)

    # The cosine path is inactive in offline mode.
    assert store.embed_available() is False

    results = store.search(tenant_id=tenant, query="retrieval ranking", limit=5)

    # No outbound request was issued — the search fell back to TF-IDF.
    assert outbound_calls == []
    assert isinstance(results, list)

    # Determinism: a repeat query on the stable DB ranks identically.
    again = store.search(tenant_id=tenant, query="retrieval ranking", limit=5)
    assert [item.id for item, _ in results] == [item.id for item, _ in again]
    assert outbound_calls == []
