"""Integration tests for ``POST /api/v2/practice/{concept_id}/grade`` (Task 3.6).

Validates Requirements:

* **R5.2** — submitting an SM-2 grade in ``0..5`` updates ``mastery_score``,
  ``next_due_at`` and ``decay_lambda`` on the concept and persists the
  result.
* **R11.1, R11.5** — the response declares ``metadata.mode ==
  "pending-review"`` because the write appends to ``mastery_history``
  and emits a ``mastery_update`` audit row.
* **R12.3 / R10.6** — cross-tenant probes return a ``404`` whose body
  cannot be distinguished from a "not found" response (no leak of the
  other tenant's id).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from apps.api.app.knowledge_core import default_core_path, get_core


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _seed_concept(
    db_path: Path,
    *,
    concept_id: str,
    tenant_id: str,
    label: str = "test concept",
    created_at: str = "2026-01-01T00:00:00+00:00",
) -> None:
    """Insert a deterministic ``concepts`` row directly so tests do not
    depend on the ``absorb`` pipeline.

    We open a short-lived ``sqlite3`` connection on the same file the
    in-process :class:`KnowledgeCore` is using (``default_core_path``)
    so the endpoint sees the seeded row.
    """

    # Touch the singleton so the schema (including the additive coaching
    # tables and the ``concepts`` mastery columns) is created before we
    # try to insert into it. The first call to ``get_core()`` in the
    # process is responsible for the migration.
    get_core()

    with sqlite3.connect(db_path) as db:
        db.execute(
            """
            insert into concepts(
              id, tenant_id, label, summary, created_at,
              mastery_score, last_practiced_at, next_due_at,
              decay_lambda, ef, repetition, interval_days, domain
            ) values (?, ?, ?, ?, ?, 0.5, NULL, NULL, 0.05, 2.5, 0, 0.0, NULL)
            """,
            (concept_id, tenant_id, label, f"summary for {label}", created_at),
        )
        db.commit()


def _read_concept_row(db_path: Path, concept_id: str) -> sqlite3.Row | None:
    with sqlite3.connect(db_path) as db:
        db.row_factory = sqlite3.Row
        return db.execute(
            "select * from concepts where id = ?", (concept_id,)
        ).fetchone()


def _post_grade(
    client: TestClient,
    *,
    tenant: str,
    concept_id: str,
    grade: Any,
) -> Any:
    return client.post(
        f"/api/v2/practice/{concept_id}/grade",
        json={"grade": grade},
        headers={"X-Tenant-ID": tenant, "X-User-ID": "alice"},
    )


# ---------------------------------------------------------------------------
# AC: pending-review metadata + persisted SM-2 update
# ---------------------------------------------------------------------------


def test_grade_returns_pending_review_metadata(client: TestClient) -> None:
    """Acceptance test for Task 3.6.

    Asserts:

    1. ``POST /api/v2/practice/{concept_id}/grade`` with grade=4 returns
       ``200`` and ``metadata.mode == "pending-review"`` (R11.5).
    2. The response carries the freshly persisted concept (R5.2 — the
       endpoint is the canonical write path so the client can refresh
       its mastery view in one round trip).
    3. ``mastery_score`` actually moved upward and SM-2 fields are set
       (``last_practiced_at``, ``next_due_at``, ``repetition`` advanced).
    4. A second tenant attempting to grade the same concept id receives
       ``404`` (R12.3) with no leakage of the original tenant id in the
       body.
    5. Out-of-range grades (e.g. ``grade=7``) are rejected at the schema
       boundary (HTTP 422 validation error) so the row is never touched.
    """

    db_path = default_core_path()

    tenant_a = "tnt-practice-a"
    tenant_b = "tnt-practice-b"
    concept_id = "cpt_practice_endpoint"

    _seed_concept(db_path, concept_id=concept_id, tenant_id=tenant_a)

    # (1) + (2) + (3) — happy path under tenant_a.
    response = _post_grade(client, tenant=tenant_a, concept_id=concept_id, grade=4)
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["metadata"]["adapter"] == "v2.practice.grade"
    assert body["metadata"]["mode"] == "pending-review"  # R11.5
    assert body["metadata"]["read_only"] is False
    assert body["metadata"]["source_system"] == "apps:api"

    concept_payload = body["concept"]
    assert concept_payload["id"] == concept_id
    # SM-2 with grade=4 from a fresh state must raise mastery (was 0.5).
    assert concept_payload["mastery_score"] > 0.5
    # SM-2 timeline fields are populated post-practice.
    assert concept_payload["last_practiced_at"] is not None
    assert concept_payload["next_due_at"] is not None
    assert concept_payload["repetition"] == 1
    assert concept_payload["interval_days"] == pytest.approx(1.0)

    # The persisted row reflects the same numbers (no ghost write).
    persisted = _read_concept_row(db_path, concept_id)
    assert persisted is not None
    assert persisted["mastery_score"] == pytest.approx(
        concept_payload["mastery_score"]
    )
    assert persisted["last_practiced_at"] == concept_payload["last_practiced_at"]
    assert persisted["repetition"] == 1

    # (4) — cross-tenant request returns 404 and does not leak tenant_a.
    cross = _post_grade(
        client, tenant=tenant_b, concept_id=concept_id, grade=3
    )
    assert cross.status_code == 404, cross.text
    cross_text = repr(cross.json())
    assert tenant_a not in cross_text
    # The persisted row must remain untouched after the failed cross-tenant
    # call: ``repetition`` is still 1 (from the tenant_a write) rather
    # than the 2 we'd see if the second grade had landed.
    persisted_after_cross = _read_concept_row(db_path, concept_id)
    assert persisted_after_cross is not None
    assert persisted_after_cross["repetition"] == 1

    # (5) — schema validation rejects out-of-range grades before any write.
    invalid = _post_grade(
        client, tenant=tenant_a, concept_id=concept_id, grade=7
    )
    assert invalid.status_code == 422, invalid.text
    untouched = _read_concept_row(db_path, concept_id)
    assert untouched is not None
    # repetition is still 1 — the bad request did not mutate state.
    assert untouched["repetition"] == 1


# ---------------------------------------------------------------------------
# 404 path — concept that does not exist for any tenant
# ---------------------------------------------------------------------------


def test_grade_returns_404_for_unknown_concept(client: TestClient) -> None:
    """Posting against an unknown concept id returns ``404`` with a
    generic body (R12.3 — same shape as cross-tenant 404 so probes
    cannot distinguish "missing" from "wrong tenant")."""

    response = _post_grade(
        client,
        tenant="tnt-practice-missing",
        concept_id="cpt_does_not_exist",
        grade=3,
    )
    assert response.status_code == 404, response.text
    body = response.json()
    # The detail message must not echo the supplied concept id, otherwise
    # an attacker could enumerate ids by reading error bodies.
    assert "cpt_does_not_exist" not in repr(body)
