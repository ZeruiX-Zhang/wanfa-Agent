"""Hybrid retrieval scoring (R8.2) --- pure functions, no I/O.

Combines three retrieval signals --- SQLite FTS5 (BM25), TF-IDF cosine,
and dense-embedding cosine --- into a single weighted score.

Property 17 (design.md) constrains the surface:

* ``normalize`` returns weights that sum to ``1.0``, with ``w_embed``
  forced to ``0`` when the embedder is unavailable.
* ``hybrid_score`` is linear in its three inputs and stays within
  ``[0, 1]`` whenever the inputs are min-max normalised to ``[0, 1]``.
"""

from __future__ import annotations

from dataclasses import dataclass

# design.md data model 8: hybrid_retrieval_weights defaults (0.4, 0.3, 0.3).
DEFAULT_W_FTS = 0.4
DEFAULT_W_TFIDF = 0.3
DEFAULT_W_EMBED = 0.3


@dataclass(frozen=True)
class HybridWeights:
    """Per-tenant retrieval-signal weights (design data model 8)."""

    w_fts: float = DEFAULT_W_FTS
    w_tfidf: float = DEFAULT_W_TFIDF
    w_embed: float = DEFAULT_W_EMBED


def normalize(weights: HybridWeights, embed_available: bool) -> HybridWeights:
    """Rescale weights to sum to ``1.0`` (R8.2).

    When ``embed_available`` is ``False`` the embedding weight is dropped
    to ``0`` *before* normalisation, so the remaining FTS / TF-IDF
    weights absorb the full mass. A non-positive total degrades to an
    even FTS/TF-IDF split.
    """

    fts = max(0.0, weights.w_fts)
    tfidf = max(0.0, weights.w_tfidf)
    embed = max(0.0, weights.w_embed) if embed_available else 0.0

    total = fts + tfidf + embed
    if total <= 0.0:
        return HybridWeights(0.5, 0.5, 0.0)
    return HybridWeights(fts / total, tfidf / total, embed / total)


def hybrid_score(
    fts_norm: float,
    tfidf_norm: float,
    cos_norm: float,
    weights: HybridWeights,
) -> float:
    """Weighted linear combination of the three normalised signals.

    Inputs are expected to be min-max normalised to ``[0, 1]`` by the
    caller; given normalised weights the result is itself in ``[0, 1]``.
    """

    return (
        weights.w_fts * fts_norm
        + weights.w_tfidf * tfidf_norm
        + weights.w_embed * cos_norm
    )
