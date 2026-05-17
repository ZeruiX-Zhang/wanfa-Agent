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

import array
import logging
import math
import os
import sys
from collections.abc import Callable, Sequence
from typing import Protocol, runtime_checkable

from . import feature_flags
from .knowledge_core import (
    KnowledgeCore,
    KnowledgeItem,
    _concepts_for_item,
    _row_to_item,
    get_core,
)


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Vector (de)serialisation — little-endian float32 (R8.1)
# ---------------------------------------------------------------------------


def encode_vector(values: Sequence[float]) -> bytes:
    """Pack an embedding into a little-endian ``float32`` BLOB.

    The on-disk format is fixed (little-endian) so a database written on
    one architecture reads back identically on another (R8.1).
    """

    arr = array.array("f", (float(v) for v in values))
    if sys.byteorder != "little":
        arr.byteswap()
    return arr.tobytes()


def decode_vector(blob: bytes) -> list[float]:
    """Inverse of :func:`encode_vector` — unpack a little-endian BLOB."""

    arr = array.array("f")
    arr.frombytes(bytes(blob))
    if sys.byteorder != "little":
        arr.byteswap()
    return list(arr)


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity in ``[-1, 1]``; ``0.0`` when either vector is zero."""

    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


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


class SqliteEmbedVectorStore:
    """Embedding backend: cosine search over stored ``float32`` vectors.

    The cosine path only runs when ``REALITY_OS_EMBED_MODE=online`` *and*
    an ``embedder`` callable is available. In every other case
    (``offline``, ``disabled``, or no embedder) the store falls back to
    :class:`SqliteTfidfVectorStore` and makes **no outbound call** ---
    that fallback is deterministic on a stable DB (R8.4, R8.6,
    Property 19).

    ``embedder`` is an injectable ``Callable[[str], list[float]]`` so the
    store can be exercised without a live embedding service; production
    wiring resolves it from ``model_registry``'s ``embedder`` slot.
    """

    def __init__(
        self,
        core: KnowledgeCore | None = None,
        *,
        embedder: Callable[[str], Sequence[float]] | None = None,
    ) -> None:
        self._core = core or get_core()
        self._embedder = embedder

    def embed_available(self) -> bool:
        """True iff the cosine path will run instead of the TF-IDF fallback."""

        return feature_flags.embed_mode() == "online" and self._embedder is not None

    def search(
        self,
        *,
        tenant_id: str,
        query: str,
        limit: int = 8,
    ) -> list[tuple[KnowledgeItem, float]]:
        if not self.embed_available():
            # offline / disabled / no embedder -> TF-IDF, no outbound call.
            return SqliteTfidfVectorStore(self._core).search(
                tenant_id=tenant_id, query=query, limit=limit
            )
        assert self._embedder is not None  # narrowed by embed_available()
        query_vec = list(self._embedder(query))
        return self._cosine_search(tenant_id=tenant_id, query_vec=query_vec, limit=limit)

    def _cosine_search(
        self,
        *,
        tenant_id: str,
        query_vec: Sequence[float],
        limit: int,
    ) -> list[tuple[KnowledgeItem, float]]:
        """Rank tenant items by cosine similarity against ``query_vec``."""

        scored: list[tuple[KnowledgeItem, float]] = []
        with self._core._lock, self._core._connect() as db:  # type: ignore[attr-defined]
            rows = db.execute(
                "select * from knowledge_items "
                "where tenant_id = ? and vector is not null",
                (tenant_id,),
            ).fetchall()
            for row in rows:
                vec = decode_vector(row["vector"])
                score = cosine_similarity(query_vec, vec)
                item = _row_to_item(row, _concepts_for_item(db, row["id"]))
                scored.append((item, score))
        # Deterministic order: cosine desc, then item id for tie-breaking.
        scored.sort(key=lambda pair: (-pair[1], pair[0].id))
        return scored[: max(0, limit)]


def rank_analogies(
    *,
    source_domain: str | None,
    source_vector: Sequence[float] | None,
    candidates: "Sequence[dict]",
    limit: int = 5,
) -> list[dict]:
    """Rank cross-domain analogy candidates by cosine similarity (R8.3).

    Pure function (Property 18). A candidate qualifies only when its
    ``domain`` is set *and* differs from ``source_domain`` --- analogies
    are deliberately cross-domain. The result is sorted by cosine
    non-increasing, with ``concept_id`` as a deterministic tie-break.

    Each candidate dict is expected to expose ``concept_id``, ``label``,
    ``domain`` and ``vector``. Candidates without a usable vector (or
    when ``source_vector`` is missing) are skipped.
    """

    ranked: list[dict] = []
    for candidate in candidates:
        domain = candidate.get("domain")
        if domain is None or domain == source_domain:
            continue
        vector = candidate.get("vector")
        if not source_vector or not vector:
            continue
        ranked.append(
            {
                "concept_id": candidate.get("concept_id"),
                "label": candidate.get("label"),
                "domain": domain,
                "cosine": cosine_similarity(source_vector, vector),
            }
        )
    ranked.sort(key=lambda hit: (-hit["cosine"], str(hit["concept_id"])))
    return ranked[: max(0, limit)]


_REGISTRY: dict[str, "type[VectorStore]"] = {
    "sqlite_tfidf": SqliteTfidfVectorStore,  # type: ignore[dict-item]
    "sqlite_embed": SqliteEmbedVectorStore,  # type: ignore[dict-item]
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


__all__ = [
    "VectorStore",
    "SqliteTfidfVectorStore",
    "SqliteEmbedVectorStore",
    "get_vector_store",
    "encode_vector",
    "decode_vector",
    "cosine_similarity",
    "rank_analogies",
]
