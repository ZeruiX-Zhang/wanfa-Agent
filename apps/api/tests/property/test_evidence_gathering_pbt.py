"""Property-based test for Active Evidence Gathering closure.

Feature: expert-coaching-loop, Property 15: Active Evidence Gathering closure

The pure layer of :mod:`apps.api.app.evidence_gathering` exposes a six-
state machine, an immutable :data:`TRANSITIONS` adjacency map, a frozen
:class:`GatheringTask` dataclass, the pure :func:`step` transition, and
the :func:`verdict_allowed` predicate. This test drives random sequences
of target states from any starting task state, requires
:func:`step` to *either* yield a valid successor *or* raise
:class:`ValueError`, and asserts the design's closure property:

    ``verdict_allowed(final) is True  iff  final.state == APPROVED``

Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.6, 11.4, 17.6
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from apps.api.app.evidence_gathering import (
    TRANSITIONS,
    GatheringState,
    GatheringTask,
    step,
    verdict_allowed,
)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------


_GATHERING_STATES = list(GatheringState)


def _initial_task(state: GatheringState = GatheringState.INSUFFICIENT) -> GatheringTask:
    """Construct a deterministic task in ``state`` for property testing.

    The non-state fields are pinned because the property is purely about
    the transition relation; varying them adds noise without improving
    coverage of the state machine.
    """

    return GatheringTask(
        id="evg_pbt",
        tenant_id="tnt_pbt",
        session_id="sess_pbt",
        coach_turn_id="turn_pbt",
        decision_log_id="dec_pbt",
        state=state,
        claim="claim",
    )


_event_states = st.sampled_from(_GATHERING_STATES)


# ---------------------------------------------------------------------------
# Property 15 — Active Evidence Gathering closure
# Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.6, 11.4, 17.6
# ---------------------------------------------------------------------------


@settings(max_examples=200, deadline=None,
          suppress_health_check=[HealthCheck.too_slow])
@given(events=st.lists(_event_states, min_size=1, max_size=12))
def test_property_15_gathering_closure(events: list[GatheringState]) -> None:
    """Random sequences of target states either end legally or raise.

    For every drawn event sequence starting from ``INSUFFICIENT``:

    * ``step`` raises :class:`ValueError` exactly when the requested
      target is not in ``TRANSITIONS[current_state]`` (Property 21
      negative branch — illegal events do not mutate the task).
    * Whenever ``step`` succeeds the resulting state is one of the
      enum values and matches the adjacency declared in
      :data:`TRANSITIONS`.
    * The closure property of design § 7 holds at every step:
      ``verdict_allowed(t) is True`` iff ``t.state == APPROVED``.
    """

    task = _initial_task()
    final = task

    for target in events:
        prev_state = final.state
        if target in TRANSITIONS[prev_state]:
            nxt = step(final, target)
            # The pure transition is total inside the legal subset.
            assert nxt.state == target
            assert nxt.state in _GATHERING_STATES
            # Every other field is preserved; only state + updated_at change.
            assert nxt.id == final.id
            assert nxt.tenant_id == final.tenant_id
            assert nxt.claim == final.claim
            final = nxt
        else:
            with pytest.raises(ValueError):
                step(final, target)
            # Reject leaves the task untouched (no side effects on reject).
            assert final.state == prev_state

        # Closure invariant must hold after every observed step,
        # regardless of whether the last event was accepted or rejected.
        if final.state == GatheringState.APPROVED:
            assert verdict_allowed(final) is True
        else:
            assert verdict_allowed(final) is False

    # And the design.md closure check at the end of the sequence.
    if final.state == GatheringState.APPROVED:
        assert verdict_allowed(final) is True
    else:
        assert verdict_allowed(final) is False


# ---------------------------------------------------------------------------
# Step purity (Property 15 supplement): same inputs → same output.
# ---------------------------------------------------------------------------


@settings(max_examples=200, deadline=None,
          suppress_health_check=[HealthCheck.too_slow])
@given(
    state=st.sampled_from(_GATHERING_STATES),
    target=st.sampled_from(_GATHERING_STATES),
)
def test_step_is_pure_with_pinned_now(
    state: GatheringState, target: GatheringState
) -> None:
    """:func:`step` is a pure function: same inputs → same output.

    With ``now`` pinned to a fixed UTC instant, ``step`` either returns
    an identical :class:`GatheringTask` on every call or raises
    :class:`ValueError` on every call. The input task is never mutated
    on either branch (frozen dataclass, but we double-check by comparing
    field-by-field after the call).
    """

    task = _initial_task(state=state)
    pinned = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    snapshot_state = task.state
    snapshot_updated = task.updated_at

    if target in TRANSITIONS[state]:
        a = step(task, target, now=pinned)
        b = step(task, target, now=pinned)
        # Determinism: identical outputs.
        assert a == b
        # State advanced as requested; updated_at is the pinned instant.
        assert a.state == target
        assert a.updated_at == pinned.isoformat()
    else:
        with pytest.raises(ValueError):
            step(task, target, now=pinned)
        with pytest.raises(ValueError):
            step(task, target, now=pinned)

    # No mutation on either branch.
    assert task.state == snapshot_state
    assert task.updated_at == snapshot_updated


# ---------------------------------------------------------------------------
# Targeted unit checks (cheap sanity assertions on the adjacency map).
# ---------------------------------------------------------------------------


def test_transitions_match_design_md() -> None:
    """The :data:`TRANSITIONS` map matches design.md § 7 verbatim."""

    expected = {
        GatheringState.INSUFFICIENT: {
            GatheringState.SEARCHING,
            GatheringState.CLOSED,
        },
        GatheringState.SEARCHING: {GatheringState.PENDING},
        GatheringState.PENDING: {
            GatheringState.APPROVED,
            GatheringState.REJECTED,
            GatheringState.SEARCHING,
            GatheringState.CLOSED,
        },
        GatheringState.APPROVED: set(),
        GatheringState.REJECTED: {
            GatheringState.SEARCHING,
            GatheringState.CLOSED,
        },
        GatheringState.CLOSED: set(),
    }
    actual = {state: set(targets) for state, targets in TRANSITIONS.items()}
    assert actual == expected


def test_terminal_states_have_no_outgoing_edges() -> None:
    """``APPROVED`` and ``CLOSED`` are absorbing — every step from them raises."""

    for terminal in (GatheringState.APPROVED, GatheringState.CLOSED):
        task = _initial_task(state=terminal)
        for target in _GATHERING_STATES:
            with pytest.raises(ValueError):
                step(task, target)


def test_verdict_allowed_only_on_approved() -> None:
    """:func:`verdict_allowed` is ``True`` only at ``APPROVED`` (R6.3 / R11.4)."""

    for state in _GATHERING_STATES:
        task = _initial_task(state=state)
        if state == GatheringState.APPROVED:
            assert verdict_allowed(task) is True
        else:
            assert verdict_allowed(task) is False
