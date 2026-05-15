"""System Rules — self-modifying rule engine for Reality OS.

When the user corrects the Agent (rejects a decision anchor, overrides an
acceptance check, or manually adds a rule), the system extracts a reusable
rule and persists it. Active rules are injected into future ask/diagnose
calls to prevent repeating the same mistakes.

Design principles:
- Rules are proposed automatically but only activated by human confirmation
- Each rule has a trigger_count (how often it influenced output)
- Max 50 active rules per tenant; low-frequency rules auto-archive
- Rules are deterministic conditions, not prompt fragments
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any, Literal

from .knowledge_core import get_core, _utc_now_iso, _new_id
from .security_scanner import flags_for_text


RuleStatus = Literal["proposed", "active", "archived", "rejected"]


@dataclass
class SystemRule:
    id: str
    tenant_id: str
    rule_text: str
    source_event: str  # e.g. "anchor_reject", "manual", "review_lesson"
    status: RuleStatus
    trigger_count: int
    created_at: str
    security_flags: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "rule_text": self.rule_text,
            "source_event": self.source_event,
            "status": self.status,
            "trigger_count": self.trigger_count,
            "created_at": self.created_at,
            "security_flags": list(self.security_flags or []),
        }


def ensure_rules_schema(db: sqlite3.Connection) -> None:
    db.execute("""
        create table if not exists system_rules (
            id text primary key,
            tenant_id text not null,
            rule_text text not null,
            source_event text not null default 'manual',
            status text not null default 'proposed',
            trigger_count integer not null default 0,
            created_at text not null,
            security_flags_json text not null default '[]'
        )
    """)
    existing_cols = {row[1] for row in db.execute("pragma table_info(system_rules)").fetchall()}
    if "security_flags_json" not in existing_cols:
        db.execute("alter table system_rules add column security_flags_json text not null default '[]'")
    db.execute("""
        create index if not exists idx_rules_tenant_status
        on system_rules(tenant_id, status)
    """)


def get_active_rules(tenant_id: str) -> list[SystemRule]:
    """Get all active rules for a tenant (used by ask/diagnose)."""
    core = get_core()
    with core._lock, core._connect() as db:
        ensure_rules_schema(db)
        rows = db.execute(
            "select * from system_rules where tenant_id = ? and status = 'active' order by trigger_count desc limit 50",
            (tenant_id,),
        ).fetchall()
    return [_row_to_rule(row) for row in rows]


def list_rules(tenant_id: str, *, include_all: bool = False, limit: int = 50) -> list[SystemRule]:
    """List rules (active + proposed by default, or all if include_all)."""
    core = get_core()
    with core._lock, core._connect() as db:
        ensure_rules_schema(db)
        if include_all:
            rows = db.execute(
                "select * from system_rules where tenant_id = ? order by created_at desc limit ?",
                (tenant_id, limit),
            ).fetchall()
        else:
            rows = db.execute(
                "select * from system_rules where tenant_id = ? and status in ('active', 'proposed') order by created_at desc limit ?",
                (tenant_id, limit),
            ).fetchall()
    return [_row_to_rule(row) for row in rows]


def add_rule(
    *,
    tenant_id: str,
    rule_text: str,
    source_event: str = "manual",
    status: RuleStatus = "proposed",
) -> SystemRule:
    """Add a new rule (proposed by default, manual rules can be active immediately)."""
    core = get_core()
    security_flags = flags_for_text(rule_text, source=f"system_rule:{source_event}")
    if source_event != "manual" and status == "active":
        status = "proposed"
    if security_flags:
        status = "proposed"
    rule = SystemRule(
        id=_new_id("rul"),
        tenant_id=tenant_id,
        rule_text=rule_text.strip(),
        source_event=source_event,
        status=status,
        trigger_count=0,
        created_at=_utc_now_iso(),
        security_flags=security_flags,
    )
    with core._lock, core._connect() as db:
        ensure_rules_schema(db)
        db.execute(
            """insert into system_rules(id, tenant_id, rule_text, source_event, status, trigger_count, created_at, security_flags_json)
               values(?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                rule.id,
                rule.tenant_id,
                rule.rule_text,
                rule.source_event,
                rule.status,
                rule.trigger_count,
                rule.created_at,
                _json_flags(security_flags),
            ),
        )
        # Auto-archive if over 50 active rules
        _enforce_rule_limit(db, tenant_id)
    return rule


def update_rule(
    *,
    tenant_id: str,
    rule_id: str,
    status: RuleStatus | None = None,
    rule_text: str | None = None,
) -> SystemRule | None:
    """Update a rule's status or text."""
    core = get_core()
    with core._lock, core._connect() as db:
        ensure_rules_schema(db)
        row = db.execute(
            "select * from system_rules where id = ? and tenant_id = ?",
            (rule_id, tenant_id),
        ).fetchone()
        if row is None:
            return None
        updates: list[str] = []
        params: list[Any] = []
        new_status = status
        new_flags: list[str] | None = None
        if rule_text is not None:
            new_flags = flags_for_text(rule_text, source=f"system_rule:{row['source_event']}")
            if new_flags:
                new_status = "proposed"
        if new_status is not None:
            existing_flags = _parse_flags(row["security_flags_json"]) if "security_flags_json" in row.keys() else []
            if existing_flags and new_status == "active":
                new_status = "proposed"
            updates.append("status = ?")
            params.append(new_status)
        if rule_text is not None:
            updates.append("rule_text = ?")
            params.append(rule_text.strip())
            updates.append("security_flags_json = ?")
            params.append(_json_flags(new_flags or []))
        if updates:
            params.extend([rule_id, tenant_id])
            db.execute(
                f"update system_rules set {', '.join(updates)} where id = ? and tenant_id = ?",
                params,
            )
        updated_row = db.execute(
            "select * from system_rules where id = ? and tenant_id = ?",
            (rule_id, tenant_id),
        ).fetchone()
    return _row_to_rule(updated_row) if updated_row else None


def increment_trigger(tenant_id: str, rule_id: str) -> None:
    """Increment the trigger count for a rule (called when rule influences output)."""
    core = get_core()
    with core._lock, core._connect() as db:
        ensure_rules_schema(db)
        db.execute(
            "update system_rules set trigger_count = trigger_count + 1 where id = ? and tenant_id = ?",
            (rule_id, tenant_id),
        )


def auto_extract_rule(
    *,
    tenant_id: str,
    anchor_content: str,
    user_correction: str,
    language: str,
) -> SystemRule:
    """Auto-extract a rule from a user correction (e.g. rejecting a decision anchor)."""
    if language == "zh-CN":
        rule_text = f"当 Agent 提议「{anchor_content[:50]}」时，正确做法是「{user_correction[:80]}」"
    else:
        rule_text = f"When Agent proposes '{anchor_content[:50]}', the correct approach is '{user_correction[:80]}'"
    return add_rule(
        tenant_id=tenant_id,
        rule_text=rule_text,
        source_event="anchor_reject",
        status="proposed",
    )


def _enforce_rule_limit(db: sqlite3.Connection, tenant_id: str) -> None:
    """If more than 50 active rules, archive the least-triggered ones."""
    count_row = db.execute(
        "select count(*) as c from system_rules where tenant_id = ? and status = 'active'",
        (tenant_id,),
    ).fetchone()
    if count_row and int(count_row["c"]) > 50:
        # Archive the 10 least-triggered active rules
        db.execute(
            """update system_rules set status = 'archived'
               where id in (
                   select id from system_rules
                   where tenant_id = ? and status = 'active'
                   order by trigger_count asc
                   limit 10
               )""",
            (tenant_id,),
        )


def _row_to_rule(row: sqlite3.Row) -> SystemRule:
    return SystemRule(
        id=row["id"],
        tenant_id=row["tenant_id"],
        rule_text=row["rule_text"],
        source_event=row["source_event"],
        status=row["status"],  # type: ignore[arg-type]
        trigger_count=int(row["trigger_count"]),
        created_at=row["created_at"],
        security_flags=_parse_flags(row["security_flags_json"]) if "security_flags_json" in row.keys() else [],
    )


def _json_flags(flags: list[str]) -> str:
    import json

    return json.dumps(flags, ensure_ascii=False)


def _parse_flags(raw: str) -> list[str]:
    import json

    try:
        value = json.loads(raw or "[]")
    except Exception:
        return []
    return [str(item) for item in value if isinstance(item, str)]
