"""Context Anchor — cognitive offloading for the human operator.

A Context Anchor is a persistent, versioned 3-sentence summary that keeps
the human aligned with their own goals across sessions. It records:

1. **goal** — the current ultimate objective
2. **logic_flow** — what has been validated so far
3. **current_blocker** — the single biggest obstacle right now

Design principles:
- Only the human can write/update an anchor (Agent can only *suggest*)
- Every update archives the previous version (full history)
- `/ask` and `/diagnose` auto-read the latest anchor as implicit task_contract
- The anchor is NOT chat history — it's a deliberate, human-maintained compass
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any

from .knowledge_core import get_core, _utc_now_iso, _new_id


@dataclass
class ContextAnchor:
    id: str
    tenant_id: str
    goal: str
    logic_flow: str
    current_blocker: str
    version: int
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "goal": self.goal,
            "logic_flow": self.logic_flow,
            "current_blocker": self.current_blocker,
            "version": self.version,
            "created_at": self.created_at,
        }

    def to_task_contract(self) -> dict[str, Any]:
        """Convert anchor to a task_contract compatible dict for ask()."""
        return {
            "goal": self.goal,
            "constraints": [self.current_blocker] if self.current_blocker else [],
            "acceptance_criteria": [],
        }


def ensure_anchor_schema(db: sqlite3.Connection) -> None:
    db.execute("""
        create table if not exists context_anchors (
            id text primary key,
            tenant_id text not null,
            goal text not null,
            logic_flow text not null default '',
            current_blocker text not null default '',
            version integer not null default 1,
            created_at text not null
        )
    """)
    db.execute("""
        create index if not exists idx_anchors_tenant_version
        on context_anchors(tenant_id, version desc)
    """)


def get_current_anchor(tenant_id: str) -> ContextAnchor | None:
    """Get the latest (highest version) anchor for a tenant."""
    core = get_core()
    with core._lock, core._connect() as db:
        ensure_anchor_schema(db)
        row = db.execute(
            "select * from context_anchors where tenant_id = ? order by version desc limit 1",
            (tenant_id,),
        ).fetchone()
    if row is None:
        return None
    return ContextAnchor(
        id=row["id"],
        tenant_id=row["tenant_id"],
        goal=row["goal"],
        logic_flow=row["logic_flow"],
        current_blocker=row["current_blocker"],
        version=int(row["version"]),
        created_at=row["created_at"],
    )


def update_anchor(
    *,
    tenant_id: str,
    goal: str,
    logic_flow: str = "",
    current_blocker: str = "",
) -> ContextAnchor:
    """Create a new version of the anchor (old versions are preserved)."""
    core = get_core()
    with core._lock, core._connect() as db:
        ensure_anchor_schema(db)
        # Get current max version
        row = db.execute(
            "select max(version) as max_v from context_anchors where tenant_id = ?",
            (tenant_id,),
        ).fetchone()
        next_version = (int(row["max_v"]) + 1) if row and row["max_v"] else 1

        anchor = ContextAnchor(
            id=_new_id("anc"),
            tenant_id=tenant_id,
            goal=goal.strip(),
            logic_flow=logic_flow.strip(),
            current_blocker=current_blocker.strip(),
            version=next_version,
            created_at=_utc_now_iso(),
        )
        db.execute(
            """insert into context_anchors(id, tenant_id, goal, logic_flow, current_blocker, version, created_at)
               values(?, ?, ?, ?, ?, ?, ?)""",
            (anchor.id, anchor.tenant_id, anchor.goal, anchor.logic_flow,
             anchor.current_blocker, anchor.version, anchor.created_at),
        )
    return anchor


def get_anchor_history(tenant_id: str, limit: int = 20) -> list[ContextAnchor]:
    """Get version history of anchors (newest first)."""
    core = get_core()
    with core._lock, core._connect() as db:
        ensure_anchor_schema(db)
        rows = db.execute(
            "select * from context_anchors where tenant_id = ? order by version desc limit ?",
            (tenant_id, limit),
        ).fetchall()
    return [
        ContextAnchor(
            id=row["id"],
            tenant_id=row["tenant_id"],
            goal=row["goal"],
            logic_flow=row["logic_flow"],
            current_blocker=row["current_blocker"],
            version=int(row["version"]),
            created_at=row["created_at"],
        )
        for row in rows
    ]
