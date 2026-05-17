"""Feature-flag test for ``REALITY_OS_HYBRID_RETRIEVAL`` (Task 4.14)."""

from __future__ import annotations

from apps.api.app import feature_flags
from apps.api.app.knowledge_core import KnowledgeCore


def test_hybrid_disabled_uses_legacy_search(tmp_path, monkeypatch) -> None:
    """Flag off -> hybrid_retrieval_enabled() is False and search still works."""

    monkeypatch.delenv("REALITY_OS_HYBRID_RETRIEVAL", raising=False)
    assert feature_flags.hybrid_retrieval_enabled() is False

    core = KnowledgeCore(path=tmp_path / "kc.sqlite3")
    tenant = "tnt_flag_hybrid"
    core.absorb(
        tenant_id=tenant,
        title="Caching",
        body="A cache stores recent results so repeated lookups stay fast.",
        source_kind="direct_import",
    )
    results = core.search(tenant_id=tenant, query="cache lookups", limit=5)
    assert results, "legacy search must work with the flag off"

    monkeypatch.setenv("REALITY_OS_HYBRID_RETRIEVAL", "true")
    assert feature_flags.hybrid_retrieval_enabled() is True
