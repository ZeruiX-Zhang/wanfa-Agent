"""Property-based test for the next_action decision table.

Feature: expert-coaching-loop, Property 6: next_action follows decision table
Validates: Requirements 1.5, 4.5
"""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from apps.api.app.coaching_session import (
    SessionSnapshot,
    decide_next_action,
)


@st.composite
def snapshots(draw):
    return SessionSnapshot(
        insufficient_evidence=draw(st.booleans()),
        evidence_gathering_open=draw(st.booleans()),
        min_due_mastery=draw(st.one_of(st.none(), st.floats(0.0, 1.0))),
        mastery_pass_threshold=draw(st.floats(0.3, 0.9)),
        calibration_score=draw(st.floats(0.0, 1.0)),
        calibration_threshold=draw(st.floats(0.3, 0.9)),
        calibration_records_recent=draw(st.integers(0, 50)),
        skill_chain_step_exit_satisfied=draw(st.booleans()),
        skill_chain_has_next_step=draw(st.booleans()),
        last_experiment_unreviewed=draw(st.booleans()),
    )


@settings(max_examples=200, deadline=None)
@given(snap=snapshots())
def test_property_6_next_action_table(snap: SessionSnapshot) -> None:
    """``decide_next_action`` follows the decision table from design.md."""

    action = decide_next_action(snap)

    if snap.insufficient_evidence and snap.evidence_gathering_open:
        assert action == "awaiting_evidence"
        return

    if (
        snap.min_due_mastery is not None
        and snap.min_due_mastery < snap.mastery_pass_threshold
    ):
        assert action == "practice"
        return

    if (
        snap.calibration_score < snap.calibration_threshold
        and snap.calibration_records_recent < 10
    ):
        assert action == "practice"
        return

    if snap.skill_chain_step_exit_satisfied and snap.skill_chain_has_next_step:
        assert action == "experiment"
        return

    if snap.last_experiment_unreviewed:
        assert action == "review"
        return

    assert action == "learn"
