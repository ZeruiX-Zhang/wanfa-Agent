from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from rag_core.observability.events import record_agent_trace
from rag_core.observability.tracing import new_trace_id


def record_agent_run(
    selected_workflow: str,
    selected_tools: list[str],
    tool_args: dict[str, Any],
    tool_result_summary: str,
    tool_latency_ms: float,
    final_answer: str,
    user_input: str | None = None,
    tool_result: dict[str, Any] | None = None,
    steps: list[dict[str, Any]] | None = None,
    finished_at: str | None = None,
) -> str:
    trace_id = new_trace_id()
    selected_tool = selected_tools[0] if selected_tools else None
    record_agent_trace(
        {
            "run_id": trace_id,
            "trace_id": trace_id,
            "user_input": user_input,
            "selected_workflow": selected_workflow,
            "selected_tool": selected_tool,
            "selected_tools": selected_tools,
            "steps": steps or [],
            "tool_args": tool_args,
            "tool_result": tool_result or {},
            "tool_result_summary": tool_result_summary,
            "tool_latency_ms": tool_latency_ms,
            "latency_ms": tool_latency_ms,
            "final_answer": final_answer,
            "finished_at": finished_at or datetime.now(timezone.utc).isoformat(),
        }
    )
    return trace_id

