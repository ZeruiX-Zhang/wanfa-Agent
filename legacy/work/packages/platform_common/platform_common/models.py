from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


RunMode = Literal["auto", "knowledge", "analysis", "hybrid"]
RunStatus = Literal["completed", "waiting_approval", "rejected", "failed", "error"]
GuardrailStage = Literal["request_precheck", "retrieval_precheck", "tool_precheck", "output_postcheck"]
GuardrailOutcome = Literal["allow", "block", "review"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AuthContext(BaseModel):
    user_id: str = Field(default="anonymous")
    tenant_id: str = Field(default="default")
    roles: list[str] = Field(default_factory=lambda: ["reader"])


class GuardrailDecision(BaseModel):
    stage: GuardrailStage
    decision: GuardrailOutcome
    reason: str
    policy_ids: list[str] = Field(default_factory=list)
    redactions: list[str] = Field(default_factory=list)


class SourceRef(BaseModel):
    title: str = Field(default="")
    snippet: str | None = Field(default=None)
    url: str | None = Field(default=None)
    document_id: str | None = Field(default=None)
    chunk_id: str | None = Field(default=None)
    score: float | None = Field(default=None)
    domain: str | None = Field(default=None)


class DataArtifact(BaseModel):
    kind: str
    name: str
    url: str | None = None
    path: str | None = None
    preview: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PendingAction(BaseModel):
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    reason: str


class RunStep(BaseModel):
    name: str
    status: str
    args: dict[str, Any] = Field(default_factory=dict)
    result: Any | None = None
    error: str | None = None
    started_at: str = Field(default_factory=utc_now)
    ended_at: str = Field(default_factory=utc_now)


class UnifiedRunRequest(BaseModel):
    user_input: str = Field(min_length=1, max_length=4000)
    scenario: str = Field(default="auto")
    mode: RunMode = Field(default="auto")
    top_k: int = Field(default=5, ge=1, le=20)
    include_trace: bool = Field(default=True)
    max_steps: int = Field(default=6, ge=1, le=20)


class RagQueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    domain: str = Field(default="auto")
    top_k: int = Field(default=5, ge=1, le=20)
    include_trace: bool = Field(default=True)


class RagQueryResponse(BaseModel):
    run_id: str
    trace_id: str
    answer: str
    sources: list[SourceRef] = Field(default_factory=list)
    trace_url: str | None = None
    safety: dict[str, Any] = Field(default_factory=dict)
    debug: dict[str, Any] = Field(default_factory=dict)


class AnalysisQueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    include_trace: bool = Field(default=True)


class ApprovalRequest(BaseModel):
    approved: bool = Field(default=True)
    comment: str | None = Field(default=None, max_length=1000)


class ApprovalResponse(BaseModel):
    run_id: str
    status: RunStatus
    approval_executed: bool
    pending_action: PendingAction | None = None
    final_answer: str
    trace_url: str | None = None
    ticket_id: str | None = None


class UnifiedRunResponse(BaseModel):
    run_id: str
    trace_id: str
    status: RunStatus
    scenario: str
    mode: RunMode
    final_answer: str
    answer_type: str | None = None
    confidence: float | None = None
    sources: list[SourceRef] = Field(default_factory=list)
    data_artifacts: list[DataArtifact] = Field(default_factory=list)
    pending_action: PendingAction | None = None
    trace_url: str | None = None
    safety: dict[str, Any] = Field(default_factory=dict)
    tool_steps: list[RunStep] = Field(default_factory=list)
    qa_plan: dict[str, Any] = Field(default_factory=dict)
    evidence_report: dict[str, Any] = Field(default_factory=dict)
    verification: dict[str, Any] = Field(default_factory=dict)


class UnifiedRunTrace(BaseModel):
    run_id: str
    trace_id: str
    user_input: str
    scenario: str
    mode: RunMode
    status: RunStatus
    final_answer: str
    answer_type: str | None = None
    confidence: float | None = None
    auth_context: AuthContext
    sources: list[SourceRef] = Field(default_factory=list)
    data_artifacts: list[DataArtifact] = Field(default_factory=list)
    pending_action: PendingAction | None = None
    tool_steps: list[RunStep] = Field(default_factory=list)
    guardrails: list[GuardrailDecision] = Field(default_factory=list)
    safety: dict[str, Any] = Field(default_factory=dict)
    qa_plan: dict[str, Any] = Field(default_factory=dict)
    evidence_report: dict[str, Any] = Field(default_factory=dict)
    verification: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    trace_store: str
