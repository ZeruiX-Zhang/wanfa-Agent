"""Vector store abstraction.

The product currently ships with a deterministic TF-IDF + SQLite FTS5 retriever
inside :mod:`knowledge_core`. That is fast and zero-dep, and sufficient for
libraries in the low thousands of items.

This module exists so that the production upgrade path to pgvector / Qdrant /
LanceDB is a *configuration* change, not a refactor. The rules:

* ``get_vector_store()`` is the only function callers should use.
* The default returns a ``SqliteTfidfVectorStore`` that delegates to the
  existing knowledge_core search path. No behaviour change.
* Setting ``REALITY_OS_VECTOR_STORE`` to a supported provider swaps the
  implementation. Unsupported values fall back to the default with a warning.

When we actually add a real vector backend, the implementation will live in a
sibling module (``vector_store_pgvector.py`` etc.) that implements the same
``VectorStore`` Protocol. No call site changes.
"""

from __future__ import annotations

import logging
import os
from typing import Protocol, runtime_checkable

from .knowledge_core import KnowledgeCore, KnowledgeItem, get_core


logger = logging.getLogger(__name__)


@runtime_checkable
class VectorStore(Protocol):
    """Minimal contract every backing store must satisfy.

    Implementations must be side-effect free for ``search`` (no writes) and
    must be deterministic for the same (tenant_id, query, limit) tuple.
    """

    def search(
        self,
        *,
        tenant_id: str,
        query: str,
        limit: int = 8,
    ) -> list[tuple[KnowledgeItem, float]]: ...


class SqliteTfidfVectorStore:
    """Default backend: delegates to :class:`KnowledgeCore` hybrid search.

    This is intentionally thin — it re-uses the existing BM25 + TF-IDF path so
    the production upgrade replaces one class, not a pipeline.
    """

    def __init__(self, core: KnowledgeCore | None = None) -> None:
        self._core = core or get_core()

    def search(
        self,
        *,
        tenant_id: str,
        query: str,
        limit: int = 8,
    ) -> list[tuple[KnowledgeItem, float]]:
        return self._core.search(tenant_id=tenant_id, query=query, limit=limit)


_REGISTRY: dict[str, "type[VectorStore]"] = {
    "sqlite_tfidf": SqliteTfidfVectorStore,  # type: ignore[dict-item]
}

_DEFAULT = "sqlite_tfidf"


def get_vector_store() -> VectorStore:
    """Resolve the active vector store based on environment configuration.

    Env: ``REALITY_OS_VECTOR_STORE``. Unknown values fall back to the default
    and a warning is logged.
    """

    requested = os.getenv("REALITY_OS_VECTOR_STORE", _DEFAULT).strip().lower()
    implementation_cls = _REGISTRY.get(requested)
    if implementation_cls is None:
        logger.warning(
            "Unknown REALITY_OS_VECTOR_STORE=%r; falling back to %s", requested, _DEFAULT
        )
        implementation_cls = _REGISTRY[_DEFAULT]
    return implementation_cls()  # type: ignore[call-arg]


__all__ = ["VectorStore", "SqliteTfidfVectorStore", "get_vector_store"]
