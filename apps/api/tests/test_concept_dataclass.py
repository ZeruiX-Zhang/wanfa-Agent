"""Unit tests for the SM-2 mastery extension on ``Concept`` (Task 3.3).

Covers Requirement 5.1: ``Concept`` gains
``mastery_score, last_practiced_at, next_due_at, decay_lambda, ef,
repetition, interval_days, domain`` with backwards-compatible defaults so
existing call sites that build a ``Concept`` from the original six required
fields keep working.
"""

from __future__ import annotations

from apps.api.app.knowledge_core import Concept


def test_new_fields_have_defaults() -> None:
    """Constructing a ``Concept`` with only the original required fields
    must yield safe defaults for every new SM-2 field (R5.1, R5.6)."""

    concept = Concept(
        id="cpt_test_0001",
        label="example",
        summary="example summary",
        item_ids=[],
        neighbors=[],
        created_at="2026-01-01T00:00:00+00:00",
    )

    assert concept.mastery_score == 0.0
    assert concept.decay_lambda == 0.05
    assert concept.ef == 2.5
    assert concept.repetition == 0
    assert concept.interval_days == 0.0
    assert concept.domain is None
    assert concept.last_practiced_at is None
    assert concept.next_due_at is None


def test_to_dict_includes_new_fields_with_defaults() -> None:
    """``Concept.to_dict`` must serialize all eight new fields."""

    concept = Concept(
        id="cpt_test_0002",
        label="dict-default",
        summary="dict default summary",
        item_ids=["kn_a"],
        neighbors=["cpt_other"],
        created_at="2026-01-01T00:00:00+00:00",
    )

    payload = concept.to_dict()

    assert payload["mastery_score"] == 0.0
    assert payload["decay_lambda"] == 0.05
    assert payload["ef"] == 2.5
    assert payload["repetition"] == 0
    assert payload["interval_days"] == 0.0
    assert payload["domain"] is None
    assert payload["last_practiced_at"] is None
    assert payload["next_due_at"] is None
    # Existing fields must continue to round-trip unchanged.
    assert payload["id"] == "cpt_test_0002"
    assert payload["label"] == "dict-default"
    assert payload["summary"] == "dict default summary"
    assert payload["item_ids"] == ["kn_a"]
    assert payload["neighbors"] == ["cpt_other"]
    assert payload["created_at"] == "2026-01-01T00:00:00+00:00"


def test_concept_with_all_new_fields_round_trips_through_to_dict() -> None:
    """A fully-populated ``Concept`` round-trips through ``to_dict``."""

    populated = Concept(
        id="cpt_test_0003",
        label="full-state",
        summary="full state summary",
        item_ids=["kn_a", "kn_b"],
        neighbors=["cpt_x"],
        created_at="2026-01-01T00:00:00+00:00",
        mastery_score=0.72,
        last_practiced_at="2026-02-01T12:00:00+00:00",
        next_due_at="2026-02-08T12:00:00+00:00",
        decay_lambda=0.1,
        ef=2.6,
        repetition=3,
        interval_days=7.0,
        domain="engineering",
    )

    payload = populated.to_dict()

    expected = {
        "id": "cpt_test_0003",
        "label": "full-state",
        "summary": "full state summary",
        "item_ids": ["kn_a", "kn_b"],
        "neighbors": ["cpt_x"],
        "created_at": "2026-01-01T00:00:00+00:00",
        "mastery_score": 0.72,
        "last_practiced_at": "2026-02-01T12:00:00+00:00",
        "next_due_at": "2026-02-08T12:00:00+00:00",
        "decay_lambda": 0.1,
        "ef": 2.6,
        "repetition": 3,
        "interval_days": 7.0,
        "domain": "engineering",
    }
    assert payload == expected

    # Reconstruct from the serialized payload to confirm the fields are
    # symmetrically writable on the dataclass (no read-only surprises).
    rebuilt = Concept(**payload)
    assert rebuilt == populated
