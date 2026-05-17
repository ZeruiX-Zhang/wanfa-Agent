"""Integration test for ``POST /api/v2/concepts/{id}/analogies`` (Task 4.7).

Covers Requirement 8.3: analogy hits are cross-domain
(``hit.domain != source.domain``) and ranked by embedding cosine.
"""

from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient

from apps.api.app.knowledge_core import get_core
from apps.api.app.vector_store import encode_vector


def _seed_concept(core, *, concept_id, tenant_id, label, domain) -> None:
    with sqlite3.connect(core.path) as db:
        db.execute(
            """
            insert into concepts(
              id, tenant_id, label, summary, created_at,
              mastery_score, last_practiced_at, next_due_at,
              decay_lambda, ef, repetition, interval_days, domain
            ) values (?, ?, ?, ?, '2026-01-01T00:00:00+00:00',
                      0.5, null, null, 0.05, 2.5, 0, 0.0, ?)
            """,
            (concept_id, tenant_id, label, f"summary {label}", domain),
        )
        db.commit()


def _seed_item_with_vector(core, *, tenant_id, concept_id, item_id, vector) -> None:
    with sqlite3.connect(core.path) as db:
        db.execute(
            """
            insert into knowledge_items(
              id, tenant_id, title, body, source_kind, content_hash,
              quality_score, quality_tier, accuracy_score, veracity_score,
              relevance_score, created_at, updated_at, vector
            ) values (?, ?, ?, ?, 'direct_import', ?, 0.8, 'verified',
                      0.8, 0.8, 0.8, ?, ?, ?)
            """,
            (
                item_id,
                tenant_id,
                f"title {item_id}",
                f"body for {item_id} with enough words to index",
                f"hash_{item_id}",
                "2026-01-01T00:00:00+00:00",
                "2026-01-01T00:00:00+00:00",
                encode_vector(vector),
            ),
        )
        db.execute(
            "insert into concept_item(concept_id, item_id) values (?, ?)",
            (concept_id, item_id),
        )
        db.commit()


def test_analogies_filter_by_domain_and_rank(client: TestClient) -> None:
    """Hits are all cross-domain and sorted by cosine non-increasing."""

    core = get_core()
    tenant = "tnt-analogy"

    # Source concept in the "math" domain.
    _seed_concept(core, concept_id="c_src", tenant_id=tenant, label="vectors", domain="math")
    _seed_item_with_vector(
        core, tenant_id=tenant, concept_id="c_src", item_id="i_src", vector=[1.0, 0.0, 0.0]
    )

    # Cross-domain candidate, highly similar (cosine ~0.99).
    _seed_concept(core, concept_id="c_phys", tenant_id=tenant, label="forces", domain="physics")
    _seed_item_with_vector(
        core, tenant_id=tenant, concept_id="c_phys", item_id="i_phys", vector=[0.95, 0.1, 0.0]
    )

    # Cross-domain candidate, weakly similar (cosine ~0.0).
    _seed_concept(core, concept_id="c_fin", tenant_id=tenant, label="cashflow", domain="finance")
    _seed_item_with_vector(
        core, tenant_id=tenant, concept_id="c_fin", item_id="i_fin", vector=[0.0, 1.0, 0.0]
    )

    # Same-domain concept — must be excluded from analogies.
    _seed_concept(core, concept_id="c_math2", tenant_id=tenant, label="matrices", domain="math")
    _seed_item_with_vector(
        core, tenant_id=tenant, concept_id="c_math2", item_id="i_math2", vector=[1.0, 0.0, 0.0]
    )

    response = client.post(
        "/api/v2/concepts/c_src/analogies",
        headers={"X-Tenant-ID": tenant, "X-User-ID": "alice"},
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["metadata"]["mode"] == "read-only"
    assert body["source_concept_id"] == "c_src"
    assert body["source_domain"] == "math"
    assert body["analogies_available"] is True

    analogies = body["analogies"]
    assert analogies, "expected at least one cross-domain analogy"

    # No same-domain concept leaks into the result (R8.3).
    assert all(hit["domain"] != "math" for hit in analogies)
    assert "c_math2" not in {hit["concept_id"] for hit in analogies}

    # Sorted by cosine non-increasing; physics outranks finance.
    cosines = [hit["cosine"] for hit in analogies]
    assert cosines == sorted(cosines, reverse=True)
    assert analogies[0]["concept_id"] == "c_phys"


def test_unknown_concept_returns_404(client: TestClient) -> None:
    """An unknown concept id surfaces as 404 with no metadata leak."""

    response = client.post(
        "/api/v2/concepts/c_does_not_exist/analogies",
        headers={"X-Tenant-ID": "tnt-analogy-404", "X-User-ID": "alice"},
    )
    assert response.status_code == 404, response.text
