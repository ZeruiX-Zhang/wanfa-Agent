from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


AdapterMode = Literal["mock-safe", "read-only", "pending-review", "dry-run", "blocked"]
ReviewStatus = Literal["pending_review", "approved", "rejected", "undone"]
RiskLevel = Literal["low", "medium", "high"]
TrustLevel = Literal["trusted", "internal", "untrusted"]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


class AdapterMetadata(BaseModel):
    adapter: str
    source_system: str
    mode: AdapterMode = "mock-safe"
    read_only: bool = True
    external_content_default: TrustLevel = "untrusted"
    generated_at: datetime = Field(default_factory=utc_now)


class HealthResponse(BaseModel):
    service: str
    status: Literal["ok"]
    version: str
    api_key_policy: str
    tool_execution: Literal["disabled", "dry-run"]
    adapters: dict[str, AdapterMode]
    auth_required: bool = False
    tenant_required_in_production: bool = True


class SourceRecord(BaseModel):
    id: str
    title: str
    origin: str
    uri: str | None = None
    summary: str
    tags: list[str] = Field(default_factory=list)
    external: bool = True
    trust_level: TrustLevel = "untrusted"
    status: Literal["read_only"] = "read_only"


class SourceListResponse(BaseModel):
    metadata: AdapterMetadata
    sources: list[SourceRecord]


class EvidenceRecord(BaseModel):
    id: str
    claim: str
    source_id: str
    quote: str
    rationale: str
    external: bool = True
    trust_level: TrustLevel = "untrusted"
    status: Literal["read_only"] = "read_only"


class EvidenceLedgerResponse(BaseModel):
    metadata: AdapterMetadata
    evidence: list[EvidenceRecord]


class IntelligenceObject(BaseModel):
    id: str
    title: str
    object_type: str
    summary: str
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    external: bool = True
    trust_level: TrustLevel = "untrusted"
    status: Literal["read_only"] = "read_only"


class IntelligenceObjectListResponse(BaseModel):
    metadata: AdapterMetadata
    objects: list[IntelligenceObject]


class SettingsResponse(BaseModel):
    metadata: AdapterMetadata
    settings: dict[str, Any]


class ClarificationRequest(BaseModel):
    problem: str = Field(min_length=1)
    context: str | None = None
    constraints: list[str] = Field(default_factory=list)


class ClarificationQuestion(BaseModel):
    id: str
    question: str
    reason: str
    required: bool = True


class ClarificationResponse(BaseModel):
    clarified_problem_id: str
    original_problem: str
    assumptions: list[str]
    questions: list[ClarificationQuestion]
    status: Literal["needs_clarification", "ready_for_retrieval"]
    metadata: AdapterMetadata


class CaptureRequest(BaseModel):
    content: str = Field(min_length=1)
    source: str = "manual"
    uri: str | None = None
    tags: list[str] = Field(default_factory=list)
    created_by: str = "local-user"


class CaptureResponse(BaseModel):
    capture_id: str
    status: ReviewStatus
    review_required: bool
    promoted_to_formal_knowledge: bool = False
    external: bool = True
    trust_level: TrustLevel = "untrusted"
    created_at: datetime = Field(default_factory=utc_now)


class KnowledgeSummaryResponse(BaseModel):
    metadata: AdapterMetadata
    captures_pending_review: int
    pending_knowledge_writes: int
    formal_knowledge_writes: int
    policy: str


class RagQueryRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=3, ge=1, le=10)
    include_debug: bool = True


class RagHit(BaseModel):
    source_id: str
    title: str
    snippet: str
    score: float = Field(ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)
    external: bool = True
    trust_level: TrustLevel = "untrusted"


class RagQueryResponse(BaseModel):
    metadata: AdapterMetadata
    query: str
    hits: list[RagHit]
    debug: dict[str, Any]


class RagDebugResponse(BaseModel):
    metadata: AdapterMetadata
    pipeline: str
    original_pipeline_modified: bool = False
    notes: list[str]


class VerificationRequest(BaseModel):
    claim: str = Field(min_length=1)
    evidence_ids: list[str] = Field(default_factory=list)


class VerificationResponse(BaseModel):
    metadata: AdapterMetadata
    claim: str
    verdict: Literal["supported", "unsupported", "insufficient_evidence"]
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_ids: list[str]
    risks: list[str]
    insufficient_evidence: bool


class EvalSummaryResponse(BaseModel):
    metadata: AdapterMetadata
    suites: list[dict[str, Any]]
    last_run_status: Literal["mock_safe", "not_run", "passed", "failed"]


class TraceResponse(BaseModel):
    metadata: AdapterMetadata
    trace_id: str
    steps: list[dict[str, Any]]
    redaction: str


class DecisionCase(BaseModel):
    id: str
    problem: str
    context: str | None = None
    constraints: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class ClarifiedProblem(BaseModel):
    id: str
    statement: str
    assumptions: list[str]
    open_questions: list[ClarificationQuestion]
    status: Literal["needs_clarification", "ready_for_memo"]


class DecisionMemo(BaseModel):
    id: str
    title: str
    recommendation: str
    evidence: list[EvidenceRecord]
    counterarguments: list[str]
    risks: list[str]
    confidence: float = Field(ge=0.0, le=1.0)
    insufficient_evidence: bool
    status: Literal["draft"] = "draft"
    trust_level: TrustLevel = "untrusted"


class DecisionMemoDraftRequest(BaseModel):
    problem: str = Field(min_length=1)
    context: str | None = None
    constraints: list[str] = Field(default_factory=list)


class DecisionMemoDraftResponse(BaseModel):
    metadata: AdapterMetadata
    case: DecisionCase
    clarified_problem: ClarifiedProblem
    memo: DecisionMemo


class PendingKnowledgeCreateRequest(BaseModel):
    content: str = Field(min_length=1)
    origin: str = "reflection"
    source_uri: str | None = None
    tags: list[str] = Field(default_factory=list)
    created_by: str = "local-user"


class PendingKnowledgeRecord(BaseModel):
    id: str
    content: str
    origin: str
    source_uri: str | None = None
    tags: list[str] = Field(default_factory=list)
    created_by: str
    status: ReviewStatus = "pending_review"
    review_required: bool = True
    formal_knowledge_write: bool = False
    external: bool = True
    trust_level: TrustLevel = "untrusted"
    tenant_id: str = "local"
    created_at: datetime = Field(default_factory=utc_now)
    undone_at: datetime | None = None


class PendingKnowledgeListResponse(BaseModel):
    metadata: AdapterMetadata
    items: list[PendingKnowledgeRecord]


class UndoPendingKnowledgeResponse(BaseModel):
    item: PendingKnowledgeRecord
    message: str


class ToolCallLog(BaseModel):
    id: str
    tool_name: str
    args: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = False
    mode: Literal["dry_run"] = "dry_run"
    risk: RiskLevel = "high"
    status: Literal["skipped", "approval_required", "completed"] = "skipped"
    requires_approval: bool = True
    tenant_id: str = "local"


class ApprovalRequest(BaseModel):
    id: str
    action: str
    risk: RiskLevel
    status: Literal["approval_required", "dry_run_recorded", "approved", "rejected"]
    dry_run: bool = True
    tenant_id: str = "local"
    created_at: datetime = Field(default_factory=utc_now)


class AgentStep(BaseModel):
    id: str
    title: str
    status: Literal["planned", "running", "blocked", "completed"]
    tool_calls: list[ToolCallLog] = Field(default_factory=list)


class AgentTask(BaseModel):
    id: str
    worker: str
    title: str
    status: Literal["planned", "running", "blocked", "completed"]
    steps: list[AgentStep] = Field(default_factory=list)


class Workflow(BaseModel):
    id: str
    title: str
    status: Literal["planned", "running", "blocked", "completed"]
    tasks: list[AgentTask] = Field(default_factory=list)


class SupervisorSnapshotResponse(BaseModel):
    metadata: AdapterMetadata
    workflow: Workflow
    approvals: list[ApprovalRequest]
    tool_logs: list[ToolCallLog]
    diff_preview_available: bool = False
    test_preview_available: bool = False


class ApprovalDryRunRequest(BaseModel):
    action: str = Field(min_length=1)
    risk: RiskLevel = "high"
    tool_name: str = "disabled-tool"
    reason: str | None = None


class ApprovalDryRunResponse(BaseModel):
    metadata: AdapterMetadata
    approval: ApprovalRequest
    tool_call: ToolCallLog
    message: str


class SecretStatusResponse(BaseModel):
    server_only: bool
    values_exposed: bool
    auth_required: bool
    configured: dict[str, bool]


class AuditEvent(BaseModel):
    id: str
    tenant_id: str
    actor: str
    event_type: str
    action: str
    risk: str | None = None
    redacted: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class AuditLogResponse(BaseModel):
    items: list[AuditEvent]
