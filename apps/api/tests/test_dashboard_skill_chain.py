"""Integration test for ``GET /api/v2/dashboard/skill-chain`` (Task 5.3).

Covers R10.1.c — completion rate per problem_type with per-step retention.
"""

from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient

from apps.api.app import skill_chain
from apps.api.app.knowledge_core import get_core


def _seed_chain_state(core, *, session_id, chain_id, step_idx, tenant_id) -> None:
    with sqlite3.connect(core.path) as db:
        db.execute(
            """
            insert into skill_chains_state(
              session_id, chain_id, step_idx, entry_state_json,
              exit_evaluated_at, tenant_id, updated_at
            ) values (?, ?, ?, '{}', null, ?, '2026-02-01T00:00:00+00:00')
            """,
            (session_id, chain_id, step_idx, tenant_id),
        )
        db.commit()


def test_completion_rate_returns_per_step_retention(client: TestClient) -> None:
    core = get_core()
    tenant = "tnt-dash-chain"

    # Use a real shipped chain so ``get_chain`` resolves problem_type + steps.
    skill_chain.load_all()
    chains = skill_chain.list_chains()
    assert chains, "expected at least one shipped skill chain"
    chain = chains[0]

    _seed_chain_state(
        core, session_id="s1", chain_id=chain.id, step_idx=0, tenant_id=tenant
    )
    _seed_chain_state(
        core, session_id="s2", chain_id=chain.id, step_idx=len(chain.steps) - 1,
        tenant_id=tenant,
    )

    response = client.get(
        "/api/v2/dashboard/skill-chain",
        headers={"X-Tenant-ID": tenant, "X-User-ID": "alice"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["metadata"]["mode"] == "read-only"

    by_type = {p["problem_type"]: p for p in body["problem_types"]}
    assert chain.problem_type in by_type
    entry = by_type[chain.problem_type]
    assert entry["chains"] == 2
    assert 0.0 <= entry["avg_completion"] <= 1.0

    retention = entry["step_retention"]
    assert len(retention) == len(chain.steps)
    # Step 0 is reached by both sessions; retention is non-increasing.
    assert retention[0] == 1.0
    assert retention == sorted(retention, reverse=True)
