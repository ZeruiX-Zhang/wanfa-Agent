"""Unit tests for the ``calibration.py`` IO helpers (Task 3.8).

Covers Requirement 4.2 (Brier / Log loss persisted on review) and
Requirement 13.3 (``calibration_record`` audit emission with the
documented payload keys).
"""

from __future__ import annotations

import json
import math
import sqlite3
from datetime import datetime, timezone

import pytest

from apps.api.app import audit_events, calibration
from apps.api.app.knowledge_core import KnowledgeCore


def _new_core(tmp_path) -> KnowledgeCore:
    return KnowledgeCore(path=tmp_path / "kc.sqlite3")


def _read_calibration_rows(core: KnowledgeCore) -> list[sqlite3.Row]:
    with sqlite3.connect(core.path) as db:
        db.row_factory = sqlite3.Row
        return list(
            db.execute(
                "select * from calibration_records order by created_at asc, "
                "coalesce(reviewed_at, created_at) asc"
            )
        )


def _read_audit_rows(core: KnowledgeCore, *, action: str) -> list[sqlite3.Row]:
    with sqlite3.connect(core.path) as db:
        db.row_factory = sqlite3.Row
        return list(
            db.execute(
                "select * from audit_log where action = ? order by created_at asc",
                (action,),
            )
        )


def test_records_persist_and_emit_audit(tmp_path) -> None:
    """`record_prediction` + `record_outcome` persist into ``calibration_records``
    and emit two ``calibration_record`` audit rows with documented payload keys.
    """

    core = _new_core(tmp_path)
    tenant_id = "tnt_calib_io"
    decision_log_id = "dec_1"
    confidence = 0.7
    predicted_outcome = "X"

    # Phase 1: record the prediction. ----------------------------------
    pred_now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    prediction = calibration.record_prediction(
        core=core,
        tenant_id=tenant_id,
        decision_log_id=decision_log_id,
        predicted_outcome=predicted_outcome,
        confidence=confidence,
        actor="user",
        now=pred_now,
    )

    # Returned record reflects the unresolved row.
    assert prediction.tenant_id == tenant_id
    assert prediction.decision_log_id == decision_log_id
    assert prediction.predicted_outcome == predicted_outcome
    assert prediction.confidence == pytest.approx(confidence)
    assert prediction.binary_resolved is False
    assert prediction.binary_value is None
    assert prediction.brier_score is None
    assert prediction.log_loss is None
    assert prediction.created_at == pred_now.isoformat()
    assert prediction.reviewed_at is None
    assert prediction.id is not None and prediction.id.startswith("calr_")

    # Persisted row has the expected unresolved shape.
    rows_after_predict = _read_calibration_rows(core)
    assert len(rows_after_predict) == 1
    row = rows_after_predict[0]
    assert row["id"] == prediction.id
    assert row["tenant_id"] == tenant_id
    assert row["decision_log_id"] == decision_log_id
    assert row["predicted_outcome"] == predicted_outcome
    assert row["confidence"] == pytest.approx(confidence)
    assert row["binary_resolved"] == 0
    assert row["binary_value"] is None
    assert row["brier_score"] is None
    assert row["log_loss"] is None
    assert row["created_at"] == pred_now.isoformat()
    assert row["reviewed_at"] is None

    # Exactly one ``calibration_record`` audit row with the documented
    # ``source="prediction"`` payload keys.
    audits_after_predict = _read_audit_rows(
        core, action=audit_events.CALIBRATION_RECORD
    )
    assert len(audits_after_predict) == 1
    pred_audit = audits_after_predict[0]
    assert pred_audit["tenant_id"] == tenant_id
    assert pred_audit["actor"] == "user"
    assert pred_audit["subject"] == decision_log_id
    pred_payload = json.loads(pred_audit["payload_json"])
    assert pred_payload["decision_log_id"] == decision_log_id
    assert pred_payload["confidence"] == pytest.approx(confidence)
    assert pred_payload["predicted_outcome"] == predicted_outcome
    assert pred_payload["source"] == "prediction"

    # Phase 2: record the resolved outcome. ----------------------------
    review_now = datetime(2026, 1, 8, 12, 0, 0, tzinfo=timezone.utc)
    binary_value = 1
    resolved = calibration.record_outcome(
        core=core,
        tenant_id=tenant_id,
        decision_log_id=decision_log_id,
        binary_resolved=True,
        binary_value=binary_value,
        actor="user",
        now=review_now,
    )

    # Brier and Log loss are computed from the stored confidence.
    expected_brier = (confidence - binary_value) ** 2
    eps = 1e-9
    p_c = min(1.0 - eps, max(eps, confidence))
    expected_log_loss = -(
        binary_value * math.log(p_c) + (1 - binary_value) * math.log(1 - p_c)
    )

    assert resolved.id == prediction.id  # update, not insert
    assert resolved.binary_resolved is True
    assert resolved.binary_value == binary_value
    assert resolved.brier_score == pytest.approx(expected_brier)
    assert resolved.log_loss == pytest.approx(expected_log_loss)
    assert resolved.reviewed_at == review_now.isoformat()
    assert resolved.created_at == pred_now.isoformat()  # preserved
    assert resolved.predicted_outcome == predicted_outcome
    assert resolved.confidence == pytest.approx(confidence)

    # Persisted row reflects the same updated values.
    rows_after_review = _read_calibration_rows(core)
    assert len(rows_after_review) == 1, "record_outcome must update, not insert"
    row = rows_after_review[0]
    assert row["binary_resolved"] == 1
    assert row["binary_value"] == binary_value
    assert row["brier_score"] == pytest.approx(expected_brier)
    assert row["log_loss"] == pytest.approx(expected_log_loss)
    assert row["reviewed_at"] == review_now.isoformat()
    assert row["created_at"] == pred_now.isoformat()

    # A second ``calibration_record`` audit row was emitted with
    # ``source="outcome"`` and the brier/log-loss payload keys.
    audits_after_review = _read_audit_rows(
        core, action=audit_events.CALIBRATION_RECORD
    )
    assert len(audits_after_review) == 2
    outcome_audit = audits_after_review[-1]
    assert outcome_audit["tenant_id"] == tenant_id
    assert outcome_audit["actor"] == "user"
    assert outcome_audit["subject"] == decision_log_id
    outcome_payload = json.loads(outcome_audit["payload_json"])
    assert outcome_payload["decision_log_id"] == decision_log_id
    assert outcome_payload["brier_score"] == pytest.approx(expected_brier)
    assert outcome_payload["log_loss"] == pytest.approx(expected_log_loss)
    assert outcome_payload["source"] == "outcome"

    # ``list_calibration_records`` returns the same row.
    listed = calibration.list_calibration_records(core=core, tenant_id=tenant_id)
    assert len(listed) == 1
    assert listed[0].id == prediction.id
    assert listed[0].brier_score == pytest.approx(expected_brier)
    assert listed[0].log_loss == pytest.approx(expected_log_loss)
    assert listed[0].reviewed_at == review_now.isoformat()
    # Tenant scoping: a different tenant sees no rows.
    assert calibration.list_calibration_records(core=core, tenant_id="other") == []
