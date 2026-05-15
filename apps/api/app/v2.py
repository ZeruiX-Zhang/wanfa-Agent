"""Production `/api/v2/*` router for Reality OS.

The v2 contract is the canonical surface the new UI talks to. It is deliberately
smaller than the `/api/*` compat router: each endpoint corresponds to one real
product action (absorb / ask / prompt / library / memory / learn / supervise).
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from ..security import current_context
from .intelligence import run_model_probes, summarize_supervisor
from .knowledge_core import (
    SourceKind,
    derive_knowledge_gaps,
    get_core,
    suggested_next_actions,
)
from .model_registry import (
    KNOWN_PROVIDERS,
    ModelConfig,
    ModelSlot,
    call_model,
    get_registry,
)
from .context_anchor import (
    get_current_anchor,
    update_anchor,
    get_anchor_history,
)
from .system_rules import (
    add_rule,
    auto_extract_rule,
    get_active_rules,
    list_rules,
    update_rule,
)
from .audit_agent import zero_context_audit
from .orchestrator import orchestrated_ask
from .expert_search import (
    expert_search,
    get_preset_sources,
    list_sources,
    add_source,
    update_source,
    delete_source,
    create_auto_search,
    list_auto_searches,
    run_auto_search,
    optimize_query,
)
from .thinking_models import (
    get_model_full,
    get_model_meta,
    get_visual_template,
    list_models,
    reload_registry,
    route_model,
)
from .trace import (
    finish_run,
    get_run,
    record_audit_result,
    record_step,
    start_run,
)


router = APIRouter(prefix="/api/v2", tags=["v2"])


def _language(value: Any) -> Literal["zh-CN", "en"]:
    raw = str(value or "").strip().lower()
    if raw in {"en", "en-us", "english"}:
        return "en"
    return "zh-CN"


# ---------------------------------------------------------------------------
# absorb
# ---------------------------------------------------------------------------


class _AbsorbRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str = Field(default="")
    body: str
    source_kind: SourceKind = "direct_import"
    source_url: str | None = None
    tags: list[str] = Field(default_factory=list)
    freshness_date: str | None = None
    language: str | None = None


@router.post("/absorb", status_code=status.HTTP_201_CREATED)
async def absorb(payload: _AbsorbRequest, request: Request) -> dict[str, Any]:
    context = current_context(request)
    try:
        item = get_core().absorb(
            tenant_id=context.tenant_id,
            title=payload.title,
            body=payload.body,
            source_kind=payload.source_kind,
            source_url=payload.source_url,
            tags=payload.tags,
            freshness_date=payload.freshness_date,
            language=payload.language or "zh-CN",
            actor=context.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return item.to_dict()


# ---------------------------------------------------------------------------
# ask
# ---------------------------------------------------------------------------


class _AskRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    question: str
    language: str | None = None
    mode: Literal["simple", "professional"] = "simple"
    model_tier: Literal["flagship", "mid", "basic", "insufficient"] = "flagship"
    answer_mode: Literal["scaffold", "draft", "final"] = "scaffold"
    task_contract: dict[str, Any] | None = None


@router.post("/ask")
async def ask(payload: _AskRequest, request: Request) -> dict[str, Any]:
    context = current_context(request)
    # Mechanism 1: Auto-read context anchor as implicit task_contract
    effective_contract = payload.task_contract
    if not effective_contract:
        anchor = get_current_anchor(context.tenant_id)
        if anchor:
            effective_contract = anchor.to_task_contract()
    try:
        result = get_core().ask(
            tenant_id=context.tenant_id,
            question=payload.question,
            language=_language(payload.language),
            mode=payload.mode,
            model_tier=payload.model_tier,
            actor=context.user_id,
            answer_mode=payload.answer_mode,
            task_contract=effective_contract,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return result.to_dict()


# ---------------------------------------------------------------------------
# Orchestrated Ask (multi-agent pipeline)
# ---------------------------------------------------------------------------


@router.post("/orchestrate/ask")
async def orchestrate_ask_route(payload: _AskRequest, request: Request) -> dict[str, Any]:
    """Multi-agent orchestrated ask — full pipeline with context anchor, rules, and audit.

    This is the premium path that runs all four mechanisms:
    1. Context Anchor (cognitive offloading)
    2. System Rules (self-modifying constraints)
    3. Multi-step generation with role isolation
    4. Zero-context audit (unbiased verification)

    Use /api/v2/ask for the simpler direct path.
    """
    context = current_context(request)
    # Read anchor for implicit contract
    effective_contract = payload.task_contract
    if not effective_contract:
        anchor = get_current_anchor(context.tenant_id)
        if anchor:
            effective_contract = anchor.to_task_contract()
    return orchestrated_ask(
        tenant_id=context.tenant_id,
        question=payload.question,
        language=_language(payload.language),
        mode=payload.mode,
        model_tier=payload.model_tier,
        actor=context.user_id,
        answer_mode=payload.answer_mode,
        task_contract=effective_contract,
    )


# ---------------------------------------------------------------------------
# library
# ---------------------------------------------------------------------------


@router.get("/library/stats")
async def library_stats(request: Request) -> dict[str, Any]:
    context = current_context(request)
    return get_core().library_stats(tenant_id=context.tenant_id)


@router.get("/library")
async def library_list(
    request: Request,
    limit: int = 50,
    offset: int = 0,
    source_kind: SourceKind | None = None,
    tier: str | None = None,
) -> dict[str, Any]:
    context = current_context(request)
    tier_value = tier if tier in {"verified", "needs_review", "insufficient", "rejected", None} else None
    items = get_core().library_list(
        tenant_id=context.tenant_id,
        limit=max(1, min(200, limit)),
        offset=max(0, offset),
        source_kind=source_kind,
        tier=tier_value,  # type: ignore[arg-type]
    )
    return {"items": [item.to_dict() for item in items]}


@router.get("/library/{item_id}")
async def library_get(item_id: str, request: Request) -> dict[str, Any]:
    context = current_context(request)
    item = get_core().library_get(tenant_id=context.tenant_id, item_id=item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="item not found")
    return item.to_dict()


@router.post("/library/{item_id}/approve")
async def library_approve(item_id: str, request: Request) -> dict[str, Any]:
    context = current_context(request)
    try:
        item = get_core().approve_item(tenant_id=context.tenant_id, item_id=item_id, actor=context.user_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="item not found") from exc
    return item.to_dict()


class _RejectRequest(BaseModel):
    reason: str = ""


@router.post("/library/{item_id}/reject")
async def library_reject(item_id: str, payload: _RejectRequest, request: Request) -> dict[str, Any]:
    context = current_context(request)
    try:
        item = get_core().reject_item(
            tenant_id=context.tenant_id,
            item_id=item_id,
            actor=context.user_id,
            reason=payload.reason,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="item not found") from exc
    return item.to_dict()


@router.get("/concepts")
async def list_concepts(request: Request, limit: int = 40) -> dict[str, Any]:
    context = current_context(request)
    concepts = get_core().list_concepts(tenant_id=context.tenant_id, limit=limit)
    return {"items": [concept.to_dict() for concept in concepts]}


# ---------------------------------------------------------------------------
# prompt
# ---------------------------------------------------------------------------


class _PromptOptimizeRequest(BaseModel):
    prompt: str
    language: str | None = None
    include_memory: bool = True


@router.post("/prompt/optimize")
async def prompt_optimize(payload: _PromptOptimizeRequest, request: Request) -> dict[str, Any]:
    context = current_context(request)
    try:
        return get_core().prompt_optimize(
            tenant_id=context.tenant_id,
            prompt=payload.prompt,
            language=_language(payload.language),
            include_memory=payload.include_memory,
            actor=context.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# memory
# ---------------------------------------------------------------------------


class _MemoryAddRequest(BaseModel):
    text: str
    kind: Literal["preference", "decision", "journal"] = "preference"


@router.post("/memory", status_code=status.HTTP_201_CREATED)
async def memory_add(payload: _MemoryAddRequest, request: Request) -> dict[str, Any]:
    context = current_context(request)
    try:
        note = get_core().memory_add(
            tenant_id=context.tenant_id,
            text=payload.text,
            kind=payload.kind,
            actor=context.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return note.to_dict()


@router.get("/memory")
async def memory_list(request: Request, limit: int = 50) -> dict[str, Any]:
    context = current_context(request)
    notes = get_core().memory_list(tenant_id=context.tenant_id, limit=max(1, min(200, limit)))
    return {"items": [note.to_dict() for note in notes]}


# ---------------------------------------------------------------------------
# learn plan
# ---------------------------------------------------------------------------


@router.get("/learn/plan")
async def learn_plan(request: Request, language: str | None = None, limit: int = 5) -> dict[str, Any]:
    context = current_context(request)
    return {
        "items": get_core().learn_plan(
            tenant_id=context.tenant_id,
            language=_language(language),
            limit=max(1, min(20, limit)),
        )
    }


@router.get("/learn/practice")
async def learn_practice(request: Request, language: str | None = None, limit: int = 5) -> dict[str, Any]:
    """Step 3: Retrieval practice exercises for low-mastery concepts."""
    context = current_context(request)
    return {
        "items": get_core().retrieval_practice_plan(
            tenant_id=context.tenant_id,
            language=_language(language),
            limit=max(1, min(20, limit)),
        )
    }


class _SoloThinkingRequest(BaseModel):
    """Step 3: AI-Off mode — user writes their own unassisted reasoning."""
    concept_label: str = ""
    body: str
    language: str | None = None


@router.post("/learn/solo", status_code=status.HTTP_201_CREATED)
async def learn_solo(payload: _SoloThinkingRequest, request: Request) -> dict[str, Any]:
    """Absorb user's independent thinking as a solo_thinking knowledge item.

    This is the 'AI-Off' mode: the user writes their own understanding without
    AI assistance. The content gets a retrieval priority boost (+0.15) in future
    searches because it represents genuine human reasoning.
    """
    context = current_context(request)
    title = payload.concept_label.strip() or "Solo thinking note"
    try:
        item = get_core().absorb(
            tenant_id=context.tenant_id,
            title=f"[独立思考] {title}" if _language(payload.language) == "zh-CN" else f"[Solo thinking] {title}",
            body=payload.body,
            source_kind="memory_note",
            tags=["solo_thinking", "learning_review"],
            language=_language(payload.language),
            actor=context.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return item.to_dict()


# ---------------------------------------------------------------------------
# audit / trace
# ---------------------------------------------------------------------------


@router.get("/audit")
async def audit_log(request: Request, limit: int = 40) -> dict[str, Any]:
    context = current_context(request)
    return {"items": get_core().audit_log(tenant_id=context.tenant_id, limit=max(1, min(200, limit)))}


@router.get("/runs/{run_id}")
async def get_agent_run(run_id: str, request: Request) -> dict[str, Any]:
    """Return a redacted execution trace for a run."""
    context = current_context(request)
    payload = get_run(run_id)
    if payload is None or payload["run"].get("tenant_id") != context.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")
    return payload


@router.get("/evidence/snapshots/{snapshot_id}")
async def get_evidence_snapshot(snapshot_id: str, request: Request) -> dict[str, Any]:
    """Return a tenant-scoped evidence snapshot for citation provenance."""
    context = current_context(request)
    snapshot = get_core().get_evidence_snapshot(tenant_id=context.tenant_id, snapshot_id=snapshot_id)
    if snapshot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="snapshot not found")
    return snapshot.to_dict()


# ---------------------------------------------------------------------------
# Context Anchor (cognitive offloading)
# ---------------------------------------------------------------------------


@router.get("/context-anchor")
async def get_context_anchor(request: Request) -> dict[str, Any]:
    """Get the current context anchor (latest version)."""
    context = current_context(request)
    anchor = get_current_anchor(context.tenant_id)
    if anchor is None:
        return {"exists": False}
    return {"exists": True, "anchor": anchor.to_dict()}


class _AnchorUpdateRequest(BaseModel):
    goal: str
    logic_flow: str = ""
    current_blocker: str = ""


@router.post("/context-anchor")
async def save_context_anchor(payload: _AnchorUpdateRequest, request: Request) -> dict[str, Any]:
    """Create or update the context anchor (archives previous version)."""
    context = current_context(request)
    if not payload.goal.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="goal is required")
    anchor = update_anchor(
        tenant_id=context.tenant_id,
        goal=payload.goal,
        logic_flow=payload.logic_flow,
        current_blocker=payload.current_blocker,
    )
    return anchor.to_dict()


@router.get("/context-anchor/history")
async def context_anchor_history(request: Request, limit: int = 20) -> dict[str, Any]:
    """Get version history of context anchors."""
    context = current_context(request)
    history = get_anchor_history(context.tenant_id, limit=max(1, min(50, limit)))
    return {"items": [a.to_dict() for a in history]}


# ---------------------------------------------------------------------------
# System Rules (self-modifying rule engine)
# ---------------------------------------------------------------------------


@router.get("/rules")
async def list_system_rules(request: Request, include_all: bool = False, limit: int = 50) -> dict[str, Any]:
    """List system rules (active + proposed by default)."""
    context = current_context(request)
    rules = list_rules(context.tenant_id, include_all=include_all, limit=max(1, min(100, limit)))
    return {"items": [r.to_dict() for r in rules]}


class _RuleAddRequest(BaseModel):
    rule_text: str
    source_event: str = "manual"
    status: str = "active"  # manual rules default to active


@router.post("/rules", status_code=status.HTTP_201_CREATED)
async def create_rule(payload: _RuleAddRequest, request: Request) -> dict[str, Any]:
    """Manually add a system rule."""
    context = current_context(request)
    if not payload.rule_text.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="rule_text is required")
    rule = add_rule(
        tenant_id=context.tenant_id,
        rule_text=payload.rule_text,
        source_event=payload.source_event,
        status=payload.status,  # type: ignore[arg-type]
    )
    return rule.to_dict()


class _RuleUpdateRequest(BaseModel):
    status: str | None = None  # active | archived | rejected
    rule_text: str | None = None


@router.patch("/rules/{rule_id}")
async def patch_rule(rule_id: str, payload: _RuleUpdateRequest, request: Request) -> dict[str, Any]:
    """Update a rule's status or text (confirm/reject/edit)."""
    context = current_context(request)
    updated = update_rule(
        tenant_id=context.tenant_id,
        rule_id=rule_id,
        status=payload.status,  # type: ignore[arg-type]
        rule_text=payload.rule_text,
    )
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="rule not found")
    return updated.to_dict()


class _RuleExtractRequest(BaseModel):
    anchor_content: str
    user_correction: str
    language: str | None = None


@router.post("/rules/extract", status_code=status.HTTP_201_CREATED)
async def extract_rule(payload: _RuleExtractRequest, request: Request) -> dict[str, Any]:
    """Auto-extract a rule from a user correction (e.g. rejecting a decision anchor)."""
    context = current_context(request)
    rule = auto_extract_rule(
        tenant_id=context.tenant_id,
        anchor_content=payload.anchor_content,
        user_correction=payload.user_correction,
        language=_language(payload.language),
    )
    return rule.to_dict()


# ---------------------------------------------------------------------------
# Zero-Context Audit (unbiased verification)
# ---------------------------------------------------------------------------


class _AuditReviewRequest(BaseModel):
    output_text: str
    output_type: str = "answer"  # answer | diagnosis | experiment | review
    language: str | None = None
    dimensions: list[str] | None = None  # logic | evidence | feasibility | subjectivity | completeness


@router.post("/audit/review")
async def audit_review(payload: _AuditReviewRequest, request: Request) -> dict[str, Any]:
    """Perform a zero-context audit on any text output.

    The auditor does NOT see the original question — it only evaluates
    the output text for internal quality, logic, and completeness.
    """
    if not payload.output_text.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="output_text is required")
    context = current_context(request)
    run_id = start_run(
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        entrypoint="audit_review",
        input_value=payload.output_text,
        metadata={"output_type": payload.output_type, "language": _language(payload.language)},
    )
    result = zero_context_audit(
        output_text=payload.output_text,
        output_type=payload.output_type,  # type: ignore[arg-type]
        language=_language(payload.language),
        dimensions=payload.dimensions,  # type: ignore[arg-type]
        run_id=run_id,
    )
    record_audit_result(
        run_id=run_id,
        passed=result.passed,
        score=result.score,
        source=result.source,
        output_type=result.output_type,
        input_value=payload.output_text,
        output_value=result.to_dict(),
        metadata={"issue_count": len(result.issues)},
    )
    record_step(
        run_id=run_id,
        step_type="zero_context_audit",
        input_value=payload.output_text,
        output_value=result.to_dict(),
        metadata={"issue_count": len(result.issues), "source": result.source},
    )
    finish_run(run_id, output_value={"passed": result.passed, "score": result.score})
    body = result.to_dict()
    body["run_id"] = run_id
    return body


# ---------------------------------------------------------------------------
# supervise (reuses first-principles digest + new model probe wiring)
# ---------------------------------------------------------------------------


class _SuperviseDigestRequest(BaseModel):
    language: str | None = None
    snapshot: dict[str, Any] | None = None


@router.post("/supervise/digest")
async def supervise_digest(payload: _SuperviseDigestRequest, request: Request) -> dict[str, Any]:
    language = _language(payload.language)
    snapshot = payload.snapshot or {}
    digest = summarize_supervisor(snapshot, language)
    return {
        "language": digest.language,
        "goal": digest.goal,
        "single_next_action": digest.single_next_action,
        "blocked_on": list(digest.blocked_on),
        "drift_alert": digest.drift_alert,
        "risk_counts": dict(digest.risk_counts),
        "approvals_waiting": digest.approvals_waiting,
        "generated_from": list(digest.generated_from),
    }


class _ModelProbeRequest(BaseModel):
    language: str | None = None
    provider: str | None = None
    model: str | None = None


@router.post("/models/probe")
async def models_probe(payload: _ModelProbeRequest) -> dict[str, Any]:
    language = _language(payload.language)
    provider = (payload.provider or "server-configured").strip() or "server-configured"
    model = (payload.model or "server-configured").strip() or "server-configured"
    report = run_model_probes(provider=provider, model=model, language=language, runner=None)
    return {
        "language": report.language,
        "provider": report.provider,
        "model": report.model,
        "source": report.source,
        "tier": report.tier,
        "aggregate_score": report.aggregate_score,
        "probes": [
            {
                "id": probe.id,
                "label": probe.label,
                "passed": probe.passed,
                "score": probe.score,
                "detail": probe.detail,
            }
            for probe in report.probes
        ],
        "workflow_strategy": report.workflow_strategy,
        "recommendation": report.recommendation,
        "notes": list(report.notes),
    }


# ---------------------------------------------------------------------------
# Model Registry — unified model API configuration
# ---------------------------------------------------------------------------


@router.get("/models/providers")
async def list_providers() -> dict[str, Any]:
    """List all known providers with their base URL hints."""
    return {"providers": KNOWN_PROVIDERS}


@router.get("/models/config")
async def list_model_configs() -> dict[str, Any]:
    """List all configured model slots (API keys masked)."""
    registry = get_registry()
    configs = registry.get_all()
    return {
        "slots": [c.to_dict(mask_key=True) for c in configs],
        "available_slots": ["generator", "verifier", "classifier", "embedder"],
    }


class _ModelConfigRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    slot: str  # generator | verifier | classifier | embedder
    provider_id: str  # openai | anthropic | gemini | deepseek | groq | mistral | together | ollama | custom
    base_url: str
    api_key: str = ""
    model_name: str
    enabled: bool = True
    display_label: str = ""


@router.post("/models/config")
async def save_model_config(payload: _ModelConfigRequest) -> dict[str, Any]:
    """Create or update a model slot configuration.

    This is how users connect any OpenAI-compatible model API to Reality OS.
    Supports: OpenAI, Anthropic, Gemini, DeepSeek, Groq, Mistral, Together, Ollama, or any custom endpoint.
    """
    slot = payload.slot.strip().lower()
    if slot not in ("generator", "verifier", "classifier", "embedder"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid slot '{slot}'. Must be one of: generator, verifier, classifier, embedder",
        )

    config = ModelConfig(
        slot=slot,  # type: ignore[arg-type]
        provider_id=payload.provider_id.strip(),
        base_url=payload.base_url.strip().rstrip("/"),
        api_key=payload.api_key,
        model_name=payload.model_name.strip(),
        enabled=payload.enabled,
        display_label=payload.display_label.strip(),
    )
    registry = get_registry()
    saved = registry.set(config)
    return saved.to_dict(mask_key=True)


@router.delete("/models/config/{slot}")
async def delete_model_config(slot: str) -> dict[str, Any]:
    """Remove a model slot configuration."""
    registry = get_registry()
    removed = registry.delete(slot)  # type: ignore[arg-type]
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Slot '{slot}' not found")
    return {"deleted": slot}


@router.post("/models/config/{slot}/test")
async def test_model_config(slot: str) -> dict[str, Any]:
    """Test connectivity to a configured model slot.

    Sends a minimal request to verify the endpoint is reachable and the API key works.
    """
    registry = get_registry()
    return registry.test_connection(slot)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Thinking Models (pluggable reasoning frameworks)
# ---------------------------------------------------------------------------


@router.get("/thinking-models")
async def list_thinking_models() -> dict[str, Any]:
    """List all available thinking models (metadata only, ~100 tokens each)."""
    models = list_models()
    return {
        "models": [m.to_dict() for m in models],
        "total": len(models),
    }


@router.get("/thinking-models/{model_id}")
async def get_thinking_model(model_id: str) -> dict[str, Any]:
    """Get full thinking model content (body + references list). Activated on demand."""
    full = get_model_full(model_id)
    if full is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Thinking model '{model_id}' not found")
    return full.to_dict()


@router.get("/thinking-models/{model_id}/template")
async def get_thinking_model_template(model_id: str) -> dict[str, Any]:
    """Get the HTML visual template for a thinking model."""
    template = get_visual_template(model_id)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No visual template for '{model_id}'")
    return {"model_id": model_id, "html": template}


@router.get("/thinking-models/{model_id}/references/{filename}")
async def get_thinking_model_reference(model_id: str, filename: str) -> dict[str, Any]:
    """Get a specific reference file from a thinking model."""
    full = get_model_full(model_id)
    if full is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Model '{model_id}' not found")
    content = full.references.get(filename)
    if content is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Reference '{filename}' not found")
    return {"model_id": model_id, "filename": filename, "content": content}


@router.post("/thinking-models/route")
async def route_thinking_model(payload: dict[str, Any]) -> dict[str, Any]:
    """Route a question to the best matching thinking model."""
    question = str(payload.get("question", "")).strip()
    language = _language(payload.get("language"))
    if not question:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="question is required")
    model = route_model(question, language)
    if model is None:
        return {"matched": False, "model": None}
    return {"matched": True, "model": model.to_dict()}


@router.post("/thinking-models/reload")
async def reload_thinking_models() -> dict[str, Any]:
    """Force reload the thinking model registry (after adding new skills)."""
    count = reload_registry()
    return {"reloaded": count}


# ---------------------------------------------------------------------------
# Expert Search Engine
# ---------------------------------------------------------------------------


@router.get("/search/presets")
async def search_presets() -> dict[str, Any]:
    """List all preset domain sources with trust scores and categories."""
    return {"sources": get_preset_sources()}


class _ExpertSearchRequest(BaseModel):
    query: str
    language: str | None = None
    sources: list[str] | None = None
    auto_absorb: bool = False


@router.post("/search/expert")
async def search_expert(payload: _ExpertSearchRequest, request: Request) -> dict[str, Any]:
    """Execute an expert search across configured domain sources.

    Optimizes the query, searches relevant sources, scores results on 7 dimensions,
    and optionally auto-absorbs high-quality results (score >= 0.7) into the knowledge base.
    """
    context = current_context(request)
    if not payload.query.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="query is required")
    return expert_search(
        tenant_id=context.tenant_id,
        query=payload.query,
        language=_language(payload.language),
        sources=payload.sources,
        auto_absorb=payload.auto_absorb,
        actor=context.user_id,
    )


@router.post("/search/optimize")
async def search_optimize_query(payload: dict[str, Any]) -> dict[str, Any]:
    """Optimize a raw query into precise search terms."""
    query = str(payload.get("query", "")).strip()
    language = _language(payload.get("language"))
    categories = payload.get("categories")
    if not query:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="query is required")
    return optimize_query(query, language, categories)


@router.get("/search/sources")
async def search_list_sources(request: Request) -> dict[str, Any]:
    """List all configured search sources for the current tenant."""
    context = current_context(request)
    sources = list_sources(context.tenant_id)
    return {"items": [s.to_dict() for s in sources]}


class _AddSourceRequest(BaseModel):
    domain: str
    name: str
    url_pattern: str
    trust_score: float = 0.5
    category: str = "general"
    fetch_interval_minutes: int = 60


@router.post("/search/sources", status_code=status.HTTP_201_CREATED)
async def search_add_source(payload: _AddSourceRequest, request: Request) -> dict[str, Any]:
    """Add a custom search source."""
    context = current_context(request)
    source = add_source(
        context.tenant_id,
        domain=payload.domain,
        name=payload.name,
        url_pattern=payload.url_pattern,
        trust_score=payload.trust_score,
        category=payload.category,
        fetch_interval_minutes=payload.fetch_interval_minutes,
    )
    return source.to_dict()


@router.patch("/search/sources/{source_id}")
async def search_update_source(source_id: str, payload: dict[str, Any], request: Request) -> dict[str, Any]:
    """Update a search source."""
    context = current_context(request)
    updated = update_source(context.tenant_id, source_id, **payload)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source not found")
    return updated.to_dict()


@router.delete("/search/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def search_delete_source(source_id: str, request: Request) -> None:
    """Delete a search source."""
    context = current_context(request)
    if not delete_source(context.tenant_id, source_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source not found")


class _AutoSearchRequest(BaseModel):
    query: str
    sources: list[str] | None = None
    schedule: str = "daily"


@router.post("/search/auto", status_code=status.HTTP_201_CREATED)
async def search_create_auto(payload: _AutoSearchRequest, request: Request) -> dict[str, Any]:
    """Create an automatic search task."""
    context = current_context(request)
    task = create_auto_search(
        context.tenant_id,
        query=payload.query,
        sources=payload.sources,
        schedule=payload.schedule,
    )
    return task.to_dict()


@router.get("/search/auto")
async def search_list_auto(request: Request) -> dict[str, Any]:
    """List all auto-search tasks."""
    context = current_context(request)
    tasks = list_auto_searches(context.tenant_id)
    return {"items": [t.to_dict() for t in tasks]}


@router.post("/search/auto/{task_id}/run")
async def search_run_auto(task_id: str, request: Request) -> dict[str, Any]:
    """Manually trigger an auto-search task."""
    context = current_context(request)
    result = run_auto_search(context.tenant_id, task_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="task not found or disabled")
    return result


# ---------------------------------------------------------------------------
# gaps helper (for the Ask UI when backend offline)
# ---------------------------------------------------------------------------


@router.get("/ask/scaffold")
async def ask_scaffold(language: str | None = None, question: str = "") -> dict[str, Any]:
    lang = _language(language)
    return {
        "language": lang,
        "knowledge_gaps": derive_knowledge_gaps(question),
        "next_actions": suggested_next_actions(question, lang),
    }


__all__ = ["router"]



# ---------------------------------------------------------------------------
# Layer 1: User Profile
# ---------------------------------------------------------------------------

from .reality_layers import (
    UserProfile,
    full_diagnosis_pipeline,
    generate_experiment,
    generate_review_template,
    ensure_layers_schema,
    ActionExperiment,
    LearningReview,
    DecisionLog,
    _utc,
    _id,
)
import json as _json


class _ProfilePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    industry: str = ""
    level: str = "beginner"
    resources: dict[str, Any] = Field(default_factory=dict)
    goals: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    current_tasks: list[str] = Field(default_factory=list)
    error_patterns: list[str] = Field(default_factory=list)


@router.get("/profile")
async def get_profile(request: Request) -> dict[str, Any]:
    context = current_context(request)
    core = get_core()
    with core._lock, core._connect() as db:
        ensure_layers_schema(db)
        row = db.execute(
            "select data_json from user_profiles where tenant_id = ?",
            (context.tenant_id,),
        ).fetchone()
    if row is None:
        return {"exists": False}
    return {"exists": True, "profile": _json.loads(row["data_json"])}


@router.post("/profile")
async def save_profile(payload: _ProfilePayload, request: Request) -> dict[str, Any]:
    context = current_context(request)
    now = _utc()
    profile = UserProfile(
        id=_id("prof"),
        tenant_id=context.tenant_id,
        industry=payload.industry,
        level=payload.level,  # type: ignore[arg-type]
        resources=payload.resources,
        goals=payload.goals,
        constraints=payload.constraints,
        current_tasks=payload.current_tasks,
        decision_history=[],
        error_patterns=payload.error_patterns,
        created_at=now,
        updated_at=now,
    )
    core = get_core()
    with core._lock, core._connect() as db:
        ensure_layers_schema(db)
        db.execute(
            """
            insert into user_profiles(id, tenant_id, data_json, created_at, updated_at)
            values(?, ?, ?, ?, ?)
            on conflict(tenant_id) do update set
              data_json = excluded.data_json,
              updated_at = excluded.updated_at
            """,
            (profile.id, context.tenant_id, _json.dumps(profile.to_dict(), ensure_ascii=False), now, now),
        )
    return profile.to_dict()


# ---------------------------------------------------------------------------
# Layer 3+4+5+6: Full Diagnosis Pipeline
# ---------------------------------------------------------------------------


class _DiagnoseRequest(BaseModel):
    question: str
    language: str | None = None


@router.post("/diagnose")
async def diagnose(payload: _DiagnoseRequest, request: Request) -> dict[str, Any]:
    context = current_context(request)
    language = _language(payload.language)
    run_id = start_run(
        tenant_id=context.tenant_id,
        user_id=context.user_id,
        entrypoint="diagnose",
        input_value=payload.question,
        metadata={"language": language},
    )
    profile: UserProfile | None = None
    core = get_core()
    with core._lock, core._connect() as db:
        ensure_layers_schema(db)
        row = db.execute(
            "select data_json from user_profiles where tenant_id = ?",
            (context.tenant_id,),
        ).fetchone()
        if row:
            data = _json.loads(row["data_json"])
            profile = UserProfile(**data)
    record_step(
        run_id=run_id,
        step_type="load_profile",
        input_value=context.tenant_id,
        output_value={"profile_loaded": profile is not None},
        metadata={"profile_loaded": profile is not None},
    )

    result = full_diagnosis_pipeline(
        question=payload.question,
        profile=profile,
        language=language,
    )
    record_step(
        run_id=run_id,
        step_type="diagnosis_generate",
        input_value=payload.question,
        output_value={
            "diagnosis_id": result["diagnosis"]["id"],
            "experiment_id": result["experiment"]["id"],
        },
        metadata={
            "problem_type": result["diagnosis"].get("problem_type"),
            "thinking_model_count": len(result["diagnosis"].get("thinking_models_used", [])),
        },
    )

    # Persist diagnosis + experiment
    with core._lock, core._connect() as db:
        ensure_layers_schema(db)
        db.execute(
            "insert into diagnoses(id, tenant_id, data_json, created_at) values(?, ?, ?, ?)",
            (result["diagnosis"]["id"], context.tenant_id, _json.dumps(result["diagnosis"], ensure_ascii=False), _utc()),
        )
        db.execute(
            "insert into experiments(id, tenant_id, data_json, status, created_at, updated_at) values(?, ?, ?, ?, ?, ?)",
            (
                result["experiment"]["id"],
                context.tenant_id,
                _json.dumps(result["experiment"], ensure_ascii=False),
                "planned",
                _utc(),
                _utc(),
            ),
        )
    record_step(
        run_id=run_id,
        step_type="diagnosis_persist",
        input_value={
            "diagnosis_id": result["diagnosis"]["id"],
            "experiment_id": result["experiment"]["id"],
        },
        output_value={"persisted": True},
    )
    result["run_id"] = run_id
    finish_run(
        run_id,
        output_value={
            "diagnosis_id": result["diagnosis"]["id"],
            "experiment_id": result["experiment"]["id"],
        },
    )
    return result


# ---------------------------------------------------------------------------
# Layer 6: Experiments CRUD
# ---------------------------------------------------------------------------


@router.get("/experiments")
async def list_experiments(request: Request, limit: int = 20) -> dict[str, Any]:
    context = current_context(request)
    core = get_core()
    with core._lock, core._connect() as db:
        ensure_layers_schema(db)
        rows = db.execute(
            "select data_json from experiments where tenant_id = ? order by created_at desc limit ?",
            (context.tenant_id, max(1, min(100, limit))),
        ).fetchall()
    return {"items": [_json.loads(row["data_json"]) for row in rows]}


class _ExperimentUpdateRequest(BaseModel):
    status: str | None = None
    actual_result: str | None = None


@router.patch("/experiments/{experiment_id}")
async def update_experiment(experiment_id: str, payload: _ExperimentUpdateRequest, request: Request) -> dict[str, Any]:
    context = current_context(request)
    core = get_core()
    with core._lock, core._connect() as db:
        ensure_layers_schema(db)
        row = db.execute(
            "select data_json from experiments where id = ? and tenant_id = ?",
            (experiment_id, context.tenant_id),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="experiment not found")
        data = _json.loads(row["data_json"])
        if payload.status:
            data["status"] = payload.status
        if payload.actual_result is not None:
            data["actual_result"] = payload.actual_result
        data["updated_at"] = _utc()
        db.execute(
            "update experiments set data_json = ?, status = ?, updated_at = ? where id = ?",
            (_json.dumps(data, ensure_ascii=False), data.get("status", "planned"), data["updated_at"], experiment_id),
        )
    return data


# ---------------------------------------------------------------------------
# Layer 7: Learning Reviews
# ---------------------------------------------------------------------------


class _ReviewRequest(BaseModel):
    experiment_id: str | None = None
    original_judgment: str = ""
    actual_result: str = ""
    gap: str = ""
    root_cause: str = "unknown"
    signal_for_next_time: str = ""
    knowledge_card_title: str = ""
    knowledge_card_body: str = ""


@router.post("/reviews")
async def create_review(payload: _ReviewRequest, request: Request) -> dict[str, Any]:
    context = current_context(request)
    review = LearningReview(
        id=_id("rev"),
        tenant_id=context.tenant_id,
        experiment_id=payload.experiment_id,
        original_judgment=payload.original_judgment,
        actual_result=payload.actual_result,
        gap=payload.gap,
        root_cause=payload.root_cause,  # type: ignore[arg-type]
        signal_for_next_time=payload.signal_for_next_time,
        knowledge_card_title=payload.knowledge_card_title,
        knowledge_card_body=payload.knowledge_card_body,
        created_at=_utc(),
    )
    core = get_core()
    with core._lock, core._connect() as db:
        ensure_layers_schema(db)
        db.execute(
            "insert into learning_reviews(id, tenant_id, experiment_id, data_json, created_at) values(?, ?, ?, ?, ?)",
            (review.id, context.tenant_id, review.experiment_id, _json.dumps(review.to_dict(), ensure_ascii=False), review.created_at),
        )
    # Auto-absorb the knowledge card if non-empty
    if review.knowledge_card_title.strip() and review.knowledge_card_body.strip():
        try:
            core.absorb(
                tenant_id=context.tenant_id,
                title=review.knowledge_card_title,
                body=review.knowledge_card_body,
                source_kind="memory_note",
                tags=["learning_review", "sop"],
                actor=context.user_id,
            )
        except Exception:
            pass  # non-critical; the review is still saved
    return review.to_dict()


@router.get("/reviews")
async def list_reviews(request: Request, limit: int = 20) -> dict[str, Any]:
    context = current_context(request)
    core = get_core()
    with core._lock, core._connect() as db:
        ensure_layers_schema(db)
        rows = db.execute(
            "select data_json from learning_reviews where tenant_id = ? order by created_at desc limit ?",
            (context.tenant_id, max(1, min(100, limit))),
        ).fetchall()
    return {"items": [_json.loads(row["data_json"]) for row in rows]}


# ---------------------------------------------------------------------------
# Decision Log
# ---------------------------------------------------------------------------


class _DecisionLogRequest(BaseModel):
    decision: str
    reasoning: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    success_metric: str = ""
    review_date: str = ""


@router.post("/decisions")
async def create_decision(payload: _DecisionLogRequest, request: Request) -> dict[str, Any]:
    context = current_context(request)
    log = DecisionLog(
        id=_id("dec"),
        tenant_id=context.tenant_id,
        decision=payload.decision,
        reasoning=payload.reasoning,
        evidence=payload.evidence,
        assumptions=payload.assumptions,
        risks=payload.risks,
        success_metric=payload.success_metric,
        review_date=payload.review_date,
        status="active",
        created_at=_utc(),
    )
    core = get_core()
    with core._lock, core._connect() as db:
        ensure_layers_schema(db)
        db.execute(
            "insert into decision_logs(id, tenant_id, data_json, status, created_at) values(?, ?, ?, ?, ?)",
            (log.id, context.tenant_id, _json.dumps(log.to_dict(), ensure_ascii=False), "active", log.created_at),
        )
    return log.to_dict()


@router.get("/decisions")
async def list_decisions(request: Request, limit: int = 20) -> dict[str, Any]:
    context = current_context(request)
    core = get_core()
    with core._lock, core._connect() as db:
        ensure_layers_schema(db)
        rows = db.execute(
            "select data_json from decision_logs where tenant_id = ? order by created_at desc limit ?",
            (context.tenant_id, max(1, min(100, limit))),
        ).fetchall()
    return {"items": [_json.loads(row["data_json"]) for row in rows]}



# ---------------------------------------------------------------------------
# Evaluation dashboard
# ---------------------------------------------------------------------------

from .evals import compute_metrics


@router.get("/eval/dashboard")
async def eval_dashboard(request: Request) -> dict[str, Any]:
    context = current_context(request)
    core = get_core()
    # Make sure layer tables exist before we query them.
    with core._lock, core._connect() as db:
        from .reality_layers import ensure_layers_schema

        ensure_layers_schema(db)
    metrics = compute_metrics(core=core, tenant_id=context.tenant_id)
    return {
        "metrics": [m.to_dict() for m in metrics],
    }


# ---------------------------------------------------------------------------
# Review Queue (Human Oversight Quality Gate)
# ---------------------------------------------------------------------------

from .quality_gate import QualityGate  # noqa: E402
from .model_summarizer import ModelSummarizer  # noqa: E402


@router.get("/review/pending")
async def review_pending(request: Request, limit: int = 50) -> dict[str, Any]:
    """List pending review items for the current tenant.

    Returns items in the review queue that are awaiting human approval,
    ordered by created_at DESC.
    """
    context = current_context(request)
    gate = QualityGate()
    items = gate.list_pending(tenant_id=context.tenant_id, limit=max(1, min(200, limit)))
    return {"items": [item.to_dict() for item in items]}


@router.post("/review/{review_id}/approve")
async def review_approve(review_id: str, request: Request) -> dict[str, Any]:
    """Approve a pending review item.

    Updates the review status to 'approved' and completes formal ingestion
    of the associated knowledge item.
    """
    context = current_context(request)
    gate = QualityGate()
    try:
        item = gate.approve(
            tenant_id=context.tenant_id,
            review_id=review_id,
            reviewer=context.user_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return item.to_dict()


class _ReviewRejectRequest(BaseModel):
    reason: str = ""


@router.post("/review/{review_id}/reject")
async def review_reject(review_id: str, payload: _ReviewRejectRequest, request: Request) -> dict[str, Any]:
    """Reject a pending review item.

    Updates the review status to 'rejected' and records the rejection
    reason to the audit log.
    """
    context = current_context(request)
    gate = QualityGate()
    try:
        item = gate.reject(
            tenant_id=context.tenant_id,
            review_id=review_id,
            reviewer=context.user_id,
            reason=payload.reason,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return item.to_dict()


class _ReviewBatchRequest(BaseModel):
    review_ids: list[str]
    action: Literal["approve", "reject"]
    reason: str = ""


@router.post("/review/batch")
async def review_batch(payload: _ReviewBatchRequest, request: Request) -> dict[str, Any]:
    """Batch approve or reject multiple pending review items.

    All operations are transactional — if any item fails, the entire
    batch is rolled back.
    """
    context = current_context(request)
    gate = QualityGate()

    if not payload.review_ids:
        return {"items": [], "count": 0}

    try:
        if payload.action == "approve":
            items = gate.batch_approve(
                tenant_id=context.tenant_id,
                review_ids=payload.review_ids,
                reviewer=context.user_id,
            )
        else:
            items = gate.batch_reject(
                tenant_id=context.tenant_id,
                review_ids=payload.review_ids,
                reviewer=context.user_id,
                reason=payload.reason,
            )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return {"items": [item.to_dict() for item in items], "count": len(items)}


# ---------------------------------------------------------------------------
# Knowledge Optimization
# ---------------------------------------------------------------------------


class _KnowledgeOptimizeRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    overlap_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    refresh_threshold_days: int = Field(default=90, ge=1)


@router.post("/knowledge/optimize")
async def knowledge_optimize(payload: _KnowledgeOptimizeRequest, request: Request) -> dict[str, Any]:
    """Trigger knowledge base optimization.

    Performs two operations:
    1. Overlap detection — identifies knowledge item pairs with token overlap
       above the specified threshold (default 70%) and suggests merging.
    2. Freshness marking — marks items whose freshness_date exceeds the
       configured threshold as needs_refresh, lowering their search weight.
    """
    context = current_context(request)
    core = get_core()
    summarizer = ModelSummarizer()

    # 1. Detect overlapping items
    overlaps = summarizer.detect_overlap(
        tenant_id=context.tenant_id,
        threshold=payload.overlap_threshold,
    )

    # 2. Mark stale items as needs_refresh
    marked_ids = core.mark_needs_refresh(
        tenant_id=context.tenant_id,
        threshold_days=payload.refresh_threshold_days,
    )

    return {
        "overlaps": [
            {"item_a": a, "item_b": b, "similarity": score}
            for a, b, score in overlaps
        ],
        "overlap_count": len(overlaps),
        "overlap_threshold": payload.overlap_threshold,
        "marked_needs_refresh": marked_ids,
        "refresh_count": len(marked_ids),
        "refresh_threshold_days": payload.refresh_threshold_days,
    }


# ---------------------------------------------------------------------------
# Knowledge Preview (Pre-ingestion scoring report)
# ---------------------------------------------------------------------------


class _KnowledgePreviewRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str = Field(default="")
    body: str
    source_kind: SourceKind = "direct_import"
    source_url: str | None = None
    tags: list[str] = Field(default_factory=list)


@router.post("/knowledge/preview")
async def knowledge_preview(payload: _KnowledgePreviewRequest, request: Request) -> dict[str, Any]:
    """Generate a pre-ingestion scoring preview report.

    Runs ModelSummarizer and SkillValidator on the provided content without
    actually ingesting it. Returns a comprehensive report including quality
    scores, validation results, and a recommendation on whether human review
    is needed.
    """
    context = current_context(request)
    gate = QualityGate()

    if not payload.body.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="body is required")

    report = gate.get_preview_report(
        tenant_id=context.tenant_id,
        title=payload.title,
        body=payload.body,
        source_kind=payload.source_kind,
        source_url=payload.source_url,
        tags=payload.tags,
    )

    return report
