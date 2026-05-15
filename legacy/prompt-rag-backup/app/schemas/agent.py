from __future__ import annotations

from pydantic import BaseModel, Field


class AgentRunRequest(BaseModel):
    user_input: str = Field(min_length=1)
    max_steps: int = Field(default=4, ge=1, le=8)


class AgentRunResponse(BaseModel):
    success: bool
    run_id: str
    final_answer: str
    tools_used: list[str]
    latency_ms: float
    trace_id: str


class AgentTraceResponse(BaseModel):
    success: bool
    run: dict[str, object]
    trace_id: str
