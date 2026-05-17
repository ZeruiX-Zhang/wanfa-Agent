"""Property-based tests for the SM-2 mastery primitives.

Feature: expert-coaching-loop, Property 10: SM-2 update invariants
Feature: expert-coaching-loop, Property 11: decay monotone

These tests target the pure functions in ``apps.api.app.mastery`` and
deliberately avoid all I/O so that 200 Hypothesis examples per property
finish well under one second.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from hypothesis import given, settings, strategies as st

from apps.api.app.mastery import MasteryState, decay, sm2_update


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------


# Anchor datetimes inside a finite, well-defined band so that arithmetic
# in ``sm2_update`` cannot overflow ``datetime``'s representable range.
_BASE_DT = datetime(2025, 1, 1, tzinfo=timezone.utc)


@st.composite
def _prev_states(draw) -> MasteryState:
    """Generate a valid prior :class:`MasteryState`.

    Constrains every field to the invariants the rest of the system
    promises to maintain so that we exercise ``sm2_update`` over its
    real input space rather than degenerate inputs.
    """

    repetition = draw(st.integers(min_value=0, max_value=20))
    interval_days = draw(st.floats(min_value=0.0, max_value=365.0,
                                    allow_nan=False, allow_infinity=False))
    ef = draw(st.floats(min_value=1.3, max_value=3.0,
                        allow_nan=False, allow_infinity=False))
    mastery_score = draw(st.floats(min_value=0.0, max_value=1.0,
                                    allow_nan=False, allow_infinity=False))
    last_practiced_offset = draw(st.integers(min_value=0, max_value=365))
    last_practiced_at = _BASE_DT + timedelta(days=last_practiced_offset)
    decay_lambda = draw(st.floats(min_value=1e-4, max_value=1.0,
                                   allow_nan=False, allow_infinity=False))
    return MasteryState(
        mastery_score=mastery_score,
        ef=ef,
        repetition=repetition,
        interval_days=interval_days,
        last_practiced_at=last_practiced_at,
        next_due_at=last_practiced_at + timedelta(days=max(interval_days, 0.0)),
        decay_lambda=decay_lambda,
    )


# ---------------------------------------------------------------------------
# Property 10 — SM-2 update invariants
# Validates: Requirements 5.2, 5.7, 17.1
# ---------------------------------------------------------------------------


@settings(max_examples=200, deadline=None)
@given(
    prev=_prev_states(),
    grade=st.integers(min_value=0, max_value=5),
    now_offset_days=st.floats(min_value=0.0, max_value=720.0,
                               allow_nan=False, allow_infinity=False),
)
def test_property_10_sm2_invariants(
    prev: MasteryState, grade: int, now_offset_days: float
) -> None:
    """``sm2_update`` preserves the invariants documented in design.md."""

    now = prev.last_practiced_at + timedelta(days=now_offset_days)

    nxt = sm2_update(grade, prev, now)

    # Bounded mastery score.
    assert 0.0 <= nxt.mastery_score <= 1.0

    # Decay lambda is strictly positive (required by ``decay``).
    assert nxt.decay_lambda > 0.0

    # SM-2 ef floor.
    assert nxt.ef >= 1.3

    # Next-due never precedes the prior practice timestamp.
    assert nxt.next_due_at >= prev.last_practiced_at

    # Repetition resets on lapse, otherwise increments by one.
    if grade < 3:
        assert nxt.repetition == 0
    else:
        assert nxt.repetition == prev.repetition + 1

    # ``last_practiced_at`` advances to the supplied ``now``.
    assert nxt.last_practiced_at == now


# ---------------------------------------------------------------------------
# Property 11 — decay monotonicity
# Validates: Requirements 5.5, 17.3
# ---------------------------------------------------------------------------


@settings(max_examples=200, deadline=None)
@given(
    mastery=st.floats(min_value=0.0, max_value=1.0,
                       allow_nan=False, allow_infinity=False),
    lam=st.floats(min_value=1e-4, max_value=5.0,
                   allow_nan=False, allow_infinity=False),
    dt_a=st.floats(min_value=0.0, max_value=365.0,
                    allow_nan=False, allow_infinity=False),
    dt_b=st.floats(min_value=0.0, max_value=365.0,
                    allow_nan=False, allow_infinity=False),
)
def test_property_11_decay_monotonicity(
    mastery: float, lam: float, dt_a: float, dt_b: float
) -> None:
    """``decay`` is monotonic non-increasing in ``dt_days`` and zero-stable."""

    dt1, dt2 = sorted((dt_a, dt_b))

    v1 = decay(mastery, lam, dt1)
    v2 = decay(mastery, lam, dt2)

    # Non-negativity.
    assert v1 >= 0.0
    assert v2 >= 0.0

    # Monotone non-increasing in dt.
    assert v1 >= v2

    # Identity at dt == 0.
    assert decay(mastery, lam, 0.0) == mastery
