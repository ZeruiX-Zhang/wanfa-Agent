"""Tests for the additive expert-coaching-loop SQLite schema.

Validates Task 1.1 acceptance criteria:
``test_schema_creates_all_tables_idempotent`` — calling
``apply_coaching_schema`` twice on a disposable database creates all eleven
new tables and is a no-op on the second call.
"""

from __future__ import annotations

import sqlite3

import pytest

from apps.api.app.coaching_schema import COACHING_TABLES, apply_coaching_schema


@pytest.fixture()
def db() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    try:
        yield connection
    finally:
        connection.close()


def _table_names(db: sqlite3.Connection) -> set[str]:
    rows = db.execute(
        "select name from sqlite_master where type='table'"
    ).fetchall()
    return {row[0] for row in rows}


def test_schema_creates_all_tables_idempotent(db: sqlite3.Connection) -> None:
    apply_coaching_schema(db)

    tables_after_first = _table_names(db)
    for name in COACHING_TABLES:
        assert name in tables_after_first, f"missing table after first call: {name}"

    # Second call must not error and must not change the table set.
    apply_coaching_schema(db)
    tables_after_second = _table_names(db)
    assert tables_after_first == tables_after_second


def test_schema_does_not_modify_existing_tables(db: sqlite3.Connection) -> None:
    db.execute(
        "create table sentinel (id text primary key, value text not null)"
    )
    db.execute("insert into sentinel(id, value) values('s1', 'baseline')")

    apply_coaching_schema(db)

    row = db.execute("select id, value from sentinel where id='s1'").fetchone()
    assert row is not None
    assert row["id"] == "s1"
    assert row["value"] == "baseline"


def test_tenant_id_is_required_on_every_new_table(db: sqlite3.Connection) -> None:
    apply_coaching_schema(db)

    # ``hybrid_retrieval_weights`` uses ``tenant_id`` as PK so it cannot be
    # nullable; other tables declare ``tenant_id`` NOT NULL explicitly.
    tables_with_tenant = set(COACHING_TABLES) - {"concept_prerequisites"}
    # ``concept_prerequisites`` still has tenant_id; include it for the check.
    tables_with_tenant.add("concept_prerequisites")

    for name in tables_with_tenant:
        cols = db.execute(f"pragma table_info({name})").fetchall()
        tenant_cols = [c for c in cols if c["name"] == "tenant_id"]
        assert tenant_cols, f"{name} is missing tenant_id"
        # ``notnull`` is 1 when the column has NOT NULL constraint.
        assert tenant_cols[0]["notnull"] == 1, f"{name}.tenant_id must be NOT NULL"


def test_evidence_gathering_state_check(db: sqlite3.Connection) -> None:
    apply_coaching_schema(db)
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "insert into evidence_gathering_tasks "
            "(id, tenant_id, state, claim, created_at, updated_at) "
            "values ('t1','tnt','bogus','c','2026-01-01','2026-01-01')"
        )


def test_experiment_review_result_class_check(db: sqlite3.Connection) -> None:
    apply_coaching_schema(db)
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "insert into experiment_reviews "
            "(id, tenant_id, experiment_id, result_class, created_at) "
            "values ('r1','tnt','exp1','bogus','2026-01-01')"
        )



def test_concept_columns_present_with_defaults(db: sqlite3.Connection) -> None:
    """Task 1.2 acceptance: SM-2 mastery columns exist with safe defaults."""

    db.executescript(
        """
        create table concepts (
          id text primary key,
          tenant_id text not null,
          label text not null,
          summary text not null,
          created_at text not null
        );
        insert into concepts(id, tenant_id, label, summary, created_at)
          values ('c1','tnt','existing','pre-migration','2026-01-01');
        """
    )

    apply_coaching_schema(db)

    cols = {row[1]: row for row in db.execute("pragma table_info(concepts)").fetchall()}
    for expected in (
        "mastery_score",
        "last_practiced_at",
        "next_due_at",
        "decay_lambda",
        "domain",
        "ef",
        "repetition",
        "interval_days",
    ):
        assert expected in cols, f"concepts.{expected} missing"

    row = db.execute(
        "select mastery_score, decay_lambda, ef, repetition, interval_days, "
        "last_practiced_at, next_due_at, domain from concepts where id='c1'"
    ).fetchone()
    assert row["mastery_score"] == 0.0
    assert row["decay_lambda"] == 0.05
    assert row["ef"] == 2.5
    assert row["repetition"] == 0
    assert row["interval_days"] == 0.0
    assert row["last_practiced_at"] is None
    assert row["next_due_at"] is None
    assert row["domain"] is None

    # Idempotent on re-apply.
    apply_coaching_schema(db)


def test_knowledge_items_vector_column(db: sqlite3.Connection) -> None:
    """Task 1.3 acceptance: ``knowledge_items.vector`` BLOB column added."""

    db.executescript(
        """
        create table knowledge_items (
          id text primary key,
          tenant_id text not null,
          title text not null,
          body text not null,
          source_kind text not null,
          content_hash text not null,
          quality_score real not null,
          quality_tier text not null,
          accuracy_score real not null,
          veracity_score real not null,
          relevance_score real not null,
          tags_json text not null default '[]',
          language text not null default 'zh-CN',
          review_required integer not null default 1,
          created_at text not null,
          updated_at text not null
        );
        """
    )

    apply_coaching_schema(db)

    cols = {row[1]: row for row in db.execute("pragma table_info(knowledge_items)").fetchall()}
    assert "vector" in cols
    # SQLite reports ``BLOB`` as the declared type.
    assert cols["vector"][2].lower() == "blob"

    # Idempotent on re-apply.
    apply_coaching_schema(db)
