"""Append-only execution tracing for Reality OS.

Trace records intentionally store hashes and small metadata, not raw user
content or API keys. The schema lives beside the knowledge core SQLite DB so
the local app can recover and inspect runs without introducing a new service.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def stable_hash(value: Any) -> str:
    """Return a stable SHA-256 hash for traceable but redacted values."""

    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple)):
        text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    else:
        text = str(value)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


_REDACTED = "[redacted]"
_SENSITIVE_KEY_RE = re.compile(
    r"(api[_-]?key|apikey|token|secret|password|authorization|cookie|prompt|content|input|output|body|question)",
    re.I,
)
_SECRET_VALUE_RE = re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b")
_SENSITIVE_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(api[_\s-]?key|apikey|token|secret|password|authorization|cookie|prompt|content|input|output|body|question)"
    r"\s*[:=]\s*[^;\n,]+"
)


def _redact_text(value: str) -> str:
    text = _SECRET_VALUE_RE.sub(_REDACTED, value)
    text = _SENSITIVE_ASSIGNMENT_RE.sub(lambda match: f"{match.group(1)}={_REDACTED}", text)
    return text[:500]


def _safe_metadata_value(value: Any, *, key: str | None = None, depth: int = 0) -> Any:
    if key and _SENSITIVE_KEY_RE.search(key):
        return _REDACTED
    if depth >= 6:
        return str(type(value).__name__)
    if isinstance(value, dict):
        return {
            str(child_key): _safe_metadata_value(child_value, key=str(child_key), depth=depth + 1)
            for child_key, child_value in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_safe_metadata_value(item, depth=depth + 1) for item in value[:50]]
    if isinstance(value, str):
        return _redact_text(value)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return _redact_text(str(value))


def _safe_error(error: str | None) -> str | None:
    if error is None:
        return None
    return _redact_text(str(error))


def _json(value: dict[str, Any] | None) -> str:
    safe = _safe_metadata_value(value or {})
    return json.dumps(safe, ensure_ascii=False, sort_keys=True, default=str)


def _connect() -> sqlite3.Connection:
    from .knowledge_core import get_core

    core = get_core()
    conn = sqlite3.connect(core.path)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_trace_schema(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        create table if not exists agent_runs (
          run_id text primary key,
          trace_id text not null,
          tenant_id text not null,
          user_id text not null,
          entrypoint text not null,
          status text not null,
          input_hash text,
          output_hash text,
          started_at text not null,
          ended_at text,
          error text,
          metadata_json text not null default '{}'
        );

        create index if not exists idx_agent_runs_tenant_started
        on agent_runs(tenant_id, started_at);

        create table if not exists agent_steps (
          step_id text primary key,
          run_id text not null,
          step_index integer not null,
          step_type text not null,
          status text not null,
          input_hash text,
          output_hash text,
          started_at text not null,
          ended_at text,
          error text,
          cost_estimate real,
          model_slot text,
          verifier_used integer not null default 0,
          metadata_json text not null default '{}'
        );

        create index if not exists idx_agent_steps_run
        on agent_steps(run_id, step_index);

        create table if not exists model_calls (
          id text primary key,
          run_id text,
          step_id text,
          slot text not null,
          provider_id text,
          model_name text,
          status text not null,
          started_at text not null,
          ended_at text,
          latency_ms integer,
          input_hash text,
          output_hash text,
          error_type text,
          error text,
          retry_count integer not null default 0,
          fallback_from text,
          fallback_used integer not null default 0,
          cost_estimate real,
          timeout_seconds real,
          metadata_json text not null default '{}'
        );

        create index if not exists idx_model_calls_run
        on model_calls(run_id, started_at);

        create table if not exists tool_calls (
          id text primary key,
          run_id text,
          step_id text,
          tool_name text not null,
          status text not null,
          input_hash text,
          output_hash text,
          started_at text not null,
          ended_at text,
          error text,
          risk text,
          supervisor_decision text,
          metadata_json text not null default '{}'
        );

        create index if not exists idx_tool_calls_run
        on tool_calls(run_id, started_at);

        create table if not exists acceptance_checks (
          id text primary key,
          run_id text,
          step_id text,
          verdict text not null,
          verifier_used integer not null default 0,
          status text not null,
          input_hash text,
          output_hash text,
          started_at text not null,
          ended_at text,
          error text,
          metadata_json text not null default '{}'
        );

        create index if not exists idx_acceptance_checks_run
        on acceptance_checks(run_id, started_at);

        create table if not exists audit_results (
          id text primary key,
          run_id text,
          passed integer not null,
          score real not null,
          source text not null,
          output_type text not null,
          input_hash text,
          output_hash text,
          started_at text not null,
          ended_at text,
          metadata_json text not null default '{}'
        );

        create index if not exists idx_audit_results_run
        on audit_results(run_id, started_at);
        """
    )


def start_run(
    *,
    tenant_id: str,
    user_id: str,
    entrypoint: str,
    input_value: Any = None,
    metadata: dict[str, Any] | None = None,
) -> str:
    run_id = _id("run")
    now = _now()
    with _connect() as db:
        ensure_trace_schema(db)
        db.execute(
            """
            insert into agent_runs(
              run_id, trace_id, tenant_id, user_id, entrypoint, status,
              input_hash, started_at, metadata_json
            ) values(?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                run_id,
                tenant_id,
                user_id,
                entrypoint,
                "running",
                stable_hash(input_value),
                now,
                _json(metadata),
            ),
        )
    return run_id


def finish_run(
    run_id: str | None,
    *,
    status: str = "completed",
    output_value: Any = None,
    error: str | None = None,
) -> None:
    if not run_id:
        return
    with _connect() as db:
        ensure_trace_schema(db)
        db.execute(
            """
            update agent_runs
            set status = ?, output_hash = ?, ended_at = ?, error = ?
            where run_id = ?
            """,
            (status, stable_hash(output_value), _now(), _safe_error(error), run_id),
        )


def record_step(
    *,
    run_id: str | None,
    step_type: str,
    status: str = "completed",
    input_value: Any = None,
    output_value: Any = None,
    error: str | None = None,
    cost_estimate: float | None = None,
    model_slot: str | None = None,
    verifier_used: bool = False,
    metadata: dict[str, Any] | None = None,
) -> str | None:
    if not run_id:
        return None
    started = _now()
    step_id = _id("step")
    with _connect() as db:
        ensure_trace_schema(db)
        row = db.execute(
            "select coalesce(max(step_index), 0) + 1 as next_index from agent_steps where run_id = ?",
            (run_id,),
        ).fetchone()
        step_index = int(row["next_index"] if row else 1)
        db.execute(
            """
            insert into agent_steps(
              step_id, run_id, step_index, step_type, status, input_hash,
              output_hash, started_at, ended_at, error, cost_estimate,
              model_slot, verifier_used, metadata_json
            ) values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                step_id,
                run_id,
                step_index,
                step_type,
                status,
                stable_hash(input_value),
                stable_hash(output_value),
                started,
                _now(),
                _safe_error(error),
                cost_estimate,
                model_slot,
                1 if verifier_used else 0,
                _json(metadata),
            ),
        )
    return step_id


def record_model_call(
    *,
    run_id: str | None,
    step_id: str | None,
    slot: str,
    provider_id: str | None,
    model_name: str | None,
    status: str,
    started_at: str,
    ended_at: str | None,
    latency_ms: int | None,
    input_value: Any = None,
    output_value: Any = None,
    error_type: str | None = None,
    error: str | None = None,
    retry_count: int = 0,
    fallback_from: str | None = None,
    fallback_used: bool = False,
    cost_estimate: float | None = None,
    timeout_seconds: float | None = None,
    metadata: dict[str, Any] | None = None,
) -> str:
    call_id = _id("mcall")
    with _connect() as db:
        ensure_trace_schema(db)
        db.execute(
            """
            insert into model_calls(
              id, run_id, step_id, slot, provider_id, model_name, status,
              started_at, ended_at, latency_ms, input_hash, output_hash,
              error_type, error, retry_count, fallback_from, fallback_used,
              cost_estimate, timeout_seconds, metadata_json
            ) values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                call_id,
                run_id,
                step_id,
                slot,
                provider_id,
                model_name,
                status,
                started_at,
                ended_at,
                latency_ms,
                stable_hash(input_value),
                stable_hash(output_value),
                error_type,
                _safe_error(error),
                retry_count,
                fallback_from,
                1 if fallback_used else 0,
                cost_estimate,
                timeout_seconds,
                _json(metadata),
            ),
        )
    return call_id


def record_acceptance_check(
    *,
    run_id: str | None,
    step_id: str | None,
    verdict: str,
    verifier_used: bool,
    status: str = "completed",
    input_value: Any = None,
    output_value: Any = None,
    error: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> str | None:
    if not run_id:
        return None
    check_id = _id("acc")
    now = _now()
    with _connect() as db:
        ensure_trace_schema(db)
        db.execute(
            """
            insert into acceptance_checks(
              id, run_id, step_id, verdict, verifier_used, status,
              input_hash, output_hash, started_at, ended_at, error, metadata_json
            ) values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                check_id,
                run_id,
                step_id,
                verdict,
                1 if verifier_used else 0,
                status,
                stable_hash(input_value),
                stable_hash(output_value),
                now,
                _now(),
                _safe_error(error),
                _json(metadata),
            ),
        )
    return check_id


def record_audit_result(
    *,
    run_id: str | None,
    passed: bool,
    score: float,
    source: str,
    output_type: str,
    input_value: Any = None,
    output_value: Any = None,
    metadata: dict[str, Any] | None = None,
) -> str | None:
    if not run_id:
        return None
    audit_id = _id("ares")
    now = _now()
    with _connect() as db:
        ensure_trace_schema(db)
        db.execute(
            """
            insert into audit_results(
              id, run_id, passed, score, source, output_type, input_hash,
              output_hash, started_at, ended_at, metadata_json
            ) values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                audit_id,
                run_id,
                1 if passed else 0,
                score,
                source,
                output_type,
                stable_hash(input_value),
                stable_hash(output_value),
                now,
                _now(),
                _json(metadata),
            ),
        )
    return audit_id


def get_run(run_id: str) -> dict[str, Any] | None:
    with _connect() as db:
        ensure_trace_schema(db)
        run = db.execute("select * from agent_runs where run_id = ?", (run_id,)).fetchone()
        if run is None:
            return None
        steps = db.execute(
            "select * from agent_steps where run_id = ? order by step_index asc",
            (run_id,),
        ).fetchall()
        model_calls = db.execute(
            "select * from model_calls where run_id = ? order by started_at asc",
            (run_id,),
        ).fetchall()
        acceptance = db.execute(
            "select * from acceptance_checks where run_id = ? order by started_at asc",
            (run_id,),
        ).fetchall()
        audit_results = db.execute(
            "select * from audit_results where run_id = ? order by started_at asc",
            (run_id,),
        ).fetchall()

    return {
        "run": _row(run),
        "steps": [_row(row) for row in steps],
        "model_calls": [_row(row) for row in model_calls],
        "acceptance_checks": [_row(row) for row in acceptance],
        "audit_results": [_row(row) for row in audit_results],
    }


def _row(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    if "error" in result:
        result["error"] = _safe_error(result["error"])
    for key in ("metadata_json",):
        if key in result:
            try:
                result[key.removesuffix("_json")] = _safe_metadata_value(json.loads(result.pop(key) or "{}"))
            except json.JSONDecodeError:
                result[key.removesuffix("_json")] = {}
    return result
