from __future__ import annotations

from typing import Any

from app.observability.tracing import write_trace


def record_rag_trace(payload: dict[str, Any]) -> None:
    write_trace("rag", payload, trace_id=str(payload.get("trace_id")))


def record_agent_trace(payload: dict[str, Any]) -> None:
    write_trace("agent", payload, trace_id=str(payload.get("trace_id")))

