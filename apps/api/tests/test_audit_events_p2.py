"""Audit event emission for P2 state changes (Task 4.16, R13.1, R13.2).

Validates the documented P2 audit event types per design.md
"Audit log event_type catalogue":

* ``metacognition.recorded`` — payload: ``session_id``, ``turn_id``
* ``experiment_review.recorded`` — payload: ``experiment_id``,
  ``result_class``
"""

from __future__ import annotations

import json
import sqlite3

from fastapi.testclient import TestClient

from apps.api.app import audit_events
from apps.api.app.knowledge_core import get_core


def _read_audit(tenant_id: str, action: str) -> list[dict]:
    with sqlite3.connect(get_core().path) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute(
            "select * from audit_log where tenant_id = ? and action = ? "
            "order by created_at asc",
            (tenant_id, action),
        ).fetchall()
    return [
        {"subject": row["subject"], "payload": json.loads(row["payload_json"] or "{}")}
        for row in rows
    ]


def test_p2_audit_events_emitted_with_documented_keys(client: TestClient) -> None:
    """metacognition.recorded and experiment_review.recorded carry their keys."""

    tenant = "tnt-p2-events"
    headers = {"X-Tenant-ID": tenant, "X-User-ID": "alice"}

    # ------------------------------------------------------------------
    # (a) metacognition.recorded — emitted by a Professional_Mode coach turn.
    # ------------------------------------------------------------------
    turn = client.post(
        "/api/v2/coach/turn",
        json={
            "user_message": "How should I decide between these designs?",
            "language": "en",
            "mode": "professional",
            "confidence_check": 0.55,
        },
        headers=headers,
    )
    assert turn.status_code == 200, turn.text
    session_id = turn.json()["session_id"]

    metacog_rows = _read_audit(tenant, audit_events.METACOGNITION_RECORDED)
    assert len(metacog_rows) == 1, f"expected 1 metacognition row, got {metacog_rows}"
    metacog_payload = metacog_rows[0]["payload"]
    assert {"session_id", "turn_id"} <= set(metacog_payload.keys())
    assert metacog_payload["session_id"] == session_id

    # ------------------------------------------------------------------
    # (b) experiment_review.recorded — emitted by the review endpoint.
    # ------------------------------------------------------------------
    review = client.post(
        "/api/v2/experiments/exp_p2/review",
        json={
            "result_class": "partial",
            "key_metrics": [],
            "notes": "",
            "concept_ids": [],
        },
        headers=headers,
    )
    assert review.status_code == 200, review.text

    review_rows = _read_audit(tenant, audit_events.EXPERIMENT_REVIEW_RECORDED)
    assert len(review_rows) == 1, f"expected 1 review row, got {review_rows}"
    review_payload = review_rows[0]["payload"]
    assert {"experiment_id", "result_class"} <= set(review_payload.keys())
    assert review_payload["experiment_id"] == "exp_p2"
    assert review_payload["result_class"] == "partial"
    assert review_rows[0]["subject"] == "exp_p2"
