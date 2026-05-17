"""Unit test for SM-2 due selection in ``retrieval_practice_plan`` (Task 3.16).

Covers Requirement 5.3 and Property 23: the retrieval practice plan only
surfaces concepts whose ``next_due_at <= now`` (a NULL ``next_due_at`` is
treated as due immediately), and every returned exercise carries the full
cloze / counterexample / Socratic format mix.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from apps.api.app.knowledge_core import KnowledgeCore


def _seed_concept(
    core: KnowledgeCore,
    *,
    concept_id: str,
    tenant_id: str,
    label: str,
    created_at: str,
    next_due_at: str | None = None,
    mastery_score: float = 0.4,
) -> None:
    with sqlite3.connect(core.path) as db:
        db.execute(
            """
            insert into concepts(
              id, tenant_id, label, summary, created_at,
              mastery_score, last_practiced_at, next_due_at,
              decay_lambda, ef, repetition, interval_days, domain
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                concept_id,
                tenant_id,
                label,
                f"summary for {label}",
                created_at,
                mastery_score,
                None,
                next_due_at,
                0.05,
                2.5,
                0,
                0.0,
                None,
            ),
        )
        db.commit()


def _seed_item_for_concept(
    core: KnowledgeCore,
    *,
    concept_id: str,
    item_id: str,
    tenant_id: str,
    title: str,
    body: str,
) -> None:
    with sqlite3.connect(core.path) as db:
        db.execute(
            """
            insert into knowledge_items(
              id, tenant_id, title, body, source_kind, content_hash,
              quality_score, quality_tier, accuracy_score, veracity_score,
              relevance_score, created_at, updated_at
            ) values (?, ?, ?, ?, 'note', ?, 0.8, 'verified', 0.8, 0.8, 0.8, ?, ?)
            """,
            (
                item_id,
                tenant_id,
                title,
                body,
                f"hash_{item_id}",
                "2026-01-01T00:00:00+00:00",
                "2026-01-01T00:00:00+00:00",
            ),
        )
        db.execute(
            "insert into concept_item(concept_id, item_id) values (?, ?)",
            (concept_id, item_id),
        )
        db.commit()


_BODY = (
    "The quadratic formula solves polynomial equations efficiently. "
    "The discriminant determines how many real roots an equation has. "
    "Completing the square reveals the vertex of the parabola."
)


def test_practice_plan_due_only_and_format_mix(tmp_path) -> None:
    """Only due concepts are surfaced and each exercise has the format mix."""

    core = KnowledgeCore(path=tmp_path / "kc.sqlite3")
    tenant_id = "tenant_practice"
    now = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
    past = (now - timedelta(days=2)).isoformat()
    future = (now + timedelta(days=30)).isoformat()

    # Due: ``next_due_at`` is in the past.
    _seed_concept(
        core,
        concept_id="cpt_due_past",
        tenant_id=tenant_id,
        label="quadratic",
        created_at="2026-01-01T00:00:00+00:00",
        next_due_at=past,
    )
    # Due: ``next_due_at`` is NULL (never practiced -> due immediately).
    _seed_concept(
        core,
        concept_id="cpt_due_null",
        tenant_id=tenant_id,
        label="discriminant",
        created_at="2026-01-02T00:00:00+00:00",
        next_due_at=None,
    )
    # Not due: ``next_due_at`` is well in the future.
    _seed_concept(
        core,
        concept_id="cpt_not_due",
        tenant_id=tenant_id,
        label="parabola",
        created_at="2026-01-03T00:00:00+00:00",
        next_due_at=future,
    )

    for concept_id, item_id in (
        ("cpt_due_past", "itm_1"),
        ("cpt_due_null", "itm_2"),
        ("cpt_not_due", "itm_3"),
    ):
        _seed_item_for_concept(
            core,
            concept_id=concept_id,
            item_id=item_id,
            tenant_id=tenant_id,
            title=f"title {concept_id}",
            body=_BODY,
        )

    plan = core.retrieval_practice_plan(tenant_id=tenant_id, language="en", now=now)

    plan_ids = {exercise["concept_id"] for exercise in plan}
    # Only the two due concepts surface; the future-due one is excluded.
    assert plan_ids == {"cpt_due_past", "cpt_due_null"}

    # Every exercise carries the full cloze / counterexample / Socratic mix.
    for exercise in plan:
        cloze = exercise["cloze_questions"]
        assert isinstance(cloze, list)
        assert 1 <= len(cloze) <= 3
        assert all(isinstance(question, str) and question for question in cloze)
        assert isinstance(exercise["counterexample"], str)
        assert exercise["counterexample"]
        assert isinstance(exercise["socratic_question"], str)
        assert exercise["socratic_question"]
