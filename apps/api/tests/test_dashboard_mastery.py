"""Integration test for ``GET /api/v2/dashboard/mastery`` (Task 5.1).

Covers R10.1.a (heatmap grouped by domain) and R10.6 (tenant-scoped).
"""

from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from apps.api.app.knowledge_core import get_core


def _seed_concept(core, *, concept_id, tenant_id, domain, mastery_score) -> None:
    with sqlite3.connect(core.path) as db:
        db.execute(
            """
            insert into concepts(
              id, tenant_id, label, summary, created_at,
              mastery_score, last_practiced_at, next_due_at,
              decay_lambda, ef, repetition, interval_days, domain
            ) values (?, ?, ?, 'summary', '2026-01-01T00:00:00+00:00',
                      ?, null, null, 0.05, 2.5, 0, 0.0, ?)
            """,
            (concept_id, tenant_id, f"label {concept_id}", mastery_score, domain),
        )
        db.commit()


def test_mastery_heatmap_tenant_scoped(client: TestClient) -> None:
    core = get_core()
    tenant_a = "tnt-dash-mastery-a"
    tenant_b = "tnt-dash-mastery-b"

    _seed_concept(core, concept_id="dm_a1", tenant_id=tenant_a, domain="math", mastery_score=0.4)
    _seed_concept(core, concept_id="dm_a2", tenant_id=tenant_a, domain="math", mastery_score=0.8)
    _seed_concept(core, concept_id="dm_a3", tenant_id=tenant_a, domain="physics", mastery_score=0.6)
    _seed_concept(core, concept_id="dm_b1", tenant_id=tenant_b, domain="finance", mastery_score=0.9)

    response = client.get(
        "/api/v2/dashboard/mastery",
        headers={"X-Tenant-ID": tenant_a, "X-User-ID": "alice"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["metadata"]["mode"] == "read-only"

    domains = {d["domain"]: d for d in body["domains"]}
    # Only tenant A's domains appear (R10.6 — no cross-tenant leak).
    assert "finance" not in domains
    assert set(domains) == {"math", "physics"}
    assert domains["math"]["count"] == 2
    assert domains["math"]["avg_mastery"] == pytest.approx(0.6)  # mean of 0.4, 0.8
    assert body["concept_count"] == 3
