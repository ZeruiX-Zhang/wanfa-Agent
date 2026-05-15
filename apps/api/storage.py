from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

from .schemas import (
    ApprovalRequest,
    AuditEvent,
    PendingKnowledgeRecord,
    ToolCallLog,
    new_id,
    utc_now,
)


def default_storage_path() -> Path:
    configured = os.getenv("REALITY_OS_API_STORAGE")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parent / ".runtime" / "reality_os.sqlite3"


class RealityStorage:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else default_storage_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_schema(self) -> None:
        with self._connect() as db:
            db.execute(
                """
                create table if not exists records (
                  kind text not null,
                  id text not null,
                  tenant_id text not null,
                  payload text not null,
                  created_at text not null,
                  updated_at text not null,
                  primary key (kind, id)
                )
                """
            )

    def _upsert(self, kind: str, item_id: str, tenant_id: str, payload: str, created_at: str | None = None) -> None:
        timestamp = utc_now().isoformat()
        with self._connect() as db:
            db.execute(
                """
                insert into records(kind, id, tenant_id, payload, created_at, updated_at)
                values (?, ?, ?, ?, ?, ?)
                on conflict(kind, id) do update set
                  tenant_id = excluded.tenant_id,
                  payload = excluded.payload,
                  updated_at = excluded.updated_at
                """,
                (kind, item_id, tenant_id, payload, created_at or timestamp, timestamp),
            )

    def save_pending(self, record: PendingKnowledgeRecord) -> PendingKnowledgeRecord:
        self._upsert("pending_knowledge", record.id, record.tenant_id, record.model_dump_json())
        self.audit(
            tenant_id=record.tenant_id,
            actor=record.created_by,
            event_type="pending_knowledge.created",
            action=f"create pending knowledge {record.id}",
        )
        return record

    def list_pending(self, tenant_id: str | None = None) -> list[PendingKnowledgeRecord]:
        return [
            PendingKnowledgeRecord.model_validate_json(row["payload"])
            for row in self._list_rows("pending_knowledge", tenant_id)
        ]

    def get_pending(self, item_id: str, tenant_id: str | None = None) -> PendingKnowledgeRecord | None:
        row = self._get_row("pending_knowledge", item_id, tenant_id)
        return PendingKnowledgeRecord.model_validate_json(row["payload"]) if row else None

    def update_pending(self, record: PendingKnowledgeRecord) -> PendingKnowledgeRecord:
        self._upsert("pending_knowledge", record.id, record.tenant_id, record.model_dump_json())
        self.audit(
            tenant_id=record.tenant_id,
            actor=record.created_by,
            event_type="pending_knowledge.updated",
            action=f"update pending knowledge {record.id}",
        )
        return record

    def save_approval(self, approval: ApprovalRequest) -> ApprovalRequest:
        self._upsert("approval", approval.id, approval.tenant_id, approval.model_dump_json())
        self.audit(
            tenant_id=approval.tenant_id,
            actor="supervisor",
            event_type="approval.recorded",
            action=approval.action,
            risk=approval.risk,
        )
        return approval

    def list_approvals(self, tenant_id: str | None = None) -> list[ApprovalRequest]:
        return [ApprovalRequest.model_validate_json(row["payload"]) for row in self._list_rows("approval", tenant_id)]

    def save_tool_log(self, tool_call: ToolCallLog) -> ToolCallLog:
        self._upsert("tool_call", tool_call.id, tool_call.tenant_id, tool_call.model_dump_json())
        self.audit(
            tenant_id=tool_call.tenant_id,
            actor="tool-gateway",
            event_type="tool_call.recorded",
            action=tool_call.tool_name,
            risk=tool_call.risk,
        )
        return tool_call

    def list_tool_logs(self, tenant_id: str | None = None) -> list[ToolCallLog]:
        return [ToolCallLog.model_validate_json(row["payload"]) for row in self._list_rows("tool_call", tenant_id)]

    def audit(
        self,
        *,
        tenant_id: str,
        actor: str,
        event_type: str,
        action: str,
        risk: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            id=new_id("audit"),
            tenant_id=tenant_id,
            actor=actor,
            event_type=event_type,
            action=action,
            risk=risk,
            metadata=metadata or {},
            created_at=utc_now(),
        )
        self._upsert("audit", event.id, tenant_id, event.model_dump_json())
        return event

    def list_audit(self, tenant_id: str | None = None) -> list[AuditEvent]:
        return [AuditEvent.model_validate_json(row["payload"]) for row in self._list_rows("audit", tenant_id)]

    def _list_rows(self, kind: str, tenant_id: str | None = None) -> list[sqlite3.Row]:
        query = "select payload from records where kind = ?"
        params: list[str] = [kind]
        if tenant_id:
            query += " and tenant_id = ?"
            params.append(tenant_id)
        query += " order by created_at asc"
        with self._connect() as db:
            return list(db.execute(query, params))

    def _get_row(self, kind: str, item_id: str, tenant_id: str | None = None) -> sqlite3.Row | None:
        query = "select payload from records where kind = ? and id = ?"
        params: list[str] = [kind, item_id]
        if tenant_id:
            query += " and tenant_id = ?"
            params.append(tenant_id)
        with self._connect() as db:
            return db.execute(query, params).fetchone()


_STORAGE: RealityStorage | None = None


def get_storage() -> RealityStorage:
    global _STORAGE
    if _STORAGE is None:
        _STORAGE = RealityStorage()
    return _STORAGE

