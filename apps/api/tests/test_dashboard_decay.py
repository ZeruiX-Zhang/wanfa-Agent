"""Integration test for ``GET /api/v2/dashboard/decay`` (Task 5.4).

Covers R10.1.d — concept decay curves projected from ``last_practiced_at``.
"""

from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient

from apps.api.app.knowledge_core import get_core


def _seed_concept(core, *, concept_id, tenant_id, last_practiced_at) -> None:
    with sqlite3.connect(core.path) as db:
        db.execute(
            """
            insert into concepts(
              id, tenant_id, label, summary, created_at,
              mastery_score, last_practiced_at, next_due_at,
              decay_lambda, ef, repetition, interval_days, domain
            ) values (?, ?, ?, 'summary', '2026-01-01T00:00:00+00:00',
                      0.8, ?, null, 0.05, 2.5, 1, 1.0, 'math')
            """,
            (concept_id, tenant_id, f"label {concept_id}", last_practiced_at),
        )
        db.commit()


def test_decay_curves_use_last_practiced_at(client: TestClient) -> None:
    core = get_core()
    tenant = "tnt-dash-decay"
    practiced_at = "2026-02-10T00:00:00+00:00"

    _seed_concept(
        core, concept_id="dd_1", tenant_id=tenant, last_practiced_at=practiced_at
    )
    # A concept that has never been practised is excluded from decay curves.
    _seed_concept(core, concept_id="dd_2", tenant_id=tenant, last_practiced_at=None)

    response = client.get(
        "/api/v2/dashboard/decay",
        headers={"X-Tenant-ID": tenant, "X-User-ID": "alice"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["metadata"]["mode"] == "read-only"

    curves = {c["concept_id"]: c for c in body["curves"]}
    # Only the practised concept has a decay curve.
    assert "dd_1" in curves
    assert "dd_2" not in curves

    curve = curves["dd_1"]
    assert curve["last_practiced_at"] == practiced_at
    projection = curve["projection"]
    assert projection[0]["day"] == 0
    # Decay is monotone non-increasing over the projection horizon.
    scores = [point["score"] for point in projection]
    assert scores == sorted(scores, reverse=True)
    assert scores[0] == curve["mastery_score"]
