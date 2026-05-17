"""Metacognition hooks for the expert-coaching-loop (R7).

Pure rules + scoring --- no I/O. The orchestrator (Task 4.2) is what
persists :class:`MetacognitionRecord` rows and emits the
``metacognition.recorded`` audit event; this module only decides *when*
to prompt, *what* to prompt, and *how well calibrated* the user is.

Property 22 (design.md) constrains the public surface:

* ``generate_questions_you_didnt_ask`` returns between 3 and 7 questions.
* ``metacognition_score`` returns a value in ``[0, 1]``.
* ``should_prompt`` fires at most once per UTC day per session in
  Simple_Mode, and on every significant turn in Professional_Mode.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone

MIN_QUESTIONS = 3
MAX_QUESTIONS = 7


@dataclass(frozen=True)
class MetacognitionRecord:
    """One captured confidence-check / question-engagement turn.

    Mirrors the ``metacognition_records`` table (design data model 7).
    ``outcome_observed`` and ``user_confidence`` are both in ``[0, 1]``
    when present; ``None`` means "not yet resolved".
    """

    session_id: str
    turn_id: str
    user_confidence: float | None = None
    system_confidence: float | None = None
    questions_engaged: int = 0
    questions_total: int = 0
    outcome_observed: float | None = None
    created_at: str | None = None


def metacognition_score(records: Sequence[MetacognitionRecord]) -> float:
    """Aggregate calibration + engagement into a ``[0, 1]`` score (R7.4).

    ``0.6 * calibration + 0.4 * engagement`` per design.md section 8.
    Calibration defaults to ``0.5`` when no record has a resolved
    outcome; engagement defaults to ``0.0`` when no record asked any
    question.
    """

    if not records:
        return 0.0

    resolved = [
        r
        for r in records
        if r.outcome_observed is not None and r.user_confidence is not None
    ]
    if resolved:
        miss = sum(
            abs(float(r.user_confidence) - float(r.outcome_observed))  # type: ignore[arg-type]
            for r in resolved
        )
        calib = 1.0 - miss / len(resolved)
    else:
        calib = 0.5

    engaged = [r for r in records if r.questions_total > 0]
    if engaged:
        eng = sum(
            r.questions_engaged / r.questions_total for r in engaged
        ) / len(engaged)
    else:
        eng = 0.0

    return max(0.0, min(1.0, 0.6 * calib + 0.4 * eng))


def should_prompt(
    *,
    mode: str,
    last_prompt_at: datetime | None = None,
    now: datetime | None = None,
    significant: bool = True,
) -> bool:
    """Decide whether this turn should surface a metacognition prompt.

    * ``professional`` --- prompt on every *significant* turn (R7.6).
    * ``simple`` --- prompt at most once per UTC calendar day per
      session; ``last_prompt_at`` is the timestamp of the session's
      previous prompt (``None`` when it has never prompted) (R7.6,
      Property 22).

    Non-significant turns never prompt, regardless of mode.
    """

    if not significant:
        return False
    if mode == "professional":
        return True

    # Simple_Mode: one prompt per UTC day per session.
    if last_prompt_at is None:
        return True
    current = now or datetime.now(timezone.utc)
    return _utc_date(last_prompt_at) != _utc_date(current)


def _utc_date(value: datetime) -> tuple[int, int, int]:
    """Return the UTC ``(year, month, day)`` of a datetime."""

    if value.tzinfo is None:
        aware = value.replace(tzinfo=timezone.utc)
    else:
        aware = value.astimezone(timezone.utc)
    return (aware.year, aware.month, aware.day)


_GENERIC_QUESTIONS_ZH: tuple[str, ...] = (
    "这个判断的前提假设是什么？哪些假设最脆弱？",
    "如果关键约束发生变化，结论还成立吗？",
    "有没有与此结论相矛盾的证据被忽略了？",
    "专家在这里会额外考虑哪些你没有想到的因素？",
    "你这份把握来自数据还是直觉？两者一致吗？",
    "最坏情况下会发生什么？代价是否可承受？",
    "还有哪个利益相关者的视角没有被纳入考量？",
)

_GENERIC_QUESTIONS_EN: tuple[str, ...] = (
    "What assumptions does this judgement rest on, and which is weakest?",
    "If the key constraints changed, would the conclusion still hold?",
    "Is there contradicting evidence that has been overlooked?",
    "What would an expert weigh here that you have not considered?",
    "Does your confidence come from data or intuition --- do they agree?",
    "What is the worst case, and is its cost acceptable?",
    "Whose stakeholder perspective has not been accounted for?",
)


def generate_questions_you_didnt_ask(
    *,
    user_message: str = "",
    concept_labels: Sequence[str] = (),
    language: str = "zh-CN",
) -> list[str]:
    """Return 3--7 metacognitive questions the user did not ask (R7.3).

    Concept-specific questions (one per supplied label) are listed first,
    then padded with generic prompts. The result is always within
    ``[MIN_QUESTIONS, MAX_QUESTIONS]`` (Property 22).
    """

    is_zh = language != "en"
    questions: list[str] = []

    for label in concept_labels:
        label = (label or "").strip()
        if not label:
            continue
        if is_zh:
            questions.append(f"「{label}」在什么边界条件下会失效或不适用？")
        else:
            questions.append(
                f"Under what boundary conditions would '{label}' fail or not apply?"
            )
        if len(questions) >= MAX_QUESTIONS:
            break

    generic = _GENERIC_QUESTIONS_ZH if is_zh else _GENERIC_QUESTIONS_EN
    for question in generic:
        if len(questions) >= MAX_QUESTIONS:
            break
        questions.append(question)

    # ``generic`` always has >= MIN_QUESTIONS entries, so this clamp only
    # ever trims; the lower bound is structurally guaranteed.
    return questions[:MAX_QUESTIONS]
