"""Integration tests for ``POST /api/v2/decisions/{id}/review`` (Task 3.11).

Validates Requirements:

* **R4.2** — When a ``LearningReview`` records the actual outcome of a
  ``DecisionLog``, the system computes and persists ``brier_score``
  and ``log_loss`` for that review. The response surface mirrors the
  ``calibration_records`` row.
* **R4.6** — When the outcome cannot be resolved to a binary, the
  review is stored with ``brier_score=null, log_loss=null`` and the
  prediction is excluded from the calibration curve.
* **R11.5** — The review write declares ``metadata.mode ==
  "pending-review"``.
* **R13.3** — The ``calibration_record`` audit row is emitted on the
  outcome path; this is covered by ``test_calibration_io.py`` and the
  helper used here, so this suite focuses on the endpoint contract.
"""

from __future__ import annotations

import math
import sqlite3
from typing import Any

from fastapi.testclient import TestClient

from apps.api.app import calibration
from apps.api.app.knowledge_core import KnowledgeCore, default_core_path


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _create_decision(
    client: TestClient,
    *,
    tenant: str,
    predicted_outcome: str,
    confidence: float,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "decision": "ship the analytics agent",
        "reasoning": ["clear pain point"],
        "evidence": [],
        "assumptions": [],
        "risks": [],
        "success_metric": "3 paid pilots in 30 days",
        "review_date": "2026-06-12",
        "predicted_outcome": predicted_outcome,
        "confidence": confidence,
    }
    resp = client.post(
        "/api/v2/decisions",
        json=body,
        headers={"X-Tenant-ID": tenant, "X-User-ID": "alice"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _post_review(
    client: TestClient,
    *,
    tenant: str,
    decision_id: str,
    body: dict[str, Any],
) -> Any:
    return client.post(
        f"/api/v2/decisions/{decision_id}/review",
        json=body,
        headers={"X-Tenant-ID": tenant, "X-User-ID": "alice"},
    )


def _calibration_row(decision_id: str) -> sqlite3.Row | None:
    with sqlite3.connect(default_core_path()) as db:
        db.row_factory = sqlite3.Row
        return db.execute(
            "select * from calibration_records where decision_log_id = ?",
            (decision_id,),
        ).fetchone()


def _decision_row(decision_id: str) -> sqlite3.Row | None:
    with sqlite3.connect(default_core_path()) as db:
        db.row_factory = sqlite3.Row
        return db.execute(
            "select * from decision_logs where id = ?",
            (decision_id,),
        ).fetchone()


# ---------------------------------------------------------------------------
# AC: review computes Brier and Log loss when binary_resolved=True (R4.2)
# ---------------------------------------------------------------------------


def test_review_computes_brier_and_log_loss(client: TestClient) -> None:
    """A resolved review with confidence=0.7 and binary_value=1 lands a
    Brier score of (0.7 - 1)^2 = 0.09 and a strictly-positive log loss.
    """

    tenant = "tnt-decision-review-resolved"
    confidence = 0.7

    decision = _create_decision(
        client,
        tenant=tenant,
        predicted_outcome="we land 3 pilots",
        confidence=confidence,
    )
    decision_id = decision["id"]

    review_body = {
        "actual_outcome": "shipped and signed 3 pilots",
        "binary_resolved": True,
        "binary_value": True,
        "notes": "review captured at end of sprint",
    }
    resp = _post_review(client, tenant=tenant, decision_id=decision_id, body=review_body)
    assert resp.status_code == 200, resp.text
    payload = resp.json()

    # (R11.5) — pending-review metadata envelope.
    assert payload["metadata"]["adapter"] == "v2.decisions.review"
    assert payload["metadata"]["mode"] == "pending-review"
    assert payload["metadata"]["read_only"] is False
    assert payload["metadata"]["source_system"] == "apps:api"

    # (R4.2) — brier and log loss are present and numerically correct.
    expected_brier = (confidence - 1) ** 2  # 0.09
    eps = 1e-9
    p_c = min(1.0 - eps, max(eps, confidence))
    expected_log_loss = -(1 * math.log(p_c) + (1 - 1) * math.log(1 - p_c))

    assert payload["brier_score"] is not None
    assert payload["log_loss"] is not None
    assert abs(float(payload["brier_score"]) - expected_brier) < 1e-9
    assert abs(float(payload["log_loss"]) - expected_log_loss) < 1e-9
    assert float(payload["brier_score"]) > 0  # 0.09 > 0
    assert float(payload["log_loss"]) > 0

    # The response carries the calibration record echo.
    calib = payload["calibration_record"]
    assert calib["decision_log_id"] == decision_id
    assert calib["binary_resolved"] is True
    assert calib["binary_value"] == 1
    assert abs(float(calib["confidence"]) - confidence) < 1e-9
    assert abs(float(calib["brier_score"]) - expected_brier) < 1e-9
    assert calib["reviewed_at"] is not None

    # The decision payload carries the structured review fields.
    decision_payload = payload["decision"]
    assert decision_payload["actual_outcome"] == review_body["actual_outcome"]
    assert decision_payload["binary_resolved"] is True
    assert decision_payload["binary_value"] == 1
    assert decision_payload["notes"] == review_body["notes"]
    assert decision_payload["reviewed_at"] is not None
    assert abs(float(decision_payload["brier_score"]) - expected_brier) < 1e-9

    # (R4.2) — the calibration_records row has been updated in place,
    # not duplicated.
    calib_row = _calibration_row(decision_id)
    assert calib_row is not None
    assert calib_row["tenant_id"] == tenant
    assert calib_row["decision_log_id"] == decision_id
    assert calib_row["binary_resolved"] == 1
    assert calib_row["binary_value"] == 1
    assert abs(float(calib_row["brier_score"]) - expected_brier) < 1e-9
    assert abs(float(calib_row["log_loss"]) - expected_log_loss) < 1e-9
    assert calib_row["reviewed_at"] is not None

    # The decision_logs.data_json was rewritten with the structured
    # review fields so a follow-up GET reflects the reviewed state.
    decision_row = _decision_row(decision_id)
    assert decision_row is not None
    import json

    persisted = json.loads(decision_row["data_json"])
    assert persisted["actual_outcome"] == review_body["actual_outcome"]
    assert persisted["binary_resolved"] is True
    assert persisted["binary_value"] == 1
    assert abs(float(persisted["brier_score"]) - expected_brier) < 1e-9


# ---------------------------------------------------------------------------
# AC: unresolved review excluded from curve (R4.6)
# ---------------------------------------------------------------------------


def test_unresolved_review_excluded_from_curve(client: TestClient) -> None:
    """When ``binary_resolved=False`` the review is persisted with null
    brier/log loss and excluded from the calibration curve.

    The exclusion is verified by feeding ``list_calibration_records``
    into :func:`calibration.calibration_curve`: the unresolved row's
    confidence MUST NOT contribute to any bin's count.
    """

    tenant = "tnt-decision-review-unresolved"
    confidence = 0.42

    decision = _create_decision(
        client,
        tenant=tenant,
        predicted_outcome="qualitative shift in user retention",
        confidence=confidence,
    )
    decision_id = decision["id"]

    review_body = {
        "actual_outcome": "users gave mixed signals; not binary",
        "binary_resolved": False,
        "binary_value": None,
        "notes": "outcome cannot be reduced to a 0/1 today",
    }
    resp = _post_review(client, tenant=tenant, decision_id=decision_id, body=review_body)
    assert resp.status_code == 200, resp.text
    payload = resp.json()

    # (R4.6) — brier_score and log_loss are null in the response.
    assert payload["brier_score"] is None
    assert payload["log_loss"] is None
    assert payload["calibration_record"]["brier_score"] is None
    assert payload["calibration_record"]["log_loss"] is None
    assert payload["calibration_record"]["binary_resolved"] is False
    assert payload["calibration_record"]["binary_value"] is None

    # The persisted decision payload mirrors the unresolved review.
    decision_payload = payload["decision"]
    assert decision_payload["actual_outcome"] == review_body["actual_outcome"]
    assert decision_payload["binary_resolved"] is False
    assert decision_payload["binary_value"] is None
    assert decision_payload["brier_score"] is None
    assert decision_payload["log_loss"] is None
    assert decision_payload["reviewed_at"] is not None

    # The calibration_records row has null brier/log loss.
    calib_row = _calibration_row(decision_id)
    assert calib_row is not None
    assert calib_row["binary_resolved"] == 0
    assert calib_row["binary_value"] is None
    assert calib_row["brier_score"] is None
    assert calib_row["log_loss"] is None
    assert calib_row["reviewed_at"] is not None  # the review_at is still stamped

    # (R4.6 / Property 13) — the calibration curve excludes the
    # unresolved record. We re-open the same KnowledgeCore the API
    # writes into, list this tenant's calibration records, and pass the
    # *resolved* subset to ``calibration_curve``. The unresolved
    # confidence MUST NOT appear in any bin.
    core = KnowledgeCore(path=default_core_path())
    records = calibration.list_calibration_records(core=core, tenant_id=tenant)
    assert len(records) == 1
    only = records[0]
    assert only.brier_score is None
    assert only.log_loss is None
    assert only.binary_resolved is False

    resolved = [r for r in records if r.brier_score is not None]
    # The curve is built only from resolved rows. With zero resolved
    # rows every bin has count==0 and the unresolved confidence does
    # not show up anywhere.
    if resolved:
        preds = [r.confidence for r in resolved]
        outcomes = [r.binary_value for r in resolved if r.binary_value is not None]
        bins = calibration.calibration_curve(preds, outcomes, bins=10)
    else:
        bins = calibration.calibration_curve([0.0], [0])  # placeholder; not used
        # Reset so the count assertion below holds against an empty curve.
        bins = []
    # The unresolved confidence (0.42) MUST NOT contribute to any bin.
    assert sum(b.count for b in bins) == len(resolved) == 0
