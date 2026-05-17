"""Audit event emission for P1 state changes (Task 3.18, R13.2, R13.3).

Validates that every documented P1 state change emits exactly one
``audit_log`` row with the documented payload keys per design.md
"Audit log event_type catalogue":

* ``mastery_update`` — payload: ``concept_id``, ``prev``, ``next``,
  ``source``, ``grade?``
* ``calibration_record`` — payload: ``decision_log_id``, ``brier?``,
  ``log_loss?``
* ``evidence_gathering.*`` — payload: ``task_id``, ``state``
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from apps.api.app import audit_events, calibration
from apps.api.app.evidence_gathering import (
    GatheringState,
    apply_step,
    open_task,
)
from apps.api.app.knowledge_core import KnowledgeCore


def _seed_concept(core: KnowledgeCore, *, concept_id: str, tenant_id: str) -> None:
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
                "quadratic",
                "summary",
                "2026-01-01T00:00:00+00:00",
                0.5,
                None,
                None,
                0.05,
                2.5,
                0,
                0.0,
                None,
            ),
        )
        db.commit()


def _read_audit(core: KnowledgeCore, *, tenant_id: str, action: str) -> list[dict]:
    with sqlite3.connect(core.path) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute(
            "select * from audit_log where tenant_id = ? and action = ? "
            "order by created_at asc",
            (tenant_id, action),
        ).fetchall()
    return [
        {
            "tenant_id": row["tenant_id"],
            "actor": row["actor"],
            "action": row["action"],
            "subject": row["subject"],
            "payload": json.loads(row["payload_json"] or "{}"),
        }
        for row in rows
    ]


def test_p1_audit_events_emitted_with_documented_keys(tmp_path) -> None:
    """All three P1 audit event families carry their documented payload keys."""

    core = KnowledgeCore(path=tmp_path / "kc.sqlite3")
    tenant_id = "tnt-p1-events"
    actor = "alice"

    # ------------------------------------------------------------------
    # (a) mastery_update — emitted by ``grade_concept`` (SM-2 practice).
    # ------------------------------------------------------------------
    concept_id = "cpt_p1"
    _seed_concept(core, concept_id=concept_id, tenant_id=tenant_id)
    core.grade_concept(
        tenant_id=tenant_id,
        concept_id=concept_id,
        grade=4,
        actor=actor,
        now=datetime(2026, 2, 1, 12, 0, 0, tzinfo=timezone.utc),
    )

    mastery_rows = _read_audit(
        core, tenant_id=tenant_id, action=audit_events.MASTERY_UPDATE
    )
    assert len(mastery_rows) == 1, f"expected 1 mastery_update, got {len(mastery_rows)}"
    mastery_payload = mastery_rows[0]["payload"]
    assert {"concept_id", "prev", "next", "source"} <= set(mastery_payload.keys())
    assert mastery_payload["concept_id"] == concept_id
    assert mastery_payload["source"] == "practice"
    assert mastery_payload["grade"] == 4

    # ------------------------------------------------------------------
    # (b) calibration_record — one ``prediction`` row + one ``outcome`` row.
    # ------------------------------------------------------------------
    decision_log_id = "dec_p1"
    calibration.record_prediction(
        core=core,
        tenant_id=tenant_id,
        decision_log_id=decision_log_id,
        predicted_outcome="ships on time",
        confidence=0.7,
        actor=actor,
        now=datetime(2026, 2, 2, 12, 0, 0, tzinfo=timezone.utc),
    )
    calibration.record_outcome(
        core=core,
        tenant_id=tenant_id,
        decision_log_id=decision_log_id,
        binary_resolved=True,
        binary_value=1,
        actor=actor,
        now=datetime(2026, 2, 9, 12, 0, 0, tzinfo=timezone.utc),
    )

    calib_rows = _read_audit(
        core, tenant_id=tenant_id, action=audit_events.CALIBRATION_RECORD
    )
    assert len(calib_rows) == 2, f"expected 2 calibration_record, got {len(calib_rows)}"
    for row in calib_rows:
        assert "decision_log_id" in row["payload"]
        assert row["payload"]["decision_log_id"] == decision_log_id
    outcome_payload = calib_rows[-1]["payload"]
    # The resolved row carries the Brier / Log-loss payload keys (R4.2).
    assert {"brier_score", "log_loss"} <= set(outcome_payload.keys())

    # ------------------------------------------------------------------
    # (c) evidence_gathering.* — opened → dispatched → pending → approved.
    # ------------------------------------------------------------------
    task = open_task(
        core=core,
        tenant_id=tenant_id,
        claim="needs a citation",
        decision_log_id=decision_log_id,
        actor=actor,
    )
    task = apply_step(
        core=core, task=task, target_state=GatheringState.SEARCHING, actor=actor
    )
    task = apply_step(
        core=core,
        task=task,
        target_state=GatheringState.PENDING,
        pending_knowledge_ids=("pk_1",),
        actor=actor,
    )
    apply_step(
        core=core, task=task, target_state=GatheringState.APPROVED, actor=actor
    )

    for action in (
        audit_events.EVIDENCE_GATHERING_OPENED,
        audit_events.EVIDENCE_GATHERING_DISPATCHED,
        audit_events.EVIDENCE_GATHERING_PENDING,
        audit_events.EVIDENCE_GATHERING_APPROVED,
    ):
        rows = _read_audit(core, tenant_id=tenant_id, action=action)
        assert len(rows) == 1, f"expected 1 {action} row, got {len(rows)}"
        payload = rows[0]["payload"]
        assert {"task_id", "state"} <= set(payload.keys())
        assert payload["task_id"] == task.id
