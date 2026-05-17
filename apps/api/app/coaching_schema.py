"""Additive SQLite schema for the ``expert-coaching-loop`` feature.

This module owns the eleven new tables and their indexes introduced by the
feature spec at ``.kiro/specs/expert-coaching-loop``. Every statement uses
``CREATE TABLE IF NOT EXISTS`` / ``CREATE INDEX IF NOT EXISTS`` so calling
``apply_coaching_schema`` repeatedly is a no-op on an already-migrated
database (R12.1 tenant scoping + R16.1 legacy preservation).

Design references:
- ``.kiro/specs/expert-coaching-loop/design.md`` § "Data Models" tables 1–11
- ``.kiro/specs/expert-coaching-loop/requirements.md`` R12.1, R16.1
"""

from __future__ import annotations

import sqlite3


_COACHING_SCHEMA_SQL = """
-- 1. coaching_sessions ----------------------------------------------------
create table if not exists coaching_sessions (
  id text primary key,
  tenant_id text not null,
  user_id text not null,
  profile_id text not null,
  state text not null check (state in (
    'active','awaiting_evidence','awaiting_practice','awaiting_experiment',
    'awaiting_review','paused','archived'
  )),
  current_chain_id text,
  current_step_idx integer not null default 0,
  last_action text,
  consecutive_failures integer not null default 0,
  created_at text not null,
  updated_at text not null,
  last_turn_at text not null,
  archived_at text
);

create index if not exists idx_coaching_sessions_tenant_state
  on coaching_sessions(tenant_id, state);

create index if not exists idx_coaching_sessions_tenant_last_turn
  on coaching_sessions(tenant_id, last_turn_at);

-- 2. coaching_session_state_log ------------------------------------------
create table if not exists coaching_session_state_log (
  id text primary key,
  session_id text not null,
  tenant_id text not null,
  from_state text not null,
  to_state text not null,
  actor text,
  reason text,
  payload_json text not null default '{}',
  created_at text not null
);

create index if not exists idx_coaching_session_state_log_session
  on coaching_session_state_log(session_id, created_at);

create index if not exists idx_coaching_session_state_log_tenant
  on coaching_session_state_log(tenant_id, created_at);

-- 3. skill_chains_state --------------------------------------------------
create table if not exists skill_chains_state (
  session_id text not null,
  chain_id text not null,
  step_idx integer not null default 0,
  entry_state_json text not null default '{}',
  exit_evaluated_at text,
  tenant_id text not null,
  updated_at text not null,
  primary key (session_id, chain_id)
);

create index if not exists idx_skill_chains_state_tenant
  on skill_chains_state(tenant_id, chain_id);

-- 4. expert_rubric_versions ----------------------------------------------
create table if not exists expert_rubric_versions (
  id text primary key,
  tenant_id text not null,
  domain text not null,
  version text not null,
  author text not null,
  source text not null,
  cited_evidence_ids_json text not null default '[]',
  loaded_at text not null,
  status text not null check (status in ('active','refused','superseded')),
  refused_reason text
);

create unique index if not exists ux_expert_rubric_versions_domain_version
  on expert_rubric_versions(domain, version);

create index if not exists idx_expert_rubric_versions_tenant
  on expert_rubric_versions(tenant_id, loaded_at);

-- 5. calibration_records -------------------------------------------------
create table if not exists calibration_records (
  id text primary key,
  tenant_id text not null,
  decision_log_id text not null,
  predicted_outcome text not null,
  confidence real not null check (confidence >= 0.0 and confidence <= 1.0),
  binary_resolved integer not null default 0,
  binary_value integer,
  brier_score real,
  log_loss real,
  created_at text not null,
  reviewed_at text
);

create index if not exists idx_calibration_records_tenant_reviewed
  on calibration_records(tenant_id, reviewed_at);

create index if not exists idx_calibration_records_decision
  on calibration_records(decision_log_id);

-- 6. mastery_history -----------------------------------------------------
create table if not exists mastery_history (
  id text primary key,
  tenant_id text not null,
  concept_id text not null,
  prev_score real not null,
  next_score real not null,
  source text not null check (source in ('practice','decay','experiment_review')),
  grade integer,
  created_at text not null
);

create index if not exists idx_mastery_history_tenant_created
  on mastery_history(tenant_id, created_at);

create index if not exists idx_mastery_history_concept
  on mastery_history(concept_id, created_at);

-- 7. metacognition_records -----------------------------------------------
create table if not exists metacognition_records (
  id text primary key,
  tenant_id text not null,
  session_id text not null,
  turn_id text not null,
  user_confidence real,
  system_confidence real,
  questions_engaged integer not null default 0,
  questions_total integer not null default 0,
  outcome_observed integer,
  created_at text not null
);

create index if not exists idx_metacognition_records_session
  on metacognition_records(session_id, created_at);

create index if not exists idx_metacognition_records_tenant
  on metacognition_records(tenant_id, created_at);

-- 8. experiment_reviews --------------------------------------------------
create table if not exists experiment_reviews (
  id text primary key,
  tenant_id text not null,
  experiment_id text not null,
  result_class text not null check (result_class in ('success','partial','fail')),
  key_metrics_json text not null default '[]',
  metric_breach integer not null default 0,
  notes text not null default '',
  created_at text not null
);

create index if not exists idx_experiment_reviews_experiment
  on experiment_reviews(experiment_id, created_at);

create index if not exists idx_experiment_reviews_tenant
  on experiment_reviews(tenant_id, created_at);

-- 9. hybrid_retrieval_weights --------------------------------------------
create table if not exists hybrid_retrieval_weights (
  tenant_id text not null primary key,
  w_fts real not null default 0.4 check (w_fts >= 0.0),
  w_tfidf real not null default 0.3 check (w_tfidf >= 0.0),
  w_embed real not null default 0.3 check (w_embed >= 0.0),
  updated_at text not null
);

-- 10. evidence_gathering_tasks -------------------------------------------
create table if not exists evidence_gathering_tasks (
  id text primary key,
  tenant_id text not null,
  session_id text,
  coach_turn_id text,
  decision_log_id text,
  state text not null check (state in (
    'insufficient','searching','pending','approved','rejected','closed_with_reason'
  )),
  claim text not null,
  pending_knowledge_ids_json text not null default '[]',
  created_at text not null,
  updated_at text not null
);

create index if not exists idx_evidence_gathering_tasks_session
  on evidence_gathering_tasks(session_id, updated_at);

create index if not exists idx_evidence_gathering_tasks_decision
  on evidence_gathering_tasks(decision_log_id);

create index if not exists idx_evidence_gathering_tasks_tenant_state
  on evidence_gathering_tasks(tenant_id, state);

-- 11. concept_prerequisites ----------------------------------------------
create table if not exists concept_prerequisites (
  parent_concept_id text not null,
  child_concept_id text not null,
  tenant_id text not null,
  weight real not null default 1.0,
  primary key (parent_concept_id, child_concept_id)
);

create index if not exists idx_concept_prerequisites_child
  on concept_prerequisites(child_concept_id);

create index if not exists idx_concept_prerequisites_tenant
  on concept_prerequisites(tenant_id);
"""


COACHING_TABLES: tuple[str, ...] = (
    "coaching_sessions",
    "coaching_session_state_log",
    "skill_chains_state",
    "expert_rubric_versions",
    "calibration_records",
    "mastery_history",
    "metacognition_records",
    "experiment_reviews",
    "hybrid_retrieval_weights",
    "evidence_gathering_tasks",
    "concept_prerequisites",
)


# Additive ALTER TABLE migrations on existing tables. Each entry is
# ``(table, column, ddl_fragment)`` where ``ddl_fragment`` is the column
# definition to append after ``ALTER TABLE table ADD COLUMN``. Defaults are
# safe for existing rows so the migration is non-breaking (R5.1, R5.6, R8.1).
_ADDITIVE_COLUMNS: tuple[tuple[str, str, str], ...] = (
    # SM-2 mastery extension on ``concepts`` (Task 1.2 / R5.1, R5.6).
    ("concepts", "mastery_score", "real not null default 0.0"),
    ("concepts", "last_practiced_at", "text"),
    ("concepts", "next_due_at", "text"),
    ("concepts", "decay_lambda", "real not null default 0.05"),
    ("concepts", "domain", "text"),
    ("concepts", "ef", "real not null default 2.5"),
    ("concepts", "repetition", "integer not null default 0"),
    ("concepts", "interval_days", "real not null default 0.0"),
    # Vector column on ``knowledge_items`` (Task 1.3 / R8.1). Stored as
    # little-endian float32 packed bytes; ``BLOB`` keeps backwards compat.
    ("knowledge_items", "vector", "blob"),
)


def _existing_columns(db: sqlite3.Connection, table: str) -> set[str]:
    rows = db.execute(f"pragma table_info({table})").fetchall()
    return {row[1] for row in rows}


def _table_exists(db: sqlite3.Connection, table: str) -> bool:
    row = db.execute(
        "select 1 from sqlite_master where type='table' and name=?", (table,)
    ).fetchone()
    return row is not None


def apply_additive_columns(db: sqlite3.Connection) -> None:
    """Add new columns to existing tables when they are missing.

    Skips a column if its parent table is not present yet (e.g. a fresh
    in-memory DB used purely to test the coaching schema in isolation).
    """

    cache: dict[str, set[str]] = {}
    for table, column, ddl in _ADDITIVE_COLUMNS:
        if not _table_exists(db, table):
            continue
        existing = cache.get(table)
        if existing is None:
            existing = _existing_columns(db, table)
            cache[table] = existing
        if column in existing:
            continue
        db.execute(f"alter table {table} add column {column} {ddl}")
        existing.add(column)


def apply_coaching_schema(db: sqlite3.Connection) -> None:
    """Create or upgrade the additive coaching-loop schema.

    Idempotent: calling this twice on the same connection is a no-op. The
    function does not modify any pre-existing table or column. It uses the
    caller's transaction context so the eleven new tables either all appear
    together or none do.

    Parameters
    ----------
    db:
        An open ``sqlite3.Connection`` whose transaction is owned by the
        caller (e.g. ``KnowledgeCore._init_schema``).
    """

    db.executescript(_COACHING_SCHEMA_SQL)
    apply_additive_columns(db)
