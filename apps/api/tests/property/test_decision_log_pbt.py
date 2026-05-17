"""Property-based test for the ``DecisionLog`` validation contract.

Feature: expert-coaching-loop, Property 24: Decision log validation
Validates: Requirements 4.1

Property 24 (design.md):
    Accepted iff ``predicted_outcome`` is non-empty (after stripping
    surrounding whitespace) AND ``confidence`` is a real number in
    ``[0.0, 1.0]``; otherwise the request is rejected (HTTP 400 / 422)
    and no row is persisted.

The test drives ``POST /api/v2/decisions`` (Task 3.9) end-to-end through
the existing ``client`` ``TestClient`` fixture. For every accepted
request we additionally verify that a sibling ``calibration_records``
row was emitted in the same write (R4.2 prerequisite, called out in the
task description). For every rejected request we verify that **no**
``decision_logs`` and **no** ``calibration_records`` row landed for the
example's tenant.

Each Hypothesis example uses a unique ``tenant_id`` so the per-example
"no leftover row" assertion is robust against earlier accepted examples
that wrote rows under their own tenants in the shared session-scoped
DB.
"""

from __future__ import annotations

import sqlite3
import uuid
from typing import Any

from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings, strategies as st

from apps.api.app.knowledge_core import default_core_path


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------


# ``predicted_outcome``: cover empty / whitespace-only / blank-shaped
# strings as well as ordinary non-empty strings. The handler trims
# whitespace before checking emptiness, so a string like ``"   "`` must
# count as empty.
_predicted_outcome_strategy = st.one_of(
    st.just(""),
    st.just("   "),
    st.text(alphabet=" \t\n", min_size=1, max_size=8),  # whitespace-only
    st.text(min_size=1, max_size=64).filter(lambda s: s.strip() != ""),
)


# ``confidence``: cover the in-range band, the boundaries, out-of-range
# values, and ``None``. ``allow_nan=True`` for the out-of-range branch
# would also exercise the NaN case but the handler does not declare a
# behavior for NaN, so we skip it (R4.1 talks about ``[0, 1]``).
_in_range_confidence = st.floats(
    min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False
)
_out_of_range_confidence = st.one_of(
    st.floats(min_value=-1e6, max_value=-1e-9, allow_nan=False, allow_infinity=False),
    st.floats(min_value=1.0 + 1e-9, max_value=1e6, allow_nan=False, allow_infinity=False),
)
_confidence_strategy = st.one_of(
    _in_range_confidence,
    _out_of_range_confidence,
    st.none(),
)


# Free-text fields shared with the existing happy-path test. We bound
# the sizes tightly so each example issues one HTTP call quickly.
_decision_strategy = st.text(min_size=1, max_size=64).filter(lambda s: s.strip() != "")
_short_text = st.text(min_size=0, max_size=32)
_text_list = st.lists(_short_text, min_size=0, max_size=4)
_review_date_strategy = st.sampled_from(
    ["", "2026-06-12", "2027-01-01", "2025-12-31"]
)


@st.composite
def _decision_payload(draw) -> dict[str, Any]:
    """Compose a request body that may or may not satisfy R4.1.

    ``predicted_outcome`` is included unconditionally (the strategy
    covers empty / whitespace / non-empty cases); ``confidence`` is
    sometimes omitted entirely, sometimes ``None``, sometimes
    out-of-range, sometimes valid. This matches the task's instruction:
    "produces float | None | out-of-range".
    """

    body: dict[str, Any] = {
        "decision": draw(_decision_strategy),
        "reasoning": draw(_text_list),
        "evidence": draw(_text_list),
        "assumptions": draw(_text_list),
        "risks": draw(_text_list),
        "success_metric": draw(_short_text),
        "review_date": draw(_review_date_strategy),
        "predicted_outcome": draw(_predicted_outcome_strategy),
    }
    confidence = draw(_confidence_strategy)
    # ``omit`` branch: don't put the key at all so the handler exercises
    # the "missing confidence" code path (which must also reject).
    omit_confidence = draw(st.booleans())
    if not omit_confidence:
        body["confidence"] = confidence
    return body


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_valid(body: dict[str, Any]) -> bool:
    """Re-implement the contract from R4.1 for the property oracle."""

    predicted_outcome = body.get("predicted_outcome")
    if not isinstance(predicted_outcome, str) or not predicted_outcome.strip():
        return False
    if "confidence" not in body:
        return False
    confidence = body["confidence"]
    if confidence is None or not isinstance(confidence, (int, float)):
        return False
    return 0.0 <= float(confidence) <= 1.0


def _count_rows(table: str, *, tenant: str) -> int:
    """Count tenant-scoped rows in ``table``; treat missing table as 0.

    A rejected request can short-circuit before ``ensure_layers_schema``
    is called, so the ``decision_logs`` / ``calibration_records`` tables
    may not exist yet when we check after the first rejected example.
    """

    with sqlite3.connect(default_core_path()) as db:
        db.row_factory = sqlite3.Row
        try:
            row = db.execute(
                f"select count(*) as n from {table} where tenant_id = ?",
                (tenant,),
            ).fetchone()
            return int(row["n"])
        except sqlite3.OperationalError:
            return 0


# ---------------------------------------------------------------------------
# Property 24 — DecisionLog validation contract
# Validates: Requirements 4.1
# ---------------------------------------------------------------------------


@settings(
    max_examples=80,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
@given(body=_decision_payload())
def test_property_24_decision_log_validation(
    client: TestClient, body: dict[str, Any]
) -> None:
    """``POST /api/v2/decisions`` accepts iff R4.1 is satisfied.

    For every example:

    * Compute the oracle ``valid = predicted_outcome non-empty AND
      confidence ∈ [0, 1]``.
    * Issue the POST under a fresh tenant (so the per-example "no row"
      assertion stays decoupled from earlier accepted examples).
    * If ``valid``: the handler must return 200, the response must
      carry ``metadata.mode == "pending-review"``, and exactly one
      ``decision_logs`` row plus exactly one ``calibration_records``
      row must exist for that tenant.
    * If not ``valid``: the handler must return 400 or 422 (the AC
      explicitly accepts both shapes — see R4.1 docstring on
      ``DecisionLogCreateRequest``) and **no** ``decision_logs`` /
      ``calibration_records`` rows can be present for that tenant.
    """

    tenant = f"tnt_pbt_dec_{uuid.uuid4().hex[:12]}"
    headers = {"X-Tenant-ID": tenant, "X-User-ID": "alice"}

    valid = _is_valid(body)

    response = client.post("/api/v2/decisions", json=body, headers=headers)

    if valid:
        # ---- Accepted request ---------------------------------------
        assert response.status_code == 200, (
            f"valid body unexpectedly rejected: {body!r} -> "
            f"{response.status_code} {response.text}"
        )
        payload = response.json()
        assert payload["metadata"]["mode"] == "pending-review"
        assert payload["metadata"]["read_only"] is False
        assert payload["tenant_id"] == tenant
        # Round-trip prediction echo.
        assert payload["predicted_outcome"] == body["predicted_outcome"].strip() or (
            payload["predicted_outcome"] == body["predicted_outcome"]
        )
        assert abs(float(payload["confidence"]) - float(body["confidence"])) < 1e-9
        # Verdict reserved as empty until evidence loop closes (R6.3).
        assert payload["verdict"] == ""

        # Exactly one decision_logs and one calibration_records row.
        assert _count_rows("decision_logs", tenant=tenant) == 1
        assert _count_rows("calibration_records", tenant=tenant) == 1

        # The calibration row must reference the persisted decision id.
        with sqlite3.connect(default_core_path()) as db:
            db.row_factory = sqlite3.Row
            calib = db.execute(
                "select * from calibration_records where decision_log_id = ?",
                (payload["id"],),
            ).fetchone()
            assert calib is not None
            assert calib["tenant_id"] == tenant
            assert abs(float(calib["confidence"]) - float(body["confidence"])) < 1e-9
            assert calib["binary_resolved"] == 0
            assert calib["brier_score"] is None
            assert calib["log_loss"] is None
    else:
        # ---- Rejected request ---------------------------------------
        assert response.status_code in (400, 422), (
            f"invalid body unexpectedly accepted: {body!r} -> "
            f"{response.status_code} {response.text}"
        )
        # No tenant-scoped row in either table.
        assert _count_rows("decision_logs", tenant=tenant) == 0, (
            f"rejected request leaked decision_logs row for tenant {tenant!r} "
            f"with body {body!r}"
        )
        assert _count_rows("calibration_records", tenant=tenant) == 0, (
            f"rejected request leaked calibration_records row for tenant "
            f"{tenant!r} with body {body!r}"
        )
