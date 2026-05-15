from __future__ import annotations

import os

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware

from .security import api_auth_required, current_context, require_api_context, secret_status
from .schemas import (
    AdapterMetadata,
    ApprovalDryRunRequest,
    ApprovalDryRunResponse,
    ApprovalRequest,
    CaptureRequest,
    CaptureResponse,
    ClarificationQuestion,
    ClarificationRequest,
    ClarificationResponse,
    ClarifiedProblem,
    DecisionCase,
    DecisionMemo,
    DecisionMemoDraftRequest,
    DecisionMemoDraftResponse,
    EvalSummaryResponse,
    EvidenceLedgerResponse,
    EvidenceRecord,
    HealthResponse,
    IntelligenceObject,
    IntelligenceObjectListResponse,
    KnowledgeSummaryResponse,
    PendingKnowledgeCreateRequest,
    PendingKnowledgeListResponse,
    PendingKnowledgeRecord,
    RagDebugResponse,
    RagHit,
    RagQueryRequest,
    RagQueryResponse,
    SettingsResponse,
    SourceListResponse,
    SourceRecord,
    SupervisorSnapshotResponse,
    ToolCallLog,
    TraceResponse,
    UndoPendingKnowledgeResponse,
    VerificationRequest,
    VerificationResponse,
    Workflow,
    AgentTask,
    AgentStep,
    AuditLogResponse,
    new_id,
    SecretStatusResponse,
    utc_now,
)
from .storage import get_storage


app = FastAPI(
    title="Reality OS API Adapter",
    version="0.4.0",
    description=(
        "Safe FastAPI adapter skeleton for Reality OS. "
        "Legacy systems are not modified; writes are pending review or dry-run."
    ),
    dependencies=[Depends(require_api_context)],
)


def _cors_origins() -> list[str]:
    configured = os.getenv("REALITY_OS_WEB_ORIGINS", "")
    if configured.strip():
        return [origin.strip() for origin in configured.split(",") if origin.strip()]
    return [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3010",
        "http://127.0.0.1:3010",
    ]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

storage = get_storage()


SOURCES: list[SourceRecord] = [
    SourceRecord(
        id="sou_src_reality_os_adapter_notes",
        title="Reality OS adapter notes",
        origin="legacy:sou",
        uri=None,
        summary="Read-only adapter placeholder for consolidated Reality OS evidence.",
        tags=["reality-os", "adapter"],
    ),
    SourceRecord(
        id="sou_src_search_knowledge",
        title="Search knowledge inventory",
        origin="legacy:sou",
        uri=None,
        summary="Read-only placeholder for source, evidence-ledger, and intelligence object inventory.",
        tags=["search", "knowledge", "sou"],
    ),
]

EVIDENCE: list[EvidenceRecord] = [
    EvidenceRecord(
        id="ev_adapter_required",
        claim="Reality OS needs a unified adapter layer before deeper integration.",
        source_id="sou_src_reality_os_adapter_notes",
        quote="Adapter-first integration keeps legacy projects independently runnable.",
        rationale="Supports read-only legacy access and limits migration blast radius.",
    ),
    EvidenceRecord(
        id="ev_pending_review_required",
        claim="Knowledge writes should default to pending review.",
        source_id="sou_src_search_knowledge",
        quote="Generated or external content must not enter formal knowledge automatically.",
        rationale="Maintains review gates for untrusted inputs and AI-generated drafts.",
    ),
]

INTELLIGENCE_OBJECTS: list[IntelligenceObject] = [
    IntelligenceObject(
        id="io_adapter_boundary",
        title="Adapter boundary",
        object_type="architecture_note",
        summary="Expose a unified API without moving or deleting legacy systems.",
        evidence_ids=["ev_adapter_required"],
        confidence=0.72,
    ),
    IntelligenceObject(
        id="io_pending_review",
        title="Pending review safety gate",
        object_type="policy_note",
        summary="All new knowledge-like writes remain pending until reviewed.",
        evidence_ids=["ev_pending_review_required"],
        confidence=0.8,
    ),
]

CAPTURES: dict[str, CaptureResponse] = {}
PENDING_KNOWLEDGE: dict[str, PendingKnowledgeRecord] = {}
APPROVALS: list[ApprovalRequest] = [
    ApprovalRequest(
        id="appr_initial_tool_gate",
        action="Enable external tool execution",
        risk="high",
        status="approval_required",
    )
]
TOOL_LOGS: list[ToolCallLog] = [
    ToolCallLog(
        id="tool_initial_disabled",
        tool_name="external-web-fetch",
        args={"url": "untrusted://example"},
        enabled=False,
        risk="high",
        status="approval_required",
    )
]


def metadata(adapter: str, source_system: str, mode: str = "mock-safe", read_only: bool = True) -> AdapterMetadata:
    return AdapterMetadata(
        adapter=adapter,
        source_system=source_system,
        mode=mode,  # type: ignore[arg-type]
        read_only=read_only,
    )


def matching_evidence(query: str) -> list[EvidenceRecord]:
    tokens = {token for token in query.lower().replace("-", " ").split() if len(token) > 2}
    if not tokens:
        return []
    source_by_id = {source.id: source for source in SOURCES}
    matches: list[EvidenceRecord] = []
    for item in EVIDENCE:
        source = source_by_id.get(item.source_id)
        haystack = " ".join(
            [
                item.claim,
                item.quote,
                item.rationale,
                source.title if source else "",
                source.summary if source else "",
                " ".join(source.tags) if source else "",
            ]
        ).lower()
        if any(token in haystack for token in tokens):
            matches.append(item)
    return matches


def make_clarification(problem: str) -> list[ClarificationQuestion]:
    questions = [
        ClarificationQuestion(
            id="cq_success_metric",
            question="What decision or success metric should this answer optimize for?",
            reason="Decision memos need a target outcome before ranking tradeoffs.",
        ),
        ClarificationQuestion(
            id="cq_constraints",
            question="Which constraints are non-negotiable for this decision?",
            reason="Constraints define retrieval filters and risk evaluation.",
        ),
    ]
    if len(problem.split()) >= 8:
        return questions[:1]
    return questions


@app.get("/", response_model=dict[str, str], tags=["health"])
async def root() -> dict[str, str]:
    return {"service": "reality-os-api", "status": "ok", "docs": "/docs"}


@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health() -> HealthResponse:
    return HealthResponse(
        service="reality-os-api",
        status="ok",
        version="0.4.0",
        api_key_policy="server-only; no keys loaded by this adapter",
        tool_execution="disabled",
        adapters={
            "sou": "read-only",
            "prompt": "mock-safe",
            "work": "mock-safe",
            "decision": "mock-safe",
            "knowledge": "pending-review",
            "supervisor": "dry-run",
        },
        auth_required=api_auth_required(),
    )


@app.get("/security/secret-status", response_model=SecretStatusResponse, tags=["security"])
async def get_secret_status() -> dict[str, object]:
    return secret_status()


@app.get("/security/audit-log", response_model=AuditLogResponse, tags=["security"])
async def get_audit_log(request: Request) -> AuditLogResponse:
    context = current_context(request)
    return AuditLogResponse(items=storage.list_audit(context.tenant_id))


@app.get("/sou/sources", response_model=SourceListResponse, tags=["sou"])
async def sou_sources() -> SourceListResponse:
    return SourceListResponse(
        metadata=metadata("sou.sources", "legacy:sou", mode="read-only"),
        sources=SOURCES,
    )


@app.get("/sou/evidence-ledger", response_model=EvidenceLedgerResponse, tags=["sou"])
async def sou_evidence_ledger() -> EvidenceLedgerResponse:
    return EvidenceLedgerResponse(
        metadata=metadata("sou.evidence-ledger", "legacy:sou", mode="read-only"),
        evidence=EVIDENCE,
    )


@app.get("/sou/intelligence-objects", response_model=IntelligenceObjectListResponse, tags=["sou"])
async def sou_intelligence_objects() -> IntelligenceObjectListResponse:
    return IntelligenceObjectListResponse(
        metadata=metadata("sou.intelligence-objects", "legacy:sou", mode="read-only"),
        objects=INTELLIGENCE_OBJECTS,
    )


@app.get("/sou/settings", response_model=SettingsResponse, tags=["sou"])
async def sou_settings() -> SettingsResponse:
    return SettingsResponse(
        metadata=metadata("sou.settings", "legacy:sou", mode="read-only"),
        settings={
            "legacy_project_mutated": False,
            "read_only_first": True,
            "external_content_default": "untrusted",
            "formal_knowledge_writes_enabled": False,
        },
    )


@app.post("/prompt/clarification", response_model=ClarificationResponse, tags=["prompt"])
async def prompt_clarification(payload: ClarificationRequest) -> ClarificationResponse:
    questions = make_clarification(payload.problem)
    return ClarificationResponse(
        clarified_problem_id=new_id("clarified"),
        original_problem=payload.problem,
        assumptions=[
            "No external content is trusted until reviewed.",
            "Clarification output is not written to formal knowledge.",
        ],
        questions=questions,
        status="needs_clarification" if questions else "ready_for_retrieval",
        metadata=metadata("prompt.clarification", "services:prompt-orchestrator", read_only=False),
    )


@app.post("/prompt/capture", response_model=CaptureResponse, status_code=status.HTTP_202_ACCEPTED, tags=["prompt"])
async def prompt_capture(payload: CaptureRequest) -> CaptureResponse:
    record = CaptureResponse(
        capture_id=new_id("capture"),
        status="pending_review",
        review_required=True,
        external=True,
        trust_level="untrusted",
        created_at=utc_now(),
    )
    CAPTURES[record.capture_id] = record
    return record


@app.get("/prompt/knowledge-os-summary", response_model=KnowledgeSummaryResponse, tags=["prompt"])
async def prompt_knowledge_os_summary() -> KnowledgeSummaryResponse:
    stored_pending = storage.list_pending()
    active_pending = [item for item in [*PENDING_KNOWLEDGE.values(), *stored_pending] if item.status == "pending_review"]
    return KnowledgeSummaryResponse(
        metadata=metadata("prompt.knowledge-os-summary", "services:prompt-orchestrator"),
        captures_pending_review=len(CAPTURES),
        pending_knowledge_writes=len(active_pending),
        formal_knowledge_writes=0,
        policy="Captured and generated content remains pending review; no formal knowledge writes occur here.",
    )


@app.post("/work/rag/query", response_model=RagQueryResponse, tags=["work"])
async def work_rag_query(payload: RagQueryRequest) -> RagQueryResponse:
    evidence = matching_evidence(payload.query)[: payload.top_k]
    source_by_id = {source.id: source for source in SOURCES}
    hits = [
        RagHit(
            source_id=item.source_id,
            title=source_by_id[item.source_id].title,
            snippet=item.quote,
            score=max(0.35, 0.82 - index * 0.08),
            evidence_ids=[item.id],
        )
        for index, item in enumerate(evidence)
        if item.source_id in source_by_id
    ]
    return RagQueryResponse(
        metadata=metadata("work.rag-query", "legacy:work"),
        query=payload.query,
        hits=hits,
        debug={
            "mode": "mock-safe",
            "original_rag_pipeline_modified": False,
            "retrieval_backend": "in-memory-adapter-fixture",
            "insufficient_evidence": len(hits) == 0,
        }
        if payload.include_debug
        else {},
    )


@app.get("/work/rag/debug", response_model=RagDebugResponse, tags=["work"])
async def work_rag_debug() -> RagDebugResponse:
    return RagDebugResponse(
        metadata=metadata("work.rag-debug", "legacy:work"),
        pipeline="adapter-shell",
        original_pipeline_modified=False,
        notes=[
            "No legacy RAG files are changed by this API skeleton.",
            "Adapter responses use safe in-memory fixtures until real connectors are reviewed.",
        ],
    )


@app.post("/work/verification", response_model=VerificationResponse, tags=["work"])
async def work_verification(payload: VerificationRequest) -> VerificationResponse:
    known_ids = {item.id for item in EVIDENCE}
    matched_ids = [item_id for item_id in payload.evidence_ids if item_id in known_ids]
    if not matched_ids:
        return VerificationResponse(
            metadata=metadata("work.verification", "services:verification"),
            claim=payload.claim,
            verdict="insufficient_evidence",
            confidence=0.0,
            evidence_ids=[],
            risks=["No recognized evidence IDs were supplied."],
            insufficient_evidence=True,
        )
    return VerificationResponse(
        metadata=metadata("work.verification", "services:verification"),
        claim=payload.claim,
        verdict="supported",
        confidence=min(0.9, 0.55 + len(matched_ids) * 0.15),
        evidence_ids=matched_ids,
        risks=["Adapter verdict is mock-safe and must be replaced by verified pipeline output."],
        insufficient_evidence=False,
    )


@app.get("/work/eval-summary", response_model=EvalSummaryResponse, tags=["work"])
async def work_eval_summary() -> EvalSummaryResponse:
    return EvalSummaryResponse(
        metadata=metadata("work.eval-summary", "services:verification"),
        suites=[
            {
                "name": "adapter-smoke",
                "status": "mock_safe",
                "coverage": ["health", "sou", "prompt", "work", "decision", "knowledge", "supervisor"],
            }
        ],
        last_run_status="mock_safe",
    )


@app.get("/work/trace/{trace_id}", response_model=TraceResponse, tags=["work"])
async def work_trace(trace_id: str) -> TraceResponse:
    return TraceResponse(
        metadata=metadata("work.trace", "services:verification"),
        trace_id=trace_id,
        steps=[
            {"name": "input", "status": "recorded", "redacted": True},
            {"name": "retrieval", "status": "mock_safe", "external_content": "untrusted"},
            {"name": "verification", "status": "mock_safe", "tool_execution": "disabled"},
        ],
        redaction="No API keys, secrets, or raw external content are emitted by this adapter.",
    )


@app.post("/decision/memo/draft", response_model=DecisionMemoDraftResponse, tags=["decision"])
async def decision_memo_draft(payload: DecisionMemoDraftRequest) -> DecisionMemoDraftResponse:
    case = DecisionCase(
        id=new_id("case"),
        problem=payload.problem,
        context=payload.context,
        constraints=payload.constraints,
    )
    questions = make_clarification(payload.problem)
    evidence = matching_evidence(payload.problem)
    insufficient = len(evidence) == 0
    clarified = ClarifiedProblem(
        id=new_id("clarified"),
        statement=payload.problem,
        assumptions=[
            "External and generated content remains untrusted.",
            "The memo is a draft and needs human review before use.",
        ],
        open_questions=questions,
        status="needs_clarification" if questions else "ready_for_memo",
    )
    memo = DecisionMemo(
        id=new_id("memo"),
        title=f"Decision memo draft: {payload.problem[:64]}",
        recommendation=(
            "Do not decide yet; collect reviewed evidence first."
            if insufficient
            else "Proceed only with adapter-gated implementation and preserve rollback paths."
        ),
        evidence=evidence,
        counterarguments=[
            "A direct legacy integration may provide richer behavior sooner.",
            "Mock-safe adapters can hide mismatches with real service contracts.",
        ],
        risks=[
            "insufficient evidence" if insufficient else "adapter evidence is not a production verification result",
            "human review is required before promoting any generated knowledge",
        ],
        confidence=0.0 if insufficient else min(0.85, 0.5 + len(evidence) * 0.15),
        insufficient_evidence=insufficient,
    )
    return DecisionMemoDraftResponse(
        metadata=metadata("decision.memo-draft", "apps:api"),
        case=case,
        clarified_problem=clarified,
        memo=memo,
    )


@app.post(
    "/knowledge/pending",
    response_model=PendingKnowledgeRecord,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["knowledge"],
)
async def create_pending_knowledge(payload: PendingKnowledgeCreateRequest, request: Request) -> PendingKnowledgeRecord:
    context = current_context(request)
    record = PendingKnowledgeRecord(
        id=new_id("pending"),
        content=payload.content,
        origin=payload.origin,
        source_uri=payload.source_uri,
        tags=payload.tags,
        created_by=payload.created_by,
        status="pending_review",
        review_required=True,
        formal_knowledge_write=False,
        external=True,
        trust_level="untrusted",
        tenant_id=context.tenant_id,
        created_at=utc_now(),
    )
    PENDING_KNOWLEDGE[record.id] = record
    return storage.save_pending(record)


@app.get("/knowledge/pending", response_model=PendingKnowledgeListResponse, tags=["knowledge"])
async def list_pending_knowledge(request: Request) -> PendingKnowledgeListResponse:
    context = current_context(request)
    stored = storage.list_pending(context.tenant_id)
    in_memory = [item for item in PENDING_KNOWLEDGE.values() if item.tenant_id == context.tenant_id]
    return PendingKnowledgeListResponse(
        metadata=metadata("knowledge.pending-list", "services:knowledge", mode="pending-review", read_only=False),
        items=[*in_memory, *[item for item in stored if item.id not in PENDING_KNOWLEDGE]],
    )


@app.post("/knowledge/pending/{pending_id}/undo", response_model=UndoPendingKnowledgeResponse, tags=["knowledge"])
async def undo_pending_knowledge(pending_id: str, request: Request) -> UndoPendingKnowledgeResponse:
    context = current_context(request)
    record = PENDING_KNOWLEDGE.get(pending_id) or storage.get_pending(pending_id, context.tenant_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="pending knowledge record not found")
    if record.status != "undone":
        record.status = "undone"
        record.undone_at = utc_now()
        PENDING_KNOWLEDGE[pending_id] = record
        storage.update_pending(record)
    return UndoPendingKnowledgeResponse(item=record, message="Pending knowledge write undone; formal knowledge was untouched.")


@app.get("/supervisor/snapshot", response_model=SupervisorSnapshotResponse, tags=["supervisor"])
async def supervisor_snapshot(request: Request) -> SupervisorSnapshotResponse:
    context = current_context(request)
    approvals = [*APPROVALS, *storage.list_approvals(context.tenant_id)]
    tool_logs = [*TOOL_LOGS, *storage.list_tool_logs(context.tenant_id)]
    workflow = Workflow(
        id="wf_reality_os_adapter_workflow",
        title="Reality OS adapter implementation",
        status="planned",
        tasks=[
            AgentTask(
                id="task_worker_1_api",
                worker="Worker 1",
                title="apps/api FastAPI adapter layer",
                status="running",
                steps=[
                    AgentStep(
                        id="step_api_skeleton",
                        title="Expose safe adapter route surface",
                        status="running",
                        tool_calls=tool_logs,
                    )
                ],
            )
        ],
    )
    return SupervisorSnapshotResponse(
        metadata=metadata("supervisor.snapshot", "services:workflow", mode="dry-run", read_only=True),
        workflow=workflow,
        approvals=approvals,
        tool_logs=tool_logs,
        diff_preview_available=False,
        test_preview_available=False,
    )


@app.post("/supervisor/approval-requests/dry-run", response_model=ApprovalDryRunResponse, tags=["supervisor"])
async def supervisor_approval_dry_run(payload: ApprovalDryRunRequest, request: Request) -> ApprovalDryRunResponse:
    context = current_context(request)
    approval = ApprovalRequest(
        id=new_id("approval"),
        action=payload.action,
        risk=payload.risk,
        status="dry_run_recorded",
        dry_run=True,
        tenant_id=context.tenant_id,
        created_at=utc_now(),
    )
    tool_call = ToolCallLog(
        id=new_id("tool"),
        tool_name=payload.tool_name,
        args={"reason": payload.reason} if payload.reason else {},
        enabled=False,
        mode="dry_run",
        risk=payload.risk,
        status="approval_required" if payload.risk == "high" else "skipped",
        requires_approval=payload.risk == "high",
        tenant_id=context.tenant_id,
    )
    APPROVALS.append(approval)
    TOOL_LOGS.append(tool_call)
    storage.save_approval(approval)
    storage.save_tool_log(tool_call)
    return ApprovalDryRunResponse(
        metadata=metadata("supervisor.approval-dry-run", "services:workflow", mode="dry-run", read_only=False),
        approval=approval,
        tool_call=tool_call,
        message="Dry-run recorded only. Tool execution remains disabled.",
    )


# ---------------------------------------------------------------------------
# Frontend compatibility router
# ---------------------------------------------------------------------------

from .app.compat import router as compat_router  # noqa: E402
from .app.v2 import router as v2_router  # noqa: E402

app.include_router(compat_router)
app.include_router(v2_router)
