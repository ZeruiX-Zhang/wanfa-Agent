"""Unit tests for ``KnowledgeCore`` concept-mastery methods (Task 3.4).

Covers Requirements 5.3 (due-only practice in topological order),
5.4 (learn plan ordering), 5.6 (lazy decay-on-read), and 13.2 (the
``mastery_update`` audit event payload).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from apps.api.app import audit_events
from apps.api.app.knowledge_core import KnowledgeCore


def _new_core(tmp_path) -> KnowledgeCore:
    return KnowledgeCore(path=tmp_path / "kc.sqlite3")


def _seed_concept(
    core: KnowledgeCore,
    *,
    concept_id: str,
    tenant_id: str,
    label: str,
    created_at: str,
    mastery_score: float = 0.5,
    last_practiced_at: str | None = None,
    next_due_at: str | None = None,
    decay_lambda: float = 0.05,
    ef: float = 2.5,
    repetition: int = 0,
    interval_days: float = 0.0,
    domain: str | None = None,
) -> None:
    """Insert a deterministic ``concepts`` row directly into the DB.

    Bypasses ``absorb`` so each test controls the SM-2 starting state and
    the persisted ``last_practiced_at`` exactly. We use the public
    ``KnowledgeCore.path`` to open a short-lived connection.
    """

    summary = f"summary for {label}"
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
                summary,
                created_at,
                mastery_score,
                last_practiced_at,
                next_due_at,
                decay_lambda,
                ef,
                repetition,
                interval_days,
                domain,
            ),
        )
        db.commit()


def _add_prerequisite(
    core: KnowledgeCore,
    *,
    parent: str,
    child: str,
    tenant_id: str,
) -> None:
    with sqlite3.connect(core.path) as db:
        db.execute(
            """
            insert into concept_prerequisites(
              parent_concept_id, child_concept_id, tenant_id, weight
            ) values (?, ?, ?, 1.0)
            """,
            (parent, child, tenant_id),
        )
        db.commit()


def _read_concept_row(core: KnowledgeCore, concept_id: str) -> sqlite3.Row:
    with sqlite3.connect(core.path) as db:
        db.row_factory = sqlite3.Row
        row = db.execute(
            "select * from concepts where id = ?", (concept_id,)
        ).fetchone()
    assert row is not None, f"concept {concept_id!r} not seeded"
    return row


def _read_audit_rows(
    core: KnowledgeCore, *, action: str
) -> list[sqlite3.Row]:
    with sqlite3.connect(core.path) as db:
        db.row_factory = sqlite3.Row
        return list(
            db.execute(
                "select * from audit_log where action = ? order by created_at asc",
                (action,),
            )
        )


def _read_mastery_history(core: KnowledgeCore, concept_id: str) -> list[sqlite3.Row]:
    with sqlite3.connect(core.path) as db:
        db.row_factory = sqlite3.Row
        return list(
            db.execute(
                "select * from mastery_history where concept_id = ? order by created_at asc",
                (concept_id,),
            )
        )


def test_grade_concept_persists(tmp_path) -> None:
    """`grade_concept` writes SM-2 fields back and emits a ``mastery_update``
    audit row whose payload matches the documented R13.2 contract."""

    core = _new_core(tmp_path)
    tenant_id = "tenant_alpha"
    concept_id = "cpt_grade_persist"
    _seed_concept(
        core,
        concept_id=concept_id,
        tenant_id=tenant_id,
        label="quadratic",
        created_at="2026-01-01T00:00:00+00:00",
        mastery_score=0.5,
        last_practiced_at=None,
        next_due_at=None,
        decay_lambda=0.05,
        ef=2.5,
        repetition=0,
        interval_days=0.0,
    )

    now = datetime(2026, 2, 1, 12, 0, 0, tzinfo=timezone.utc)
    updated = core.grade_concept(
        tenant_id=tenant_id,
        concept_id=concept_id,
        grade=4,
        actor="user",
        now=now,
    )

    # Returned Concept reflects the new state.
    assert updated.id == concept_id
    assert updated.mastery_score > 0.5
    assert updated.repetition == 1
    assert updated.last_practiced_at == now.isoformat()
    assert updated.next_due_at == (now + timedelta(days=1.0)).isoformat()
    assert updated.decay_lambda > 0

    # Persisted row matches the returned snapshot.
    persisted = _read_concept_row(core, concept_id)
    assert persisted["mastery_score"] == pytest.approx(updated.mastery_score)
    assert persisted["last_practiced_at"] == now.isoformat()
    assert persisted["next_due_at"] == (now + timedelta(days=1.0)).isoformat()
    assert persisted["decay_lambda"] == pytest.approx(updated.decay_lambda)
    assert persisted["ef"] == pytest.approx(updated.ef)
    assert persisted["repetition"] == 1
    assert persisted["interval_days"] == pytest.approx(1.0)

    # Mastery history captures the change.
    history = _read_mastery_history(core, concept_id)
    assert len(history) == 1
    assert history[0]["prev_score"] == pytest.approx(0.5)
    assert history[0]["next_score"] == pytest.approx(updated.mastery_score)
    assert history[0]["source"] == "practice"
    assert history[0]["grade"] == 4
    assert history[0]["tenant_id"] == tenant_id

    # Exactly one ``mastery_update`` audit row with the documented payload.
    audits = _read_audit_rows(core, action=audit_events.MASTERY_UPDATE)
    assert len(audits) == 1
    audit = audits[0]
    assert audit["tenant_id"] == tenant_id
    assert audit["actor"] == "user"
    assert audit["subject"] == concept_id
    payload = json.loads(audit["payload_json"])
    assert payload["concept_id"] == concept_id
    assert payload["prev"] == pytest.approx(0.5)
    assert payload["next"] == pytest.approx(updated.mastery_score)
    assert payload["source"] == "practice"
    assert payload["grade"] == 4


def test_lazy_decay_on_read_no_persist_without_write(tmp_path) -> None:
    """Reading a stale concept returns a decayed in-memory score while the
    persisted row stays untouched (R5.6 lazy decay-on-read)."""

    core = _new_core(tmp_path)
    tenant_id = "tenant_decay"
    concept_id = "cpt_decay_test"

    last_practiced = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    last_practiced_iso = last_practiced.isoformat()
    persisted_score = 0.8

    _seed_concept(
        core,
        concept_id=concept_id,
        tenant_id=tenant_id,
        label="forgetting curve",
        created_at=last_practiced_iso,
        mastery_score=persisted_score,
        last_practiced_at=last_practiced_iso,
        next_due_at=last_practiced_iso,
        decay_lambda=0.05,
        ef=2.5,
        repetition=2,
        interval_days=6.0,
    )

    # 30 days later: the in-memory value must be strictly less than 0.8.
    now = last_practiced + timedelta(days=30)
    decayed = core.load_concept(tenant_id=tenant_id, concept_id=concept_id)
    assert decayed is not None
    decayed = core.lazy_decay_on_read(decayed, now=now)
    assert decayed.mastery_score < persisted_score

    # Also exercised via list_concepts (the same code path).
    listed = [c for c in core.list_concepts(tenant_id=tenant_id) if c.id == concept_id]
    assert listed, "seeded concept should appear in list_concepts"
    # list_concepts uses real wall-clock time which is well past 2026-01-01,
    # so the in-memory mastery_score must be strictly less than persisted.
    assert listed[0].mastery_score < persisted_score

    # The persisted row is unchanged (no write happened).
    persisted = _read_concept_row(core, concept_id)
    assert persisted["mastery_score"] == pytest.approx(persisted_score)
    assert persisted["last_practiced_at"] == last_practiced_iso

    # And no mastery_update audit row has been written.
    audits = _read_audit_rows(core, action=audit_events.MASTERY_UPDATE)
    assert audits == []


def test_list_due_topological_order(tmp_path) -> None:
    """`list_due_concepts` returns due rows ordered so prereqs precede
    dependents (R5.3 + R5.4 ordering)."""

    core = _new_core(tmp_path)
    tenant_id = "tenant_topo"

    base_due = "2026-01-01T00:00:00+00:00"
    _seed_concept(
        core,
        concept_id="cpt_C",
        tenant_id=tenant_id,
        label="C",
        created_at="2026-01-01T00:00:00+00:00",
        next_due_at=base_due,
    )
    _seed_concept(
        core,
        concept_id="cpt_A",
        tenant_id=tenant_id,
        label="A",
        created_at="2026-01-01T00:00:01+00:00",
        next_due_at=base_due,
    )
    _seed_concept(
        core,
        concept_id="cpt_B",
        tenant_id=tenant_id,
        label="B",
        created_at="2026-01-01T00:00:02+00:00",
        next_due_at=base_due,
    )
    # Edges: A → B → C (so the expected order is A, B, C even though
    # ``cpt_C`` was inserted first by created_at).
    _add_prerequisite(core, parent="cpt_A", child="cpt_B", tenant_id=tenant_id)
    _add_prerequisite(core, parent="cpt_B", child="cpt_C", tenant_id=tenant_id)

    now = datetime(2026, 1, 2, 0, 0, 0, tzinfo=timezone.utc)
    due = core.list_due_concepts(tenant_id=tenant_id, now=now)
    ids = [concept.id for concept in due]
    assert ids == ["cpt_A", "cpt_B", "cpt_C"]

    # Concepts not yet due are excluded.
    future = (now + timedelta(days=365)).isoformat()
    _seed_concept(
        core,
        concept_id="cpt_future",
        tenant_id=tenant_id,
        label="future",
        created_at="2026-01-01T00:00:00+00:00",
        next_due_at=future,
    )
    refreshed = core.list_due_concepts(tenant_id=tenant_id, now=now)
    refreshed_ids = [c.id for c in refreshed]
    assert "cpt_future" not in refreshed_ids
    assert refreshed_ids == ["cpt_A", "cpt_B", "cpt_C"]
