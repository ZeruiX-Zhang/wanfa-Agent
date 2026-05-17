"""Property-based tests for ``expert_gap_score``.

Feature: expert-coaching-loop, Property 8: Expert gap score bounds
Validates: Requirements 2.2, 2.3
"""

from __future__ import annotations

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from apps.api.app.expert_rubric import (
    ExpertRubric,
    RubricDimension,
    expert_gap_score,
)


@st.composite
def rubrics(draw):
    n_dims = draw(st.integers(min_value=1, max_value=5))
    dims = []
    weights = draw(
        st.lists(st.floats(0.1, 1.0), min_size=n_dims, max_size=n_dims)
    )
    weight_total = sum(weights) or 1.0
    for i, w in enumerate(weights):
        anchor_count = draw(st.integers(min_value=1, max_value=4))
        anchors = draw(
            st.lists(
                st.text(alphabet="abcdefghij", min_size=2, max_size=6),
                min_size=anchor_count,
                max_size=anchor_count,
            )
        )
        dims.append(
            RubricDimension(
                id=f"dim_{i}",
                weight=w / weight_total,
                anchors=tuple(anchors),
            )
        )
    return ExpertRubric(
        id="pbt",
        domain="pbt",
        version="0.0.0",
        author="pbt",
        source="pbt",
        dimensions=tuple(dims),
        examples=(),
        cited_evidence_ids=(),
    )


@settings(max_examples=200, deadline=None,
          suppress_health_check=[HealthCheck.too_slow])
@given(answer=st.text(alphabet="abcdefghij ", min_size=0, max_size=200), rubric=rubrics())
def test_property_8_expert_gap_bounds(answer: str, rubric: ExpertRubric) -> None:
    gap = expert_gap_score(answer, rubric)
    assert 0.0 <= gap.expert_gap_score <= 1.0
    assert len(gap.missing_points) <= 7
    assert gap.rubric_id == rubric.id
    assert gap.rubric_version == rubric.version


@settings(max_examples=50, deadline=None)
@given(rubric=rubrics())
def test_property_8_zero_overlap_returns_low_score(rubric: ExpertRubric) -> None:
    """An answer that shares no tokens with anchors must score 0.0."""

    # Use characters disjoint from the anchor alphabet.
    gap = expert_gap_score("XXXX YYY ZZZ 12345", rubric)
    assert gap.expert_gap_score == 0.0
    assert len(gap.missing_points) > 0


@settings(max_examples=50, deadline=None)
@given(rubric=rubrics())
def test_property_8_full_overlap_saturates(rubric: ExpertRubric) -> None:
    """An answer containing every anchor saturates the score to 1.0."""

    every_anchor = " ".join(
        anchor for dim in rubric.dimensions for anchor in dim.anchors
    )
    gap = expert_gap_score(every_anchor, rubric)
    assert gap.expert_gap_score == pytest.approx(1.0, abs=1e-9)
