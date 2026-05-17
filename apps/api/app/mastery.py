"""Pure spaced-repetition primitives for the expert-coaching-loop.

This module is deliberately I/O-free: it exposes a frozen dataclass
:class:`MasteryState` and two pure functions :func:`sm2_update` and
:func:`decay`. Storage, audit, and request handling live in
``knowledge_core``/``coaching_session`` and call into these helpers.

Design references:
- ``design.md`` § Algorithms / 1. SM-2 update
- ``design.md`` § Algorithms / 2. Decay

Validates: Requirements 5.2, 5.5, 5.7, 17.1, 17.3
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

__all__ = ["MasteryState", "sm2_update", "decay", "grade_to_sm2", "ResultClass"]

ResultClass = Literal["success", "partial", "fail"]

# Real-world result → SM-2 grade mapping (design.md / R9.2, Property 20).
_RESULT_CLASS_TO_GRADE: dict[str, int] = {
    "success": 5,
    "partial": 3,
    "fail": 1,
}


@dataclass(frozen=True)
class MasteryState:
    """Snapshot of the SM-2 spaced-repetition state for a single concept.

    Invariants enforced by :func:`sm2_update`:

    * ``0.0 <= mastery_score <= 1.0``
    * ``ef >= 1.3``
    * ``repetition >= 0``
    * ``interval_days >= 1.0`` for graded items, ``>= 0.0`` otherwise
    * ``decay_lambda > 0``
    * ``next_due_at >= last_practiced_at``
    """

    mastery_score: float
    ef: float
    repetition: int
    interval_days: float
    last_practiced_at: datetime
    next_due_at: datetime
    decay_lambda: float


def sm2_update(grade: int, prev: MasteryState, now: datetime) -> MasteryState:
    """Apply one SM-2 update step.

    Pure function. Returns a new :class:`MasteryState`; ``prev`` is never
    mutated. Faithful to the SM-2 algorithm with the project's blended
    ``mastery_score`` recurrence (60% retention of prior score, 40% from
    the normalised grade) and the lazy-decay ``decay_lambda`` derivation
    used by :func:`decay`.

    Parameters
    ----------
    grade:
        Recall quality in ``{0, 1, 2, 3, 4, 5}``. Anything ``< 3`` resets
        the repetition counter and forces the next interval to one day.
    prev:
        Prior :class:`MasteryState` for the concept.
    now:
        Wall-clock instant at which the practice grade was captured.
        Callers SHOULD pass ``now >= prev.last_practiced_at`` so that
        the resulting ``next_due_at`` does not rewind history.

    Returns
    -------
    MasteryState
        The updated state with all invariants documented on the
        :class:`MasteryState` docstring satisfied.
    """

    if not (0 <= grade <= 5):
        raise ValueError(f"grade must be in 0..5, got {grade!r}")

    # Repetition counter and interval ----------------------------------
    if grade < 3:
        n_next = 0
        i_next = 1.0
    else:
        if prev.repetition <= 0:
            i_next = 1.0
        elif prev.repetition == 1:
            i_next = 6.0
        else:
            i_next = prev.interval_days * prev.ef
        n_next = prev.repetition + 1

    # Easiness factor — clamped at 1.3 per SM-2 spec ------------------
    ef_next = max(
        1.3,
        prev.ef + (0.1 - (5 - grade) * (0.08 + (5 - grade) * 0.02)),
    )

    # Mastery score blend (clamped to [0, 1]) -------------------------
    g_norm = grade / 5.0
    mastery_next = max(0.0, min(1.0, 0.6 * prev.mastery_score + 0.4 * g_norm))

    # Decay lambda decreases as interval grows; floor keeps it > 0 ----
    lam_next = max(1e-4, 0.5 / max(1.0, i_next))

    return MasteryState(
        mastery_score=mastery_next,
        ef=ef_next,
        repetition=n_next,
        interval_days=i_next,
        last_practiced_at=now,
        next_due_at=now + timedelta(days=i_next),
        decay_lambda=lam_next,
    )


def decay(mastery: float, lam: float, dt_days: float) -> float:
    """Exponentially decay a mastery score over ``dt_days``.

    Monotonic non-increasing in ``dt_days``: ``decay(m, lam, 0) == m``
    and for any ``dt1 <= dt2``, ``decay(m, lam, dt1) >= decay(m, lam, dt2)``.

    Negative ``dt_days`` is clamped to zero so that callers passing a
    pair of timestamps in the wrong order do not push mastery upward.
    """

    if not (0.0 <= mastery <= 1.0):
        raise ValueError(f"mastery must be in [0, 1], got {mastery!r}")
    if not (lam > 0):
        raise ValueError(f"lam must be > 0, got {lam!r}")

    dt = max(0.0, float(dt_days))
    return mastery * math.exp(-lam * dt)


def grade_to_sm2(result_class: ResultClass) -> int:
    """Map a real-world experiment ``result_class`` to an SM-2 grade.

    Per Requirement 9.2 / design Property 20:

    * ``success`` → ``5``
    * ``partial`` → ``3``
    * ``fail``    → ``1``

    Any other value raises :class:`ValueError` so that callers cannot
    silently push a malformed review into :func:`sm2_update`.
    """

    try:
        return _RESULT_CLASS_TO_GRADE[result_class]
    except KeyError as exc:  # pragma: no cover - defensive branch
        raise ValueError(
            f"unknown result_class {result_class!r}; expected one of "
            "'success', 'partial', 'fail'"
        ) from exc
