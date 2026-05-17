"""Property-based tests for hybrid retrieval scoring.

Feature: expert-coaching-loop, Property 17: hybrid score linearity + bounds.

Targets the pure functions in ``apps.api.app.hybrid_retrieval``.
"""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from apps.api.app.hybrid_retrieval import HybridWeights, hybrid_score, normalize

_UNIT = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
_RAW_WEIGHT = st.floats(
    min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False
)


@settings(max_examples=300, deadline=None)
@given(
    w_fts=_RAW_WEIGHT,
    w_tfidf=_RAW_WEIGHT,
    w_embed=_RAW_WEIGHT,
    embed_available=st.booleans(),
    fts_norm=_UNIT,
    tfidf_norm=_UNIT,
    cos_norm=_UNIT,
)
def test_property_17_hybrid_score_linearity_and_bounds(
    w_fts: float,
    w_tfidf: float,
    w_embed: float,
    embed_available: bool,
    fts_norm: float,
    tfidf_norm: float,
    cos_norm: float,
) -> None:
    """normalize sums to 1.0 (w_embed=0 when unavailable); score in [0, 1]."""

    weights = normalize(
        HybridWeights(w_fts=w_fts, w_tfidf=w_tfidf, w_embed=w_embed),
        embed_available,
    )

    # Normalised weights sum to 1.0 and are all non-negative.
    total = weights.w_fts + weights.w_tfidf + weights.w_embed
    assert abs(total - 1.0) < 1e-9
    assert weights.w_fts >= 0.0
    assert weights.w_tfidf >= 0.0
    assert weights.w_embed >= 0.0

    # The embedding weight is exactly zero when the embedder is unavailable.
    if not embed_available:
        assert weights.w_embed == 0.0

    score = hybrid_score(fts_norm, tfidf_norm, cos_norm, weights)
    # A convex combination of [0, 1] inputs stays within [0, 1].
    assert -1e-9 <= score <= 1.0 + 1e-9

    # Linearity: scaling every input by k scales the score by k.
    k = 0.5
    scaled = hybrid_score(k * fts_norm, k * tfidf_norm, k * cos_norm, weights)
    assert abs(scaled - k * score) < 1e-9
