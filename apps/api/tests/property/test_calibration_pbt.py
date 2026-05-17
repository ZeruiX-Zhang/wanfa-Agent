"""Property-based tests for the pure calibration primitives.

Feature: expert-coaching-loop, Property 12: Brier score bounds and equality
Feature: expert-coaching-loop, Property 13: Calibration curve bin invariants
Feature: expert-coaching-loop, Property 14: calibration_score aggregation

These tests target the I/O-free helpers in ``apps.api.app.calibration``
and avoid all storage so 200 Hypothesis examples per property finish
well under one second.
"""

from __future__ import annotations

import math

import pytest
from hypothesis import given, settings, strategies as st

from apps.api.app.calibration import (
    CalibrationRecord,
    brier_score,
    calibration_curve,
    calibration_score,
)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------


_PROB = st.floats(
    min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False
)
_OUTCOME = st.integers(min_value=0, max_value=1)


@st.composite
def _aligned_preds_outcomes(draw, max_size: int = 64):
    """Generate ``(preds, outcomes)`` of equal length in ``[1, max_size]``."""

    n = draw(st.integers(min_value=1, max_value=max_size))
    preds = draw(st.lists(_PROB, min_size=n, max_size=n))
    outcomes = draw(st.lists(_OUTCOME, min_size=n, max_size=n))
    return preds, outcomes


@st.composite
def _calibration_records(draw, max_size: int = 80):
    """Generate a list of :class:`CalibrationRecord`.

    Roughly two-thirds of records are resolved (``brier_score`` populated)
    so that :func:`calibration_score` exercises both the empty-aggregate
    branch and the typical case where the window is partially full.
    """

    n = draw(st.integers(min_value=0, max_value=max_size))
    records: list[CalibrationRecord] = []
    for _ in range(n):
        confidence = draw(_PROB)
        resolved = draw(st.booleans())
        if resolved:
            outcome = draw(_OUTCOME)
            brier = (confidence - outcome) ** 2
            # Use clipped log loss so the value matches what storage
            # would persist for a resolved row.
            eps = 1e-9
            p_c = min(1.0 - eps, max(eps, confidence))
            ll = -(outcome * math.log(p_c) + (1 - outcome) * math.log(1 - p_c))
        else:
            outcome = None
            brier = None
            ll = None
        records.append(
            CalibrationRecord(
                predicted_outcome="pbt",
                confidence=confidence,
                binary_resolved=resolved,
                binary_value=outcome,
                brier_score=brier,
                log_loss=ll,
            )
        )
    return records


# ---------------------------------------------------------------------------
# Property 12 — Brier score bounds and zero-on-match
# Validates: Requirements 4.2, 17.2
# ---------------------------------------------------------------------------


@settings(max_examples=200, deadline=None)
@given(po=_aligned_preds_outcomes())
def test_property_12_brier_bounds_and_zero_on_match(po) -> None:
    """``brier_score`` is bounded in [0,1] and zero iff predictions match.

    For binary inputs ``(p in [0,1], o in {0,1})``, ``(p - o)^2 <= 1``,
    so the mean of squared errors is bounded by 1. The score is exactly
    ``0.0`` when every prediction is in ``{0, 1}`` and matches its
    outcome.
    """

    preds, outcomes = po
    score = brier_score(preds, outcomes)

    # Bounded in [0, 1].
    assert 0.0 <= score <= 1.0

    # Zero iff every p in {0, 1} matches its outcome.
    matched = all(
        (p == 0.0 and o == 0) or (p == 1.0 and o == 1)
        for p, o in zip(preds, outcomes)
    )
    if matched:
        assert score == 0.0

    # And the converse direction: a zero score with binary predictions
    # implies every prediction matched.
    if score == 0.0 and all(p in (0.0, 1.0) for p in preds):
        for p, o in zip(preds, outcomes):
            assert int(p) == o


# A targeted check: forcing matched binary inputs always yields 0.0.
@settings(max_examples=100, deadline=None)
@given(outcomes=st.lists(_OUTCOME, min_size=1, max_size=64))
def test_property_12_binary_match_is_exactly_zero(outcomes: list[int]) -> None:
    preds = [float(o) for o in outcomes]
    assert brier_score(preds, outcomes) == 0.0


# ---------------------------------------------------------------------------
# Property 13 — calibration curve bin invariants
# Validates: Requirements 4.3, 17.5
# ---------------------------------------------------------------------------


@settings(max_examples=200, deadline=None)
@given(po=_aligned_preds_outcomes(), bins=st.integers(min_value=1, max_value=20))
def test_property_13_calibration_curve_invariants(po, bins: int) -> None:
    """Bin counts sum to N, frequencies are bounded, and last bin closes on right."""

    preds, outcomes = po
    curve = calibration_curve(preds, outcomes, bins=bins)

    # One bin per requested bin.
    assert len(curve) == bins

    # Bin edges tile [0, 1] exactly with no overlaps.
    expected_edges = [i / bins for i in range(bins + 1)]
    for i, b in enumerate(curve):
        assert b.lo == expected_edges[i]
        assert b.hi == expected_edges[i + 1]

    # Every count is non-negative and sums to the input size.
    assert all(b.count >= 0 for b in curve)
    assert sum(b.count for b in curve) == len(preds)

    # Empirical frequencies are bounded in [0, 1].
    assert all(0.0 <= b.empirical_freq <= 1.0 for b in curve)

    # When count > 0, mean_pred sits within the bin's half-open / closed range.
    for i, b in enumerate(curve):
        if b.count == 0:
            continue
        is_last = i == bins - 1
        # Allow tiny floating-point slack on the closed side of the last bin.
        if is_last:
            assert b.lo <= b.mean_pred <= b.hi + 1e-12
        else:
            assert b.lo <= b.mean_pred < b.hi + 1e-12

    # ``p == 1.0`` always lands in the last bin (right-closed).
    if any(p == 1.0 for p in preds):
        assert curve[-1].count >= sum(1 for p in preds if p == 1.0)


# ---------------------------------------------------------------------------
# Property 14 — calibration_score aggregation
# Validates: Requirements 4.4
# ---------------------------------------------------------------------------


@settings(max_examples=200, deadline=None)
@given(records=_calibration_records(), window=st.integers(min_value=1, max_value=80))
def test_property_14_calibration_score_aggregation(
    records: list[CalibrationRecord], window: int
) -> None:
    """``calibration_score`` matches the closed-form aggregation in design.md."""

    score = calibration_score(records, window=window)

    # Bounded in [0, 1] regardless of input mix.
    assert 0.0 <= score <= 1.0

    resolved = [r for r in records if r.brier_score is not None]

    if not resolved:
        # No reviewed decision yet → cold-start zero (design Open Questions).
        assert score == 0.0
        return

    tail = resolved[-window:]
    mean_brier = sum(r.brier_score for r in tail) / len(tail)
    expected = max(0.0, min(1.0, 1.0 - mean_brier))
    assert score == pytest.approx(expected, abs=1e-12)
