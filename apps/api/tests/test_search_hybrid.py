"""Unit tests for hybrid retrieval in ``KnowledgeCore.search`` (Task 4.5).

Covers Requirement 8.2: when ``REALITY_OS_HYBRID_RETRIEVAL`` is on, FTS
and TF-IDF signals are min-max normalised and combined via
``hybrid_score``; when off, the legacy fixed-weight blend is unchanged.
"""

from __future__ import annotations

from apps.api.app.knowledge_core import KnowledgeCore


def _seeded_core(tmp_path):
    core = KnowledgeCore(path=tmp_path / "kc.sqlite3")
    tenant = "tnt_hybrid"
    core.absorb(
        tenant_id=tenant,
        title="Gradient descent",
        body="Gradient descent optimises model parameters by following the loss gradient.",
        source_kind="direct_import",
    )
    core.absorb(
        tenant_id=tenant,
        title="Learning rate",
        body="The learning rate scales each gradient descent step during optimisation.",
        source_kind="direct_import",
    )
    core.absorb(
        tenant_id=tenant,
        title="Unrelated topic",
        body="Photosynthesis converts sunlight into chemical energy in plant cells.",
        source_kind="direct_import",
    )
    return core, tenant


def test_search_unchanged_when_flag_off(tmp_path, monkeypatch) -> None:
    """With the flag off, search runs the legacy blend and stays ordered."""

    monkeypatch.setenv("REALITY_OS_HYBRID_RETRIEVAL", "false")
    core, tenant = _seeded_core(tmp_path)

    results = core.search(tenant_id=tenant, query="gradient descent step", limit=5)
    assert results, "legacy search must return matches"
    scores = [score for _, score in results]
    assert scores == sorted(scores, reverse=True)


def test_search_uses_hybrid_when_flag_on(tmp_path, monkeypatch) -> None:
    """With the flag on, search returns the same items, hybrid-scored in [0,1]."""

    core, tenant = _seeded_core(tmp_path)

    monkeypatch.setenv("REALITY_OS_HYBRID_RETRIEVAL", "false")
    legacy = core.search(tenant_id=tenant, query="gradient descent step", limit=5)
    legacy_ids = {item.id for item, _ in legacy}

    monkeypatch.setenv("REALITY_OS_HYBRID_RETRIEVAL", "true")
    hybrid = core.search(tenant_id=tenant, query="gradient descent step", limit=5)
    hybrid_ids = {item.id for item, _ in hybrid}

    assert hybrid, "hybrid search must return matches"
    # Hybrid retrieval re-scores but does not change candidate membership.
    assert hybrid_ids == legacy_ids

    scores = [score for _, score in hybrid]
    assert scores == sorted(scores, reverse=True)
    # The hybrid blend is a convex combination -> bounded to [0, 1].
    assert all(0.0 <= score <= 1.0 for score in scores)
