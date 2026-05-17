"""Property-based test for cross-domain analogy ranking.

Feature: expert-coaching-loop, Property 18: analogy hits all satisfy
``domain != source.domain`` and are sorted by cosine non-increasing.

Targets the pure function ``vector_store.rank_analogies``.
"""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from apps.api.app.vector_store import rank_analogies

_DOMAINS = ["math", "physics", "finance", "biology", None]
_COORD = st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False)
_VECTOR = st.lists(_COORD, min_size=3, max_size=3)


@st.composite
def _candidates(draw) -> list[dict]:
    count = draw(st.integers(min_value=0, max_value=12))
    out: list[dict] = []
    for idx in range(count):
        out.append(
            {
                "concept_id": f"c{idx}",
                "label": f"label {idx}",
                "domain": draw(st.sampled_from(_DOMAINS)),
                "vector": draw(st.one_of(st.none(), _VECTOR)),
            }
        )
    return out


@settings(max_examples=300, deadline=None)
@given(
    source_domain=st.sampled_from(_DOMAINS),
    source_vector=st.one_of(st.none(), _VECTOR),
    candidates=_candidates(),
    limit=st.integers(min_value=1, max_value=10),
)
def test_property_18_analogy_ranking(
    source_domain,
    source_vector,
    candidates,
    limit,
) -> None:
    """All hits are cross-domain and cosine-ordered non-increasing."""

    hits = rank_analogies(
        source_domain=source_domain,
        source_vector=source_vector,
        candidates=candidates,
        limit=limit,
    )

    assert len(hits) <= limit

    for hit in hits:
        # Cross-domain only: domain is set and differs from the source.
        assert hit["domain"] is not None
        assert hit["domain"] != source_domain
        assert -1.0 - 1e-9 <= hit["cosine"] <= 1.0 + 1e-9

    cosines = [hit["cosine"] for hit in hits]
    assert cosines == sorted(cosines, reverse=True)
