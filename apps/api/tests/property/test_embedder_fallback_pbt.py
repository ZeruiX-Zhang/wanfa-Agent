"""Property-based test for embedder fallback determinism.

Feature: expert-coaching-loop, Property 19: when the embedder is
unconfigured or ``EMBED_MODE`` is ``offline`` / ``disabled``, the embed
store falls back to TF-IDF, makes no outbound call, and ranks
deterministically on a stable DB (R8.4, R8.6, R18.2-3).
"""

from __future__ import annotations

import os

from hypothesis import given, settings, strategies as st

from apps.api.app.knowledge_core import KnowledgeCore
from apps.api.app.vector_store import SqliteEmbedVectorStore


def test_property_19_embedder_fallback_no_outbound_call_and_deterministic_ranking(
    tmp_path,
) -> None:
    """Offline / disabled modes never call the embedder and rank stably."""

    core = KnowledgeCore(path=tmp_path / "kc.sqlite3")
    tenant = "tnt_fallback"
    for idx in range(4):
        core.absorb(
            tenant_id=tenant,
            title=f"Topic {idx}",
            body=f"Document number {idx} about retrieval indexing and search quality.",
            source_kind="direct_import",
        )

    previous = os.environ.get("REALITY_OS_EMBED_MODE")

    @settings(max_examples=60, deadline=None)
    @given(
        mode=st.sampled_from(["offline", "disabled"]),
        query=st.text(
            alphabet=st.characters(min_codepoint=97, max_codepoint=122),
            min_size=1,
            max_size=24,
        ),
    )
    def _check(mode: str, query: str) -> None:
        os.environ["REALITY_OS_EMBED_MODE"] = mode
        calls: list[str] = []

        def _embedder(text: str):
            calls.append(text)
            return [1.0, 0.0]

        store = SqliteEmbedVectorStore(core, embedder=_embedder)
        assert store.embed_available() is False

        first = store.search(tenant_id=tenant, query=query, limit=5)
        second = store.search(tenant_id=tenant, query=query, limit=5)

        # No outbound embedding call was made.
        assert calls == []
        # Ranking is deterministic on a stable DB.
        assert [item.id for item, _ in first] == [item.id for item, _ in second]

    try:
        _check()
    finally:
        if previous is None:
            os.environ.pop("REALITY_OS_EMBED_MODE", None)
        else:
            os.environ["REALITY_OS_EMBED_MODE"] = previous
