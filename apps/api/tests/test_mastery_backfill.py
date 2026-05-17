"""Tests for ``apps.api.app.mastery_backfill`` (Task 1.8)."""

from __future__ import annotations

import sqlite3

import pytest

from apps.api.app.coaching_schema import apply_coaching_schema
from apps.api.app.mastery_backfill import (
    DEFAULT_DECAY_LAMBDA,
    DEFAULT_MASTERY_SCORE,
    backfill_mastery,
)


def _make_db_with_concept(rows: list[dict]) -> sqlite3.Connection:
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript(
        """
        create table concepts (
          id text primary key,
          tenant_id text not null,
          label text not null,
          summary text not null,
          created_at text not null
        );
        """
    )
    apply_coaching_schema(db)
    for row in rows:
        db.execute(
            "insert into concepts(id, tenant_id, label, summary, created_at, "
            "mastery_score, last_practiced_at, decay_lambda) "
            "values (:id, :tenant_id, :label, :summary, :created_at, "
            ":mastery_score, :last_practiced_at, :decay_lambda)",
            row,
        )
    db.commit()
    return db


def test_backfill_idempotent_skips_already_set() -> None:
    db = _make_db_with_concept(
        [
            {
                "id": "c1",
                "tenant_id": "tnt",
                "label": "fresh",
                "summary": "",
                "created_at": "2026-01-01",
                "mastery_score": 0.0,
                "last_practiced_at": None,
                "decay_lambda": 0.05,
            },
            {
                "id": "c2",
                "tenant_id": "tnt",
                "label": "already practiced",
                "summary": "",
                "created_at": "2026-01-01",
                "mastery_score": 0.8,
                "last_practiced_at": "2026-01-05",
                "decay_lambda": 0.04,
            },
        ]
    )

    report1 = backfill_mastery(db)
    db.commit()
    assert report1.scanned == 2
    assert report1.updated == 1

    rows = {r["id"]: r for r in db.execute(
        "select id, mastery_score, decay_lambda, last_practiced_at from concepts"
    ).fetchall()}
    assert rows["c1"]["mastery_score"] == DEFAULT_MASTERY_SCORE
    assert rows["c1"]["decay_lambda"] == DEFAULT_DECAY_LAMBDA
    # Untouched row keeps its real practice history.
    assert rows["c2"]["mastery_score"] == pytest.approx(0.8)
    assert rows["c2"]["last_practiced_at"] == "2026-01-05"

    # Second call must be a no-op.
    report2 = backfill_mastery(db)
    db.commit()
    assert report2.scanned == 2
    assert report2.updated == 0
