"""Integration tests for ``POST /api/v2/experiments/{id}/review`` (Task 4.10).

Covers Requirements 9.1, 9.2, 9.5: a structured review persists and
hard-binds SM-2 mastery for every linked concept; an unlinked
experiment review still persists without error.
"""

from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient

from apps.api.app.knowledge_core import get_core


def _seed_concept(core, *, concept_id, tenant_id, mastery_score) -> None:
    with sqlite3.connect(core.path) as db:
        db.execute(
            """
            insert into concepts(
              id, tenant_id, label, summary, created_at,
              mastery_score, last_practiced_at, next_due_at,
              decay_lambda, ef, repetition, interval_days, domain
            ) values (?, ?, ?, ?, '2026-01-01T00:00:00+00:00',
                      ?, null, null, 0.05, 2.5, 0, 0.0, null)
            """,
            (concept_id, tenant_id, f"label {concept_id}", "summary", mastery_score),
        )
        db.commit()


def _read_mastery(core, concept_id) -> float:
    with sqlite3.connect(core.path) as db:
        row = db.execute(
            "select mastery_score from concepts where id = ?", (concept_id,)
        ).fetchone()
    return float(row[0])


def test_review_binds_mastery_for_linked_concepts(client: TestClient) -> None:
    """A success review grades every linked concept up the SM-2 curve."""

    core = get_core()
    tenant = "tnt-exp-review"
    _seed_concept(core, concept_id="erc_1", tenant_id=tenant, mastery_score=0.5)
    _seed_concept(core, concept_id="erc_2", tenant_id=tenant, mastery_score=0.5)

    response = client.post(
        "/api/v2/experiments/exp_linked/review",
        json={
            "result_class": "success",
            "key_metrics": [
                {"name": "uplift", "target": 0.1, "value": 0.12, "tolerance": 0.05}
            ],
            "notes": "worked well",
            "concept_ids": ["erc_1", "erc_2"],
        },
        headers={"X-Tenant-ID": tenant, "X-User-ID": "alice"},
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["metadata"]["mode"] == "pending-review"
    assert sorted(body["graded_concepts"]) == ["erc_1", "erc_2"]
    assert body["review"]["result_class"] == "success"
    assert body["review"]["metric_breach"] is False

    # Mastery hard-binding moved both concepts up the curve (R9.2).
    assert _read_mastery(core, "erc_1") > 0.5
    assert _read_mastery(core, "erc_2") > 0.5


def test_unlinked_experiment_review_persists_without_error(
    client: TestClient,
) -> None:
    """A review with no linked concepts still persists (R9.5)."""

    response = client.post(
        "/api/v2/experiments/exp_unlinked/review",
        json={
            "result_class": "fail",
            "key_metrics": [],
            "notes": "no concepts attached",
            "concept_ids": [],
        },
        headers={"X-Tenant-ID": "tnt-exp-unlinked", "X-User-ID": "alice"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["graded_concepts"] == []
    assert body["review"]["experiment_id"] == "exp_unlinked"
    assert body["review"]["result_class"] == "fail"
