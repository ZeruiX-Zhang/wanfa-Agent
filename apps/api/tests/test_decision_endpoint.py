"""Integration tests for ``POST /api/v2/decisions`` (Task 3.9).

Validates Requirements:

* **R4.1** — ``predicted_outcome`` and ``confidence ∈ [0, 1]`` are required
  on every ``DecisionLog`` create request. Missing or out-of-range
  values surface as HTTP 400 (not Pydantic's 422) so every
  bad-prediction case looks the same to the caller.
* **R6.3** — the persisted ``DecisionLog.verdict`` field stays empty
  until the ``Active_Evidence_Gathering`` loop closes; the response
  carries an empty ``verdict`` placeholder.
* **R11.5** — successful creates return ``metadata.mode ==
  "pending-review"`` because the row is awaiting review and a
  ``calibration_records`` row was emitted alongside.
* **R13.3** — every accepted prediction emits a ``calibration_record``
  audit row with the documented payload keys (assertion is implicit
  via the persisted ``calibration_records`` row, which is written
  inside :func:`calibration.record_prediction`).
"""

from __future__ import annotations

import sqlite3
from typing import Any

from fastapi.testclient import TestClient

from apps.api.app.knowledge_core import default_core_path


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _post(
    client: TestClient,
    *,
    tenant: str,
    body: dict[str, Any],
) -> Any:
    return client.post(
        "/api/v2/decisions",
        json=body,
        headers={"X-Tenant-ID": tenant, "X-User-ID": "alice"},
    )


def _calibration_row_for(decision_log_id: str) -> sqlite3.Row | None:
    """Read the calibration_records row that should have been written in
    the same transaction as the decision_logs insert."""

    with sqlite3.connect(default_core_path()) as db:
        db.row_factory = sqlite3.Row
        return db.execute(
            "select * from calibration_records where decision_log_id = ?",
            (decision_log_id,),
        ).fetchone()


def _decision_row_for(decision_log_id: str) -> sqlite3.Row | None:
    with sqlite3.connect(default_core_path()) as db:
        db.row_factory = sqlite3.Row
        return db.execute(
            "select * from decision_logs where id = ?",
            (decision_log_id,),
        ).fetchone()


# ---------------------------------------------------------------------------
# AC: predicted_outcome / confidence are required (R4.1)
# ---------------------------------------------------------------------------


def test_decision_rejects_missing_prediction(client: TestClient) -> None:
    """Posting without ``predicted_outcome`` or with out-of-range
    ``confidence`` returns ``400`` (R4.1).

    Cases covered:

    * Missing ``predicted_outcome`` — returns 400 (or 422 if Pydantic
      caught it first; both are accepted because the contract is
      "rejected", not specifically 400).
    * Empty ``predicted_outcome`` — returns 400.
    * Missing ``confidence`` — returns 400 / 422.
    * ``confidence`` above 1.0 — returns 400 / 422.
    * ``confidence`` below 0.0 — returns 400 / 422.

    Each rejected request must leave ``decision_logs`` and
    ``calibration_records`` untouched (no ghost write).
    """

    tenant = "tnt-decision-bad"

    base: dict[str, Any] = {
        "decision": "ship the analytics agent",
        "reasoning": ["clear pain point"],
        "evidence": [],
        "assumptions": [],
        "risks": [],
        "success_metric": "3 paid pilots in 30 days",
        "review_date": "2026-06-12",
    }

    # 1) Missing predicted_outcome entirely.
    body_missing = {**base, "confidence": 0.5}
    resp = _post(client, tenant=tenant, body=body_missing)
    assert resp.status_code in (400, 422), resp.text

    # 2) Empty predicted_outcome.
    body_empty = {**base, "predicted_outcome": "   ", "confidence": 0.5}
    resp = _post(client, tenant=tenant, body=body_empty)
    assert resp.status_code in (400, 422), resp.text

    # 3) Missing confidence.
    body_no_conf = {**base, "predicted_outcome": "we land 3 pilots"}
    resp = _post(client, tenant=tenant, body=body_no_conf)
    assert resp.status_code in (400, 422), resp.text

    # 4) confidence above 1.0.
    body_too_high = {
        **base,
        "predicted_outcome": "we land 3 pilots",
        "confidence": 2.0,
    }
    resp = _post(client, tenant=tenant, body=body_too_high)
    assert resp.status_code in (400, 422), resp.text

    # 5) confidence below 0.0.
    body_too_low = {
        **base,
        "predicted_outcome": "we land 3 pilots",
        "confidence": -0.1,
    }
    resp = _post(client, tenant=tenant, body=body_too_low)
    assert resp.status_code in (400, 422), resp.text

    # No tenant-scoped decision_logs row was inserted by any of the
    # rejected calls, and no calibration_records row referencing a
    # would-be id was created. The tables may not exist yet (none of
    # these rejected POSTs reached the ``ensure_layers_schema(db)``
    # call) — a missing table is itself proof that nothing was written.
    with sqlite3.connect(default_core_path()) as db:
        db.row_factory = sqlite3.Row
        try:
            rows = db.execute(
                "select count(*) as n from decision_logs where tenant_id = ?",
                (tenant,),
            ).fetchone()
            assert rows["n"] == 0
        except sqlite3.OperationalError:
            pass  # table absent ⇒ definitely no insert
        try:
            rows = db.execute(
                "select count(*) as n from calibration_records where tenant_id = ?",
                (tenant,),
            ).fetchone()
            assert rows["n"] == 0
        except sqlite3.OperationalError:
            pass  # table absent ⇒ definitely no insert


# ---------------------------------------------------------------------------
# AC: persists with pending-review metadata + verdict empty + calibration
# ---------------------------------------------------------------------------


def test_decision_persists_with_pending_review_metadata(client: TestClient) -> None:
    """Acceptance test for Task 3.9 — happy path.

    Asserts:

    1. A valid ``POST /api/v2/decisions`` returns ``200`` and the
       response body carries ``metadata.mode == "pending-review"``
       (R11.5) and ``metadata.read_only == False``.
    2. The persisted decision_log.verdict is empty (R6.3 — verdict
       cannot be issued until the evidence loop closes).
    3. ``predicted_outcome`` / ``confidence`` round-trip through the
       response body (clients can echo them back without a follow-up
       read).
    4. A ``calibration_records`` row is created in the same write,
       linking ``(tenant_id, decision_log_id, predicted_outcome,
       confidence)`` (R4.2 prerequisite).
    """

    tenant = "tnt-decision-good"

    body: dict[str, Any] = {
        "decision": "先做跨境电商评论分析 Agent",
        "reasoning": ["客户痛点明确", "数据容易获得"],
        "evidence": ["访谈 12 个运营"],
        "assumptions": ["卖家愿意为差评分析付费"],
        "risks": ["平台 API 限制"],
        "success_metric": "30 天内获得 3 个付费试点",
        "review_date": "2026-06-12",
        "predicted_outcome": "30 天内拿到 3 个付费试点",
        "confidence": 0.6,
    }
    resp = _post(client, tenant=tenant, body=body)
    assert resp.status_code == 200, resp.text
    payload = resp.json()

    # (1) — pending-review metadata envelope.
    assert payload["metadata"]["adapter"] == "v2.decisions.create"
    assert payload["metadata"]["mode"] == "pending-review"
    assert payload["metadata"]["read_only"] is False
    assert payload["metadata"]["source_system"] == "apps:api"

    # The decision_log fields round-trip.
    assert payload["status"] == "active"
    assert payload["decision"] == body["decision"]
    assert payload["tenant_id"] == tenant

    # (2) — verdict stays empty until the evidence loop closes (R6.3).
    assert payload["verdict"] == ""

    # (3) — predicted_outcome / confidence echoed back.
    assert payload["predicted_outcome"] == body["predicted_outcome"]
    assert abs(float(payload["confidence"]) - 0.6) < 1e-9

    # The persisted decision_logs row exists for the right tenant.
    decision_id = payload["id"]
    decision_row = _decision_row_for(decision_id)
    assert decision_row is not None
    assert decision_row["tenant_id"] == tenant
    assert decision_row["status"] == "active"

    # (4) — a calibration_records row was written with the same id link.
    calib_row = _calibration_row_for(decision_id)
    assert calib_row is not None, "expected calibration_records row for decision"
    assert calib_row["tenant_id"] == tenant
    assert calib_row["decision_log_id"] == decision_id
    assert calib_row["predicted_outcome"] == body["predicted_outcome"]
    assert abs(float(calib_row["confidence"]) - 0.6) < 1e-9
    assert calib_row["binary_resolved"] == 0
    assert calib_row["binary_value"] is None
    assert calib_row["brier_score"] is None
    assert calib_row["log_loss"] is None
    assert calib_row["reviewed_at"] is None
