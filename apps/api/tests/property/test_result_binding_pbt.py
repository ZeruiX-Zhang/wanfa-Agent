"""Property-based test for real-world result binding.

Feature: expert-coaching-loop, Property 20: a review's ``result_class``
maps to the SM-2 grade ``{success:5, partial:3, fail:1}``; a key metric
breaches iff ``|value - target| > tolerance``; ``K`` trailing fails
triggers a chain switch / human-review escalation.
"""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from apps.api.app.mastery import grade_to_sm2
from apps.api.app.reality_layers import KeyMetric
from apps.api.app.skill_chain import consecutive_fail_policy, count_trailing_fails

_RESULTS = ["success", "partial", "fail"]
_EXPECTED_GRADE = {"success": 5, "partial": 3, "fail": 1}
_REAL = st.floats(
    min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False
)
_NONNEG = st.floats(
    min_value=0.0, max_value=1e6, allow_nan=False, allow_infinity=False
)


@settings(max_examples=200, deadline=None)
@given(result_class=st.sampled_from(_RESULTS))
def test_property_20_result_class_maps_to_sm2_grade(result_class: str) -> None:
    """grade_to_sm2 maps every result class to its documented grade."""

    assert grade_to_sm2(result_class) == _EXPECTED_GRADE[result_class]


@settings(max_examples=300, deadline=None)
@given(target=_REAL, value=_REAL, tolerance=_NONNEG)
def test_property_20_metric_breach_predicate(
    target: float, value: float, tolerance: float
) -> None:
    """A metric breaches iff its deviation exceeds the tolerance."""

    metric = KeyMetric(
        name="m", target=target, value=value, tolerance=tolerance
    )
    assert metric.breached == (abs(value - target) > tolerance)


@settings(max_examples=300, deadline=None)
@given(
    history=st.lists(st.sampled_from(_RESULTS), min_size=0, max_size=15),
    threshold=st.integers(min_value=1, max_value=6),
    policy=st.sampled_from(["chain_switch", "human_review"]),
)
def test_property_20_consecutive_fail_switch(
    history: list[str], threshold: int, policy: str
) -> None:
    """K trailing fails trigger the configured escalation, not before."""

    trailing = count_trailing_fails(history)
    action = consecutive_fail_policy(
        trailing_fails=trailing, threshold=threshold, policy=policy
    )

    if trailing >= threshold:
        expected = "human_review_required" if policy == "human_review" else "chain_switch"
        assert action == expected
    else:
        assert action is None
