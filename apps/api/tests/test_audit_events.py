"""Tests for the audit event-type catalog (Task 1.6, R13)."""

from __future__ import annotations

from apps.api.app import audit_events


REQUIRED_DESIGN_EVENT_TYPES = {
    "coaching_session.created",
    "coaching_session_transition",
    "coaching_session.archived",
    "mastery_update",
    "calibration_record",
    "rubric_check",
    "skill_chain.advance",
    "skill_chain.switch",
    "evidence_gathering.opened",
    "evidence_gathering.dispatched",
    "evidence_gathering.pending",
    "evidence_gathering.approved",
    "evidence_gathering.rejected",
    "evidence_gathering.closed",
    "experiment_review.recorded",
    "metacognition.recorded",
}


def test_event_type_catalog_complete() -> None:
    """Every event_type listed in design.md is exposed as a constant."""

    declared = set(audit_events.ALL_EVENT_TYPES)
    missing = REQUIRED_DESIGN_EVENT_TYPES - declared
    assert not missing, f"missing event types: {sorted(missing)}"


def test_event_type_constants_are_unique() -> None:
    declared = audit_events.ALL_EVENT_TYPES
    assert len(declared) == len(set(declared)), "event types must be unique"


def test_event_type_constants_are_lowercase_snakecase() -> None:
    for value in audit_events.ALL_EVENT_TYPES:
        assert value == value.lower(), f"{value} must be lowercase"
        assert " " not in value, f"{value} must not contain spaces"
