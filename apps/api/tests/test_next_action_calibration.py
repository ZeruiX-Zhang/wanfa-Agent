"""Unit tests for the calibration-bias branch of ``decide_next_action`` (Task 3.15).

Validates Requirement 4.5: when a tenant's ``calibration_score`` is below
the configured ``REALITY_OS_CALIBRATION_THRESHOLD`` (default 0.6) and the
tenant has fewer than 10 recent reviewed predictions to learn from, the
coach SHALL bias the next action toward ``practice`` over ``learn``.

The pure decision rule lives in ``apps.api.app.coaching_session.decide_next_action``;
the orchestrator's ``_resolve_coach_session_state`` is the wiring that reads
``feature_flags.calibration_threshold()`` and the tenant's persisted
calibration records when assembling the ``SessionSnapshot``.
"""

from __future__ import annotations

import pytest

from apps.api.app import feature_flags
from apps.api.app.coaching_session import (
    SessionSnapshot,
    decide_next_action,
)


# ---------------------------------------------------------------------------
# AC: low calibration_score biases next_action toward "practice"
# ---------------------------------------------------------------------------


def test_low_calibration_biases_practice() -> None:
    """R4.5 — both branches of the calibration-bias decision row.

    Branch 1: ``calibration_score`` below the default threshold and a
    sparse calibration history (< 10 resolved records) → ``practice``.

    Branch 2: a well-calibrated user (score above threshold) with the
    same sparse history → the rule does *not* fire and the coach falls
    through to ``learn`` (the table's default outcome).
    """

    threshold = feature_flags.calibration_threshold()
    assert threshold == pytest.approx(0.6), (
        "default REALITY_OS_CALIBRATION_THRESHOLD must be 0.6 per design.md"
    )

    # --- Branch 1: low calibration_score → practice ------------------------
    low = SessionSnapshot(
        insufficient_evidence=False,
        evidence_gathering_open=False,
        # No mastery branch active so calibration is the deciding rule.
        min_due_mastery=None,
        mastery_pass_threshold=0.6,
        # Below the configured threshold (0.6) → trigger the bias.
        calibration_score=0.2,
        calibration_threshold=threshold,
        # Sparse history — the second AND in the design table is satisfied.
        calibration_records_recent=3,
        # Skill-chain branch must not pre-empt the calibration row.
        skill_chain_step_exit_satisfied=False,
        skill_chain_has_next_step=False,
        last_experiment_unreviewed=False,
    )
    assert decide_next_action(low) == "practice"

    # --- Branch 2: high calibration_score → unchanged (learn) --------------
    high = SessionSnapshot(
        insufficient_evidence=False,
        evidence_gathering_open=False,
        min_due_mastery=None,
        mastery_pass_threshold=0.6,
        # Well above threshold — the calibration row MUST NOT fire even
        # though the tenant still has a sparse history.
        calibration_score=0.9,
        calibration_threshold=threshold,
        calibration_records_recent=3,
        skill_chain_step_exit_satisfied=False,
        skill_chain_has_next_step=False,
        last_experiment_unreviewed=False,
    )
    assert decide_next_action(high) == "learn"


# ---------------------------------------------------------------------------
# Regression: the calibration row must not pre-empt earlier rows in the
# decision table (insufficient evidence + due-mastery have priority per
# design.md "next_action 决策规则").
# ---------------------------------------------------------------------------


def test_calibration_does_not_override_higher_priority_rows() -> None:
    """Low calibration must not steal priority from earlier rows.

    The design table orders the rules:

    1. ``insufficient_evidence`` + open gathering → ``awaiting_evidence``
    2. due concept below mastery threshold       → ``practice``
    3. low ``calibration_score`` (sparse history)→ ``practice``
    4. ...

    Rule 3's outcome (``practice``) coincides with rule 2's, so this
    test mainly guards rule 1: even a freshly-cold-started tenant
    (calibration_score=0) MUST surface ``awaiting_evidence`` first
    when the gathering loop is open.
    """

    threshold = feature_flags.calibration_threshold()
    snap = SessionSnapshot(
        insufficient_evidence=True,
        evidence_gathering_open=True,
        calibration_score=0.0,
        calibration_threshold=threshold,
        calibration_records_recent=0,
    )
    assert decide_next_action(snap) == "awaiting_evidence"


# ---------------------------------------------------------------------------
# Regression: a tenant with enough resolved calibration history (>= 10)
# escapes the bias-to-practice rule even when their score is low — the
# design table requires *both* conditions to fire (R4.5 / design table
# row 3).
# ---------------------------------------------------------------------------


def test_low_calibration_with_sufficient_history_does_not_bias() -> None:
    """Low score *but* >= 10 resolved records → fall through to ``learn``.

    The second AND in the design table prevents the coach from drilling a
    user who already has plenty of calibration data — at that point the
    Brier score itself is the signal, and additional practice would not
    add information.
    """

    threshold = feature_flags.calibration_threshold()
    snap = SessionSnapshot(
        insufficient_evidence=False,
        evidence_gathering_open=False,
        min_due_mastery=None,
        calibration_score=0.1,  # very poorly calibrated
        calibration_threshold=threshold,
        calibration_records_recent=25,  # but plenty of data
        skill_chain_step_exit_satisfied=False,
        skill_chain_has_next_step=False,
        last_experiment_unreviewed=False,
    )
    assert decide_next_action(snap) == "learn"
