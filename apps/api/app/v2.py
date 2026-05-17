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
from .feature_flags import coach_enabled as _coach_enabled
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
# coach turn (expert-coaching-loop, R1.3, R1.4, R1.10, R11.5)
# ---------------------------------------------------------------------------


from ..schemas import (  # noqa: E402  - intentional local import to avoid top churn
    CoachTurnRequest,
    CoachTurnResponse,
    CoachExpertGap,
    CoachSkillChainState,
    CoachMetacognitionBlock,
)
from .adapter_metadata import make_metadata as _make_coach_metadata
from .coaching_session import (
    ALLOWED_TRANSITIONS as _COACH_ALLOWED,
    ArchivedSessionWrite,
    CoachingSessionRepo,
    InvalidStateTransition,
)


def _require_coach_enabled() -> None:
    """Gate coach routes behind ``REALITY_OS_COACH_ENABLED`` (Task 2.17).

    When the flag is off the route surface is dark-launched: every
    handler responds ``404`` with the same opaque body that a missing
    resource would produce so a client cannot tell the difference
    between "feature off" and "session not found" (R12.3, R10.6).
    The check happens before any DB read so a disabled flag never
    touches storage.
    """

    if not _coach_enabled():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="not found"
        )


_NEXT_ACTION_TO_STATE: dict[str, str] = {
    # Maps the orchestrator-derived ``next_action`` onto the coaching state
    # machine's expected target state. Mirrors design.md's
    # "next_action 决策规则" table (R1.5 + R4.5).
    "awaiting_evidence": "awaiting_evidence",
    "practice": "awaiting_practice",
    "experiment": "awaiting_experiment",
    "review": "awaiting_review",
    "learn": "active",
}


def _coach_next_prompt(answer: str, language: str) -> str:
    """Pick the surface-level prompt the coach renders next.

    Falls back to a localized stub when the orchestrator only produced a
    scaffold (no LLM answer). The stub keeps the response shape stable so
    web/extension clients can still render the turn.
    """

    if answer and answer.strip():
        return answer.strip()
    if language == "en":
        return (
            "What's the smallest piece of evidence you could collect next "
            "to move this decision forward?"
        )
    return "为了把这个决策推进一步，你接下来能收集的最小证据是什么？"


def _grounded_evidence_from(citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Project orchestrator citations to the response's grounded_evidence shape."""

    grounded: list[dict[str, Any]] = []
    for citation in citations or []:
        grounded.append(
            {
                "item_id": citation.get("item_id"),
                "title": citation.get("title", ""),
                "snippet": citation.get("snippet", ""),
                "url": citation.get("url"),
                "relevance": citation.get("relevance"),
                "quality": citation.get("quality"),
                "external": True,
                "trust_level": "untrusted",
            }
        )
    return grounded


def _due_practice(tenant_id: str, language: str) -> list[dict[str, Any]]:
    """Shallow projection of ``retrieval_practice_plan`` for the coach surface.

    Keeping this read-only here means the endpoint stays tenant-scoped via
    the core's existing query (R12.2) without needing M2's mastery
    scheduler to be live yet.
    """

    try:
        plan = get_core().retrieval_practice_plan(
            tenant_id=tenant_id, language=language, limit=3
        )
    except Exception:
        return []
    return list(plan)


@router.post("/coach/turn", response_model=CoachTurnResponse)
async def coach_turn(payload: CoachTurnRequest, request: Request) -> CoachTurnResponse:
    """Run one coach turn (R1.3, R1.4, R1.10, R11.5).

    Behavior:

    * When ``session_id`` is omitted a fresh :class:`CoachingSession` is
      created under the caller's tenant (R1.4) and returned along with
      its id.
    * When ``session_id`` is supplied but the session does not exist for
      this tenant we respond ``404`` and emit no metadata about the
      session (R1.10, R12.3).
    * The orchestrator's ``coach_turn=True`` mode is invoked to derive
      ``expert_gap``, ``skill_chain``, ``next_action`` and an audit row.
    * Any state transition is persisted by *this* layer — the orchestrator
      stays read-only over the aggregate (per design.md note).
    * ``metadata.mode`` is ``"pending-review"`` because the turn writes a
      ``coaching_session_state_log`` row (R11.5).
    """

    _require_coach_enabled()

    context = current_context(request)

    repo = CoachingSessionRepo(path=get_core().path)

    if payload.session_id:
        session = repo.get(tenant_id=context.tenant_id, session_id=payload.session_id)
        if session is None:
            # R1.10 — never leak that a session exists under another tenant.
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="session not found"
            )
        # R1.7 — archived sessions reject new coach_turn writes. We short-
        # circuit before invoking the orchestrator so no downstream write
        # path can silently mutate state behind the user's back.
        if session.state == "archived":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="session is archived",
            )
    else:
        session = repo.get_or_create(
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            profile_id=f"prof:{context.tenant_id}",
            actor=context.user_id,
        )

    language = _language(payload.language)

    try:
        orchestration = orchestrated_ask(
            tenant_id=context.tenant_id,
            question=payload.user_message,
            language=language,
            mode=payload.mode,
            model_tier="flagship",
            actor=context.user_id,
            answer_mode="final",
            coaching_session_id=session.id,
            coach_turn=True,
            user_confidence_check=payload.confidence_check,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    next_action = orchestration.get("next_action") or "learn"
    target_state = _NEXT_ACTION_TO_STATE.get(next_action, "active")

    # Persist the state transition this layer is responsible for. The
    # orchestrator only computed it; transitions live here so the audit
    # row is emitted in the same write path that owns the session
    # (design.md "Security / safety" note + R13.1).
    final_state: str = session.state
    if target_state != session.state and target_state in _COACH_ALLOWED.get(session.state, frozenset()):
        try:
            updated = repo.transition(
                tenant_id=context.tenant_id,
                session_id=session.id,
                to_state=target_state,  # type: ignore[arg-type]
                reason=f"coach_turn:{next_action}",
                actor=context.user_id,
                payload={"next_action": next_action},
            )
            final_state = updated.state
        except (InvalidStateTransition, ArchivedSessionWrite):
            # If the transition is not legal (e.g. archived session) we
            # touch the row instead so ``last_turn_at`` advances and the
            # session does not get archived prematurely (R1.6).
            repo.touch_last_turn(
                tenant_id=context.tenant_id,
                session_id=session.id,
                last_action=next_action,  # type: ignore[arg-type]
            )
    else:
        repo.touch_last_turn(
            tenant_id=context.tenant_id,
            session_id=session.id,
            last_action=next_action,  # type: ignore[arg-type]
        )

    # Compose response payload. Optional fields stay ``None`` when the
    # orchestrator could not derive them rather than synthesising values
    # that would mislead the user.
    expert_gap_data = orchestration.get("expert_gap")
    expert_gap_model: CoachExpertGap | None = None
    if isinstance(expert_gap_data, dict) and "expert_gap_score" in expert_gap_data:
        try:
            expert_gap_model = CoachExpertGap(**{
                k: expert_gap_data.get(k)
                for k in (
                    "expert_gap_score",
                    "missing_points",
                    "rubric_id",
                    "rubric_version",
                    "rubric_source",
                )
            })
        except Exception:
            expert_gap_model = None

    skill_chain_data = orchestration.get("skill_chain")
    skill_chain_model: CoachSkillChainState | None = None
    if isinstance(skill_chain_data, dict):
        try:
            skill_chain_model = CoachSkillChainState(**skill_chain_data)
        except Exception:
            skill_chain_model = None

    metacog_block: CoachMetacognitionBlock | None = None
    if payload.confidence_check is not None:
        metacog_block = CoachMetacognitionBlock(
            confidence_check_required=False,
            user_confidence=payload.confidence_check,
            system_confidence=float(orchestration.get("confidence") or 0.0),
            questions_you_didnt_ask=[],
        )

    return CoachTurnResponse(
        metadata=_make_coach_metadata(
            adapter="v2.coach.turn",
            source_system="apps:api",
            mode="pending-review",
            read_only=False,
        ),
        session_id=session.id,
        session_state=final_state,  # type: ignore[arg-type]
        next_prompt=_coach_next_prompt(orchestration.get("answer", ""), language),
        grounded_evidence=_grounded_evidence_from(orchestration.get("citations", [])),
        contradictions=list(orchestration.get("contradictions") or []),
        due_practice=_due_practice(context.tenant_id, language),
        expert_gap=expert_gap_model,
        skill_chain=skill_chain_model,
        next_action=next_action,  # type: ignore[arg-type]
        metacognition=metacog_block,
        audit_id=str(orchestration.get("audit_id") or ""),
        run_id=str(orchestration.get("run_id") or ""),
        user_confidence_check=payload.confidence_check,
    )


# ---------------------------------------------------------------------------
# coach session read / archive (Task 2.14, R1.7, R12.3)
# ---------------------------------------------------------------------------


@router.get("/coach/sessions/{session_id}")
async def get_coach_session(session_id: str, request: Request) -> dict[str, Any]:
    """Read a single coaching session (R1.7 read access; R12.3 tenant-scoped 404).

    Behaviour:

    * Returns the session aggregate as a plain dict so clients see all the
      documented fields (state, current_chain_id, last_turn_at, …).
    * Cross-tenant lookups return ``404`` with the same body any
      not-found request would receive — no metadata leakage (R1.10,
      R12.3, R10.6).
    * Archived sessions are still readable per R1.7 — only writes are
      rejected.
    * ``metadata.mode`` is ``"read-only"`` (design.md "Endpoint × mode"
      table).
    """

    _require_coach_enabled()

    context = current_context(request)
    repo = CoachingSessionRepo(path=get_core().path)
    session = repo.get(tenant_id=context.tenant_id, session_id=session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="session not found"
        )
    return {
        "metadata": _make_coach_metadata(
            adapter="v2.coach.sessions.get",
            source_system="apps:api",
            mode="read-only",
            read_only=True,
        ).model_dump(),
        "session": session.to_dict(),
    }


@router.post("/coach/sessions/{session_id}/archive")
async def archive_coach_session(session_id: str, request: Request) -> dict[str, Any]:
    """Archive a coaching session (R1.7 write-reject downstream; R13.1 audit).

    Behaviour:

    * Cross-tenant lookups return ``404`` (R1.10, R12.3) with no
      metadata leakage.
    * On success transitions the session to ``archived`` via
      :class:`CoachingSessionRepo.transition` so the
      ``coaching_session_state_log`` row, the
      ``coaching_session_transition`` audit row, and the
      ``coaching_session.archived`` audit row all land in the same
      write (R13.1, R13.4).
    * Already-archived sessions return ``409`` (design.md "Endpoint ×
      mode" table — explicit conflict instead of silent idempotency).
    * ``metadata.mode`` is ``"pending-review"`` because this write
      appends to ``coaching_session_state_log`` (R11.5).
    """

    _require_coach_enabled()

    context = current_context(request)
    repo = CoachingSessionRepo(path=get_core().path)
    session = repo.get(tenant_id=context.tenant_id, session_id=session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="session not found"
        )
    if session.state == "archived":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="session already archived"
        )
    try:
        archived = repo.transition(
            tenant_id=context.tenant_id,
            session_id=session_id,
            to_state="archived",
            reason="manual_archive",
            actor=context.user_id,
            payload={"trigger": "user"},
        )
    except InvalidStateTransition as exc:
        # archived only flows in from declared states; any unexpected
        # state surfaces as 409 rather than 500 so the client can react.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except ArchivedSessionWrite:  # pragma: no cover — guarded above
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="session already archived"
        )
    return {
        "metadata": _make_coach_metadata(
            adapter="v2.coach.sessions.archive",
            source_system="apps:api",
            mode="pending-review",
            read_only=False,
        ).model_dump(),
        "session": archived.to_dict(),
    }


# ---------------------------------------------------------------------------
# rubrics — admin dry-run + read-only listing (Task 2.15, R2.6, R11.5)
# ---------------------------------------------------------------------------


from . import expert_rubric as _expert_rubric_mod  # noqa: E402


class _RubricCheckRequest(BaseModel):
    """Body for ``POST /api/v2/rubrics/check`` (R2.6 admin dry-run).

    ``domain`` is optional — when provided we cross-check it against the
    YAML's ``domain`` field so a payload mistakenly addressed to the
    wrong domain is caught before publish (R2.1 + R2.5 spirit).
    """

    model_config = ConfigDict(extra="ignore")

    domain: str | None = None
    yaml_text: str = Field(min_length=1)


@router.post("/rubrics/check")
async def rubrics_check(payload: _RubricCheckRequest, request: Request) -> dict[str, Any]:
    """Dry-run validate a rubric YAML body without persisting anything.

    Behaviour (per design.md "Endpoint × mode" table):

    * Returns ``200`` with ``valid: bool``, ``errors: list[str]`` and a
      ``rubric`` *preview* (only when ``valid`` is true) so admins can
      diff before opening a git PR (R2.6 deferred to git PR / CI).
    * Never writes to disk and never mutates the loader cache —
      ``metadata.mode = "dry-run"`` (R11.5).
    * ``cited_evidence_ids`` are resolved against the tenant-scoped
      ``KnowledgeCore`` so a rubric author cannot reference evidence
      that does not exist for their tenant (R2.5).
    """

    context = current_context(request)

    core = get_core()

    def _resolver(evidence_id: str) -> bool:
        # R2.5: a rubric is only valid if every cited id resolves to an
        # existing :class:`EvidenceSnapshot` *or* :class:`KnowledgeItem`
        # under the same tenant. We swallow exceptions per-id so a
        # transient error against one id does not poison the whole
        # validation.
        try:
            if core.get_evidence_snapshot(
                tenant_id=context.tenant_id, snapshot_id=evidence_id
            ) is not None:
                return True
        except Exception:
            pass
        try:
            if core.library_get(
                tenant_id=context.tenant_id, item_id=evidence_id
            ) is not None:
                return True
        except Exception:
            pass
        return False

    valid, errors, rubric_preview = _expert_rubric_mod.validate_yaml_text(
        payload.yaml_text,
        expected_domain=payload.domain,
        evidence_resolver=_resolver,
    )

    body: dict[str, Any] = {
        "metadata": _make_coach_metadata(
            adapter="v2.rubrics.check",
            source_system="apps:api",
            mode="dry-run",
            read_only=False,
        ).model_dump(),
        "valid": valid,
        "errors": errors,
        "rubric": (
            _expert_rubric_mod.rubric_to_dict(rubric_preview)
            if rubric_preview is not None
            else None
        ),
    }
    return body


@router.get("/rubrics")
async def rubrics_list(request: Request) -> dict[str, Any]:
    """List every loaded rubric, including prior versions kept for
    historical coach sessions (R2.6).

    Notes:

    * Read-only — declares ``metadata.mode = "read-only"`` per design's
      "Endpoint × mode" table.
    * Tenant-agnostic by design: rubrics are global YAML artefacts
      (``apps/api/expert_rubrics/{domain}.yaml``), not per-tenant data
      (R2.1, R12 unaffected).
    * Lazily refreshes the loader cache so a freshly added domain
      becomes visible without a process restart in dev environments.
    * Surfaces refused rubrics so admins can see *why* a domain is
      missing from the active set (R2.5 troubleshooting).
    """

    # Touch ``current_context`` so the standard auth middleware still runs;
    # the value itself is unused because this endpoint is global per the
    # design notes above.
    current_context(request)

    _expert_rubric_mod.load_all()

    rubrics = _expert_rubric_mod.list_loaded()

    # Group ``versions`` by domain so the UI can present per-domain
    # version pickers (R2.6 "keep prior versions readable").
    versions_by_domain: dict[str, list[str]] = {}
    items: list[dict[str, Any]] = []
    for rubric in rubrics:
        versions_by_domain.setdefault(rubric.domain, []).append(rubric.version)
        items.append(_expert_rubric_mod.rubric_to_dict(rubric))

    refused = [
        {"path": str(path), "reason": reason}
        for (path, reason) in _expert_rubric_mod.refused_rubrics()
    ]

    return {
        "metadata": _make_coach_metadata(
            adapter="v2.rubrics.list",
            source_system="apps:api",
            mode="read-only",
            read_only=True,
        ).model_dump(),
        "items": items,
        "versions_by_domain": versions_by_domain,
        "refused": refused,
    }


# ---------------------------------------------------------------------------
# practice grading (expert-coaching-loop, R5.2, R11.1, R11.5, R13.2)
# ---------------------------------------------------------------------------


from ..schemas import (  # noqa: E402  - kept local to mirror coach-turn import block
    PracticeGradeRequest,
    PracticeGradeResponse,
)


@router.post("/practice/{concept_id}/grade", response_model=PracticeGradeResponse)
async def practice_grade(
    concept_id: str, payload: PracticeGradeRequest, request: Request
) -> PracticeGradeResponse:
    """Apply an SM-2 practice grade to a concept (R5.2, R11.1, R11.5).

    Behaviour:

    * Tenant scoping is enforced via :func:`current_context`; cross-tenant
      lookups surface as ``404`` with no metadata leakage (R12.3, R10.6).
      The actual scoping happens inside
      :meth:`KnowledgeCore.grade_concept`, which raises ``KeyError`` when
      ``(tenant_id, concept_id)`` does not exist.
    * ``grade`` is validated by :class:`PracticeGradeRequest` (``0..5``);
      out-of-range values fail Pydantic validation (HTTP 422). The
      explicit ``ValueError`` branch below covers any defensive raise
      from the core.
    * On success the response carries the freshly-persisted concept and
      ``metadata.mode = "pending-review"`` because this write appends to
      ``mastery_history`` and emits a ``mastery_update`` audit row
      (R11.1, R11.5, R13.2).
    """

    context = current_context(request)
    try:
        concept = get_core().grade_concept(
            tenant_id=context.tenant_id,
            concept_id=concept_id,
            grade=payload.grade,
            actor=context.user_id,
        )
    except KeyError as exc:
        # R12.3 — same body shape as any other not-found path. We do not
        # distinguish "concept does not exist" from "concept belongs to
        # another tenant" so cross-tenant probes leak no information.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="concept not found"
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    return PracticeGradeResponse(
        metadata=_make_coach_metadata(
            adapter="v2.practice.grade",
            source_system="apps:api",
            mode="pending-review",
            read_only=False,
        ),
        concept=concept.to_dict(),
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


from ..schemas import DecisionLogCreateRequest as _DecisionLogCreateRequest  # noqa: E402
from ..schemas import DecisionLogReviewRequest as _DecisionLogReviewRequest  # noqa: E402
from . import calibration as _calibration  # noqa: E402


@router.post("/decisions")
async def create_decision(
    payload: _DecisionLogCreateRequest, request: Request
) -> dict[str, Any]:
    """Create a :class:`DecisionLog` with calibration prediction (R4.1, R6.3, R11.5).

    Behaviour:

    * Requires ``predicted_outcome`` (non-empty) and ``confidence ∈ [0, 1]``
      (R4.1). Missing or out-of-range values return ``400`` directly so
      every shape of "bad prediction" looks the same to the client; a
      pure Pydantic ``Field`` constraint would surface as a 422 with a
      different body, breaking the AC test contract.
    * Persists the row with ``status="active"`` and a ``verdict`` field
      reserved as empty in the JSON payload (R6.3) so a downstream
      ``DecisionMemo`` cannot publish a verdict until the
      ``Active_Evidence_Gathering`` loop closes.
    * Calls :func:`calibration.record_prediction` so the prediction lands
      in ``calibration_records`` and emits the documented
      ``calibration_record`` audit row (R4.2, R13.3) in the same write.
    * Wraps the returned :class:`DecisionLog` in an
      :class:`AdapterMetadata` envelope with ``mode="pending-review"``
      (R11.5) so clients can tell the row is awaiting review.
    """

    context = current_context(request)

    # R4.1 — explicit 400 on missing or out-of-range prediction fields.
    predicted_outcome = (payload.predicted_outcome or "").strip()
    if not predicted_outcome:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="predicted_outcome is required",
        )
    confidence = payload.confidence
    if confidence is None or not (0.0 <= float(confidence) <= 1.0):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="confidence must be in [0.0, 1.0]",
        )
    confidence = float(confidence)

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
    # R6.3 — verdict stays empty until the evidence loop closes. We add
    # it here on the dict so existing clients still see the same fields
    # plus the new ``verdict`` placeholder and the prediction echo.
    log_dict = log.to_dict()
    log_dict["verdict"] = ""
    log_dict["predicted_outcome"] = predicted_outcome
    log_dict["confidence"] = confidence

    core = get_core()
    with core._lock, core._connect() as db:
        ensure_layers_schema(db)
        db.execute(
            "insert into decision_logs(id, tenant_id, data_json, status, created_at) values(?, ?, ?, ?, ?)",
            (
                log.id,
                context.tenant_id,
                _json.dumps(log_dict, ensure_ascii=False),
                "active",
                log.created_at,
            ),
        )

    # R4.2, R13.3 — persist the prediction into ``calibration_records``
    # and emit the ``calibration_record`` audit row. We do this *after*
    # the decision_logs insert so a calibration row can never reference
    # a missing ``decision_log_id``.
    try:
        _calibration.record_prediction(
            core=core,
            tenant_id=context.tenant_id,
            decision_log_id=log.id,
            predicted_outcome=predicted_outcome,
            confidence=confidence,
            actor=context.user_id,
        )
    except ValueError as exc:  # pragma: no cover — guarded above
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    return {
        "metadata": _make_coach_metadata(
            adapter="v2.decisions.create",
            source_system="apps:api",
            mode="pending-review",
            read_only=False,
        ).model_dump(),
        **log_dict,
    }


def _normalize_binary_value(value: bool | int | None) -> int | None:
    """Coerce ``binary_value`` to ``0/1`` for downstream Brier / Log loss.

    JSON clients may send ``true``/``false``, ``0``/``1``, or omit the
    field. The handler delegates "missing when required" semantics to
    :func:`calibration.record_outcome` (which raises ``ValueError``) so
    we keep this helper purely about coercion.
    """

    if value is None:
        return None
    if isinstance(value, bool):
        return 1 if value else 0
    return int(value)


@router.post("/decisions/{decision_id}/review")
async def review_decision(
    decision_id: str,
    payload: _DecisionLogReviewRequest,
    request: Request,
) -> dict[str, Any]:
    """Record a :class:`LearningReview`-style outcome for a decision (R4.2, R4.6).

    Behaviour:

    * Tenant-scoped lookup; cross-tenant or unknown decision ids return
      ``404`` with the same body any not-found path emits (R12.3,
      R10.6) so cross-tenant probes leak no metadata.
    * When ``binary_resolved=True`` the handler passes through to
      :func:`calibration.record_outcome` which computes ``brier_score``
      and ``log_loss`` from the prediction's stored confidence and the
      ``binary_value`` ∈ {0, 1} (R4.2). When ``binary_resolved=False``
      (R4.6) ``brier_score`` and ``log_loss`` stay ``NULL`` so the row
      is excluded from the calibration curve and aggregate score.
    * Updates ``decision_logs.data_json`` with the reviewed payload
      (``actual_outcome``, ``binary_resolved``, ``binary_value``,
      ``reviewed_at``, ``notes``) so the audit trail lives in one place
      and clients can re-render the decision card without joining
      against ``calibration_records``.
    * Response ``metadata.mode == "pending-review"`` per R11.5 — the
      review is durably stored but does not flip the decision to a
      committed verdict yet (R6.3 keeps that gated behind the evidence
      loop).
    """

    context = current_context(request)

    # R4.2 + Pydantic — we let Pydantic validate the literal types; the
    # only cross-field rule (binary_resolved=True ⇒ binary_value
    # required) is enforced inside ``record_outcome`` so errors surface
    # with consistent payloads.
    if payload.binary_resolved and payload.binary_value is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="binary_value is required when binary_resolved=True",
        )

    binary_value = (
        _normalize_binary_value(payload.binary_value) if payload.binary_resolved else None
    )

    core = get_core()
    reviewed_at = _utc()

    # Look up the decision_log row first so cross-tenant requests
    # surface as 404 *before* any calibration mutation runs (R12.3).
    with core._lock, core._connect() as db:
        ensure_layers_schema(db)
        row = db.execute(
            "select data_json from decision_logs where id = ? and tenant_id = ?",
            (decision_id, context.tenant_id),
        ).fetchone()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="decision not found"
            )
        log_dict = _json.loads(row["data_json"])

    # R4.2 / R4.6 — write the calibration outcome. ``record_outcome``
    # raises ``LookupError`` when no prediction exists for this
    # decision (e.g. legacy rows missing a calibration row); we surface
    # that as 404 to mirror the decision-not-found shape rather than
    # confuse the caller with a 500.
    try:
        calib_record = _calibration.record_outcome(
            core=core,
            tenant_id=context.tenant_id,
            decision_log_id=decision_id,
            binary_resolved=payload.binary_resolved,
            binary_value=binary_value,
            actor=context.user_id,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no calibration prediction for decision",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    # Persist the structured review onto the decision_log payload so
    # the next ``GET /decisions`` reflects the updated state.
    log_dict["actual_outcome"] = payload.actual_outcome
    log_dict["binary_resolved"] = bool(payload.binary_resolved)
    log_dict["binary_value"] = binary_value
    log_dict["reviewed_at"] = reviewed_at
    log_dict["notes"] = payload.notes
    # ``brier_score`` / ``log_loss`` echoed back to the dict for clients
    # that read the decision row directly.
    log_dict["brier_score"] = calib_record.brier_score
    log_dict["log_loss"] = calib_record.log_loss

    with core._lock, core._connect() as db:
        ensure_layers_schema(db)
        db.execute(
            "update decision_logs set data_json = ? where id = ? and tenant_id = ?",
            (
                _json.dumps(log_dict, ensure_ascii=False),
                decision_id,
                context.tenant_id,
            ),
        )

    return {
        "metadata": _make_coach_metadata(
            adapter="v2.decisions.review",
            source_system="apps:api",
            mode="pending-review",
            read_only=False,
        ).model_dump(),
        "decision_log_id": decision_id,
        "brier_score": calib_record.brier_score,
        "log_loss": calib_record.log_loss,
        "calibration_record": {
            "id": calib_record.id,
            "tenant_id": calib_record.tenant_id,
            "decision_log_id": calib_record.decision_log_id,
            "predicted_outcome": calib_record.predicted_outcome,
            "confidence": calib_record.confidence,
            "binary_resolved": calib_record.binary_resolved,
            "binary_value": calib_record.binary_value,
            "brier_score": calib_record.brier_score,
            "log_loss": calib_record.log_loss,
            "created_at": calib_record.created_at,
            "reviewed_at": calib_record.reviewed_at,
        },
        "decision": log_dict,
    }


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
