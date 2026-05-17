"""Feature-flag test for ``REALITY_OS_EMBED_MODE`` (Task 4.15).

``disabled`` and ``offline`` both bypass the embedder; only ``online``
activates the cosine path (R8.5, R8.6, R18.3).
"""

from __future__ import annotations

from apps.api.app import feature_flags
from apps.api.app.knowledge_core import KnowledgeCore
from apps.api.app.vector_store import SqliteEmbedVectorStore


def _store(tmp_path) -> SqliteEmbedVectorStore:
    core = KnowledgeCore(path=tmp_path / "kc.sqlite3")
    return SqliteEmbedVectorStore(core, embedder=lambda _q: [1.0, 0.0])


def test_offline_uses_tfidf(tmp_path, monkeypatch) -> None:
    """``offline`` mode keeps the embedder dormant."""

    monkeypatch.setenv("REALITY_OS_EMBED_MODE", "offline")
    assert feature_flags.embed_mode() == "offline"
    assert _store(tmp_path).embed_available() is False


def test_disabled_disables_embed_path(tmp_path, monkeypatch) -> None:
    """``disabled`` mode keeps the embedder dormant."""

    monkeypatch.setenv("REALITY_OS_EMBED_MODE", "disabled")
    assert feature_flags.embed_mode() == "disabled"
    assert _store(tmp_path).embed_available() is False


def test_online_enables_embed_path(tmp_path, monkeypatch) -> None:
    """``online`` mode with an embedder activates the cosine path."""

    monkeypatch.setenv("REALITY_OS_EMBED_MODE", "online")
    assert feature_flags.embed_mode() == "online"
    assert _store(tmp_path).embed_available() is True
