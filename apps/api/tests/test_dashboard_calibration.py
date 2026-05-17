"""Integration test for ``GET /api/v2/dashboard/calibration`` (Task 5.2).

Covers R10.1.b — the calibration curve bins and Brier score are present.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from apps.api.app import calibration
from apps.api.app.knowledge_core import get_core


def test_calibration_curve_bins_present(client: TestClient) -> None:
    core = get_core()
    tenant = "tnt-dash-calib"

    # Seed three resolved calibration records.
    base = datetime(2026, 2, 1, tzinfo=timezone.utc)
    for idx, (confidence, outcome) in enumerate(
        [(0.9, 1), (0.7, 0), (0.3, 0)]
    ):
        decision_id = f"dec_calib_{idx}"
        calibration.record_prediction(
            core=core,
            tenant_id=tenant,
            decision_log_id=decision_id,
            predicted_outcome="ships",
            confidence=confidence,
            actor="alice",
            now=base + timedelta(days=idx),
        )
        calibration.record_outcome(
            core=core,
            tenant_id=tenant,
            decision_log_id=decision_id,
            binary_resolved=True,
            binary_value=outcome,
            actor="alice",
            now=base + timedelta(days=idx, hours=1),
        )

    response = client.get(
        "/api/v2/dashboard/calibration",
        headers={"X-Tenant-ID": tenant, "X-User-ID": "alice"},
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["metadata"]["mode"] == "read-only"
    assert body["resolved_count"] == 3
    assert body["brier_score"] is not None
    assert 0.0 <= body["calibration_score"] <= 1.0

    bins = body["bins"]
    assert len(bins) == 10  # decile bins
    assert sum(b["count"] for b in bins) == 3
    for b in bins:
        assert 0.0 <= b["empirical_freq"] <= 1.0
