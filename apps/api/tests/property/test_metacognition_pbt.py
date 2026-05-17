"""Property-based tests for the metacognition primitives.

Feature: expert-coaching-loop, Property 22: metacognition rules.

Targets the pure functions in ``apps.api.app.metacognition`` --- no I/O,
so 200 Hypothesis examples per property finish well under one second.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from hypothesis import given, settings, strategies as st

from apps.api.app.metacognition import (
    MAX_QUESTIONS,
    MIN_QUESTIONS,
    MetacognitionRecord,
    generate_questions_you_didnt_ask,
    metacognition_score,
    should_prompt,
)

_BASE_DT = datetime(2026, 1, 1, tzinfo=timezone.utc)


@st.composite
def _records(draw) -> MetacognitionRecord:
    total = draw(st.integers(min_value=0, max_value=10))
    engaged = draw(st.integers(min_value=0, max_value=total)) if total else 0
    has_conf = draw(st.booleans())
    has_outcome = draw(st.booleans())
    unit = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    return MetacognitionRecord(
        session_id="s",
        turn_id="t",
        user_confidence=draw(unit) if has_conf else None,
        system_confidence=draw(unit) if draw(st.booleans()) else None,
        questions_engaged=engaged,
        questions_total=total,
        outcome_observed=draw(unit) if has_outcome else None,
    )


@settings(max_examples=200, deadline=None)
@given(
    records=st.lists(_records(), min_size=0, max_size=12),
    concept_labels=st.lists(
        st.text(min_size=0, max_size=8), min_size=0, max_size=10
    ),
    language=st.sampled_from(["zh-CN", "en"]),
    user_message=st.text(min_size=0, max_size=40),
)
def test_property_22_metacognition_rules(
    records: list[MetacognitionRecord],
    concept_labels: list[str],
    language: str,
    user_message: str,
) -> None:
    """metacognition_score is bounded; questions count stays in [3, 7]."""

    score = metacognition_score(records)
    assert 0.0 <= score <= 1.0
    if not records:
        assert score == 0.0

    questions = generate_questions_you_didnt_ask(
        user_message=user_message,
        concept_labels=concept_labels,
        language=language,
    )
    assert MIN_QUESTIONS <= len(questions) <= MAX_QUESTIONS
    assert all(isinstance(q, str) and q for q in questions)


@settings(max_examples=200, deadline=None)
@given(
    day_offset=st.integers(min_value=0, max_value=400),
    hour=st.integers(min_value=0, max_value=23),
    significant=st.booleans(),
)
def test_property_22_simple_mode_one_prompt_per_day(
    day_offset: int, hour: int, significant: bool
) -> None:
    """Simple_Mode never prompts twice within the same UTC day per session."""

    last_prompt = _BASE_DT
    now = _BASE_DT + timedelta(days=day_offset, hours=hour)

    fired = should_prompt(
        mode="simple",
        last_prompt_at=last_prompt,
        now=now,
        significant=significant,
    )
    if not significant:
        assert fired is False
    elif day_offset == 0:
        # Same UTC calendar day as the previous prompt -> suppressed.
        assert fired is False
    else:
        assert fired is True

    # Professional_Mode fires on every significant turn regardless of date.
    pro = should_prompt(
        mode="professional", last_prompt_at=last_prompt, now=now, significant=significant
    )
    assert pro is significant
