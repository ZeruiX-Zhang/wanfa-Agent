"""Orchestrator — multi-agent coordination layer for Reality OS.

The Orchestrator does NOT do work itself. It decomposes a user request into
discrete steps, dispatches each step to the appropriate subsystem (with
minimal context), and assembles the final result.

This implements the "Coordinator/Manager" pattern:
- Step 1: Load context anchor (cognitive offloading)
- Step 2: Load active rules (self-modifying system)
- Step 3: Classify the question (classifier slot or deterministic)
- Step 4: Retrieve evidence (knowledge core search)
- Step 5: Generate response (generator slot or deterministic)
- Step 6: Verify response (verifier slot — zero-context audit)
- Step 7: Assemble and return

Each step has:
- An independent timeout
- A deterministic fallback (no LLM required)
- Minimal context (only what that step needs)

The orchestrator is opt-in: callers can use it via `/api/v2/orchestrate/ask`
or continue using the direct `/api/v2/ask` endpoint.
"""

from __future__ import annotations

from typing import Any, Literal

from .context_anchor import get_current_anchor
from .system_rules import get_active_rules, increment_trigger
from .audit_agent import zero_context_audit
from .security_scanner import evidence_warning
from .thinking_models import get_model_full, get_registry
from .thinking_models.router import (
    compose_model_prompt,
    decide_model_count,
    estimate_complexity,
    select_models,
)
from .reality_advisor import RealityAdvisor
from .knowledge_core import (
    AskResult,
    get_core,
    pick_thinking_model,
    _prompt_strategy_for_tier,
    derive_knowledge_gaps,
    suggested_next_actions,
    _compose_answer,
    _compose_draft_answer,
    _aggregate_confidence,
    _derive_snippet,
    _derive_candidate_angles,
    _derive_open_questions,
    _derive_key_tradeoffs,
    _run_acceptance_check,
    AnswerCitation,
    tokenize,
    STOPWORDS,
)


def orchestrated_ask(
    *,
    tenant_id: str,
    question: str,
    language: str = "zh-CN",
    mode: Literal["simple", "professional"] = "simple",
    model_tier: Literal["flagship", "mid", "basic", "insufficient"] = "flagship",
    actor: str = "user",
    answer_mode: Literal["scaffold", "draft", "final"] = "scaffold",
    task_contract: dict[str, Any] | None = None,
    run_id: str | None = None,
    use_reality_advisor: bool = True,
    coaching_session_id: str | None = None,
    coach_turn: bool = False,
    user_confidence_check: float | None = None,
    decision_log_id: str | None = None,
    evidence_storage: Any | None = None,
    evidence_search_runner: Any = None,
) -> dict[str, Any]:
    """Orchestrated ask — multi-step pipeline with role isolation.

    Unlike the direct `core.ask()`, this version:
    1. Reads context anchor and active rules before processing
    2. Applies rules as pre-conditions on the response
    3. Runs zero-context audit on the output
    4. Returns richer metadata about which steps ran

    Coach-turn extensions (R1.9):
        When ``coach_turn=True`` the orchestrator additionally attaches
        ``expert_gap``, ``skill_chain``, ``next_action`` and
        ``session_state`` to the response. ``coaching_session_id`` is
        consulted only to look up the current session state — the
        orchestrator does **not** persist transitions here; that is the
        responsibility of the ``/api/v2/coach/turn`` endpoint (task 2.13)
        once it composes the full coach payload.

        For non-coach callers the new parameters are no-ops and the
        response keeps the historical shape (back-compat preserved).

    Active Evidence Gathering wiring (Task 3.14, R6.3, R6.4, R6.6):
        When ``coach_turn=True`` and the verifier reports
        ``confidence_band="insufficient"``, the orchestrator opens an
        :class:`GatheringTask` seeded with the user's claim and
        dispatches an ``expert_search`` to fill the gap (R6.1, R6.2).
        The response surfaces ``evidence_gathering`` (the task id +
        state) and ``verdict_allowed`` (``False`` while any linked task
        is not ``APPROVED`` per R6.3 / R11.4). The session transitions
        to ``awaiting_evidence`` via the snapshot ``next_action``
        decision rule (the persistence happens in the
        ``/api/v2/coach/turn`` endpoint per Task 2.13).
    """

    from .trace import finish_run, record_acceptance_check, record_audit_result, record_step, start_run

    core = get_core()
    run_id = run_id or start_run(
        tenant_id=tenant_id,
        user_id=actor,
        entrypoint="orchestrate_ask",
        input_value=question,
        metadata={
            "language": language,
            "mode": mode,
            "model_tier": model_tier,
            "answer_mode": answer_mode,
        },
    )
    steps_log: list[dict[str, str]] = []

    # --- Step 1: Load Context Anchor ---
    anchor = get_current_anchor(tenant_id)
    effective_contract = task_contract
    if not effective_contract and anchor:
        effective_contract = anchor.to_task_contract()
        steps_log.append({"step": "load_anchor", "status": "applied", "goal": anchor.goal[:60]})
        record_step(
            run_id=run_id,
            step_type="load_anchor",
            input_value=tenant_id,
            output_value={"anchor_id": anchor.id, "version": anchor.version},
            metadata={"applied": True},
        )
    else:
        steps_log.append({"step": "load_anchor", "status": "skipped"})
        record_step(run_id=run_id, step_type="load_anchor", status="skipped", input_value=tenant_id)

    # --- Step 2: Load Active Rules ---
    rules = get_active_rules(tenant_id)
    rules_applied: list[str] = []
    if rules:
        steps_log.append({"step": "load_rules", "status": "loaded", "count": str(len(rules))})
    else:
        steps_log.append({"step": "load_rules", "status": "none"})
    record_step(
        run_id=run_id,
        step_type="load_rules",
        status="completed",
        input_value=tenant_id,
        output_value=[rule.id for rule in rules],
        metadata={"count": len(rules)},
    )

    # --- Step 3: Classify (thinking model selection via Skill registry) ---
    # When use_reality_advisor=True, the RealityAdvisor handles Skill routing
    # internally, so we use its output instead of the existing routing logic.
    advisor_response = None
    advisor_context_data: dict[str, Any] | None = None
    full_models: list[Any] = []
    user_level: str | None = None

    if use_reality_advisor:
        # Use RealityAdvisor for hybrid reasoning
        advisor = RealityAdvisor()
        advisor_response = advisor.advise(
            tenant_id=tenant_id,
            question=question,
            language=language,
            run_id=run_id,
        )

        # Extract thinking model info from advisor's skill_framework
        advisor_model_ids = advisor_response.skill_framework.get("model_ids", [])
        advisor_labels = advisor_response.skill_framework.get("labels", [])
        if advisor_model_ids:
            thinking = {
                "id": advisor_model_ids[0],
                "label_zh": advisor_labels[0] if advisor_labels else advisor_model_ids[0],
                "label_en": advisor_labels[0] if advisor_labels else advisor_model_ids[0],
            }
        else:
            thinking = pick_thinking_model(question, language)

        # When using RealityAdvisor, the advisor handles Skill routing internally.
        # Set full_models and user_level for downstream prompt composition.
        full_models = []
        user_level = advisor_response.skill_framework.get("complexity")

        # Build advisor_context_data for the response
        advisor_context_data = {
            "user_level": user_level,
            "strategy_used": advisor_response.strategy_used,
            "strategy_reason": advisor_response.strategy_reason,
            "depth_boost": advisor_response.skill_framework.get("retrieval_depth_boost", 0),
        }

        steps_log.append({
            "step": "classify",
            "status": "reality_advisor",
            "strategy_used": advisor_response.strategy_used,
            "models": advisor_model_ids,
            "complexity": advisor_response.skill_framework.get("complexity", "moderate"),
        })
        record_step(
            run_id=run_id,
            step_type="thinking_route",
            input_value=question,
            output_value=advisor_model_ids,
            metadata={
                "router": "reality_advisor",
                "strategy_used": advisor_response.strategy_used,
                "strategy_reason": advisor_response.strategy_reason,
                "complexity": advisor_response.skill_framework.get("complexity", "moderate"),
            },
        )
    else:
        # Existing behavior: Skill-based router or legacy fallback
        user_level = None
        # Try to get user level from profile
        try:
            from .reality_layers import UserProfile, ensure_layers_schema
            import json as _json
            with core._lock, core._connect() as db:
                ensure_layers_schema(db)
                profile_row = db.execute(
                    "select data_json from user_profiles where tenant_id = ?",
                    (tenant_id,),
                ).fetchone()
                if profile_row:
                    profile_data = _json.loads(profile_row["data_json"])
                    user_level = profile_data.get("level")
        except Exception:
            pass

        # Select thinking models using the Skill-based router
        selected_models = select_models(
            question=question,
            language=language,
            user_level=user_level,
        )

        # Load full model content for prompt composition
        full_models = []
        for meta in selected_models:
            full = get_model_full(meta.id)
            if full:
                full_models.append(full)

        # Fall back to legacy pick_thinking_model if no Skill models available
        if full_models:
            thinking = {"id": full_models[0].meta.id, "label_zh": full_models[0].meta.label_zh, "label_en": full_models[0].meta.label_en}
            steps_log.append({
                "step": "classify",
                "status": "skill_router",
                "models": [m.meta.id for m in full_models],
                "complexity": estimate_complexity(question),
                "user_level": user_level or "intermediate",
            })
            record_step(
                run_id=run_id,
                step_type="thinking_route",
                input_value=question,
                output_value=[m.meta.id for m in full_models],
                metadata={"router": "skill", "complexity": estimate_complexity(question)},
            )
        else:
            thinking = pick_thinking_model(question, language)
            steps_log.append({"step": "classify", "status": "legacy_fallback", "model": thinking["id"]})
            record_step(
                run_id=run_id,
                step_type="thinking_route",
                input_value=question,
                output_value=thinking["id"],
                metadata={"router": "legacy"},
            )

    # --- Step 4: Retrieve ---
    candidates = core.search(tenant_id=tenant_id, query=question, limit=6)
    citations: list[AnswerCitation] = []
    for item, relevance in candidates[:4]:
        snippet = evidence_warning(language) if item.security_flags else _derive_snippet(item.body, question)
        citations.append(AnswerCitation(
            item_id=item.id, title=item.title, snippet=snippet,
            url=item.source_url, relevance=relevance, quality=item.quality_score,
            security_flags=item.security_flags, content_role="evidence",
        ))
    steps_log.append({"step": "retrieve", "status": "done", "citations": str(len(citations))})
    record_step(
        run_id=run_id,
        step_type="retrieval",
        input_value=question,
        output_value=[citation.item_id for citation in citations],
        metadata={
            "candidate_count": len(candidates),
            "citation_count": len(citations),
            "flagged_citations": sum(1 for citation in citations if citation.security_flags),
        },
    )

    # --- Step 5: Generate ---
    aggregate = _aggregate_confidence(citations)
    confidence_band: Literal["solid", "probable", "uncertain", "insufficient"]
    if aggregate >= 0.8 and len(citations) >= 2:
        confidence_band = "solid"
    elif aggregate >= 0.55:
        confidence_band = "probable"
    elif aggregate >= 0.3:
        confidence_band = "uncertain"
    else:
        confidence_band = "insufficient"

    knowledge_gaps: list[str] = []
    next_actions: list[str] = []
    if confidence_band == "insufficient":
        knowledge_gaps = derive_knowledge_gaps(question)
        next_actions = suggested_next_actions(question, language)

    # Apply rules as pre-conditions
    for rule in rules:
        rule_lower = rule.rule_text.lower()
        question_lower = question.lower()
        # Simple rule matching: if rule mentions keywords in the question
        rule_tokens = {t for t in tokenize(rule.rule_text) if t not in STOPWORDS and len(t) > 1}
        question_tokens = set(tokenize(question))
        if rule_tokens & question_tokens:
            rules_applied.append(rule.rule_text)
            increment_trigger(tenant_id, rule.id)

    candidate_angles = _derive_candidate_angles(question, thinking, language)
    open_questions = _derive_open_questions(question, citations, language)
    key_tradeoffs = _derive_key_tradeoffs(question, language)

    # Compose level-aware structured prompt (for LLM calls when generator is configured)
    structured_prompt = ""
    if full_models:
        user_constraints_list = effective_contract.get("constraints", []) if effective_contract else []
        structured_prompt = compose_model_prompt(
            question=question,
            models=full_models,
            user_level=user_level,
            language=language,
            user_constraints=user_constraints_list,
        )

    # Try LLM generation if generator slot is configured and answer_mode != scaffold
    llm_answer: str | None = None
    if answer_mode != "scaffold" and structured_prompt and confidence_band != "insufficient":
        try:
            from .model_registry import call_model
            llm_answer = call_model(
                "generator",
                prompt=structured_prompt,
                temperature=0.3,
                max_tokens=2000,
                timeout=20,
                run_id=run_id,
            )
        except Exception:
            pass

    if answer_mode == "scaffold":
        answer = ""
    elif llm_answer:
        # LLM generated answer — mark as draft if in draft mode
        if answer_mode == "draft":
            draft_label = "【草稿，需人工审查】" if language == "zh-CN" else "[DRAFT — requires human review]"
            answer = draft_label + "\n" + llm_answer
        else:
            answer = llm_answer
    elif answer_mode == "draft":
        answer = _compose_draft_answer(
            question=question, thinking=thinking, language=language,
            citations=citations, confidence_band=confidence_band, gaps=knowledge_gaps,
        )
    else:
        answer = _compose_answer(
            question=question, thinking=thinking, language=language,
            citations=citations, confidence_band=confidence_band, gaps=knowledge_gaps,
        )
    steps_log.append({
        "step": "generate",
        "status": "llm" if llm_answer else "deterministic",
        "mode": answer_mode,
        "structured_prompt_length": len(structured_prompt),
    })
    record_step(
        run_id=run_id,
        step_type="generate",
        input_value={"answer_mode": answer_mode, "citation_count": len(citations)},
        output_value={"answer_hash_source": answer, "llm_used": bool(llm_answer)},
        model_slot="generator" if llm_answer else None,
        metadata={"llm_used": bool(llm_answer), "answer_mode": answer_mode},
    )

    # --- Step 6: Verify (zero-context audit) ---
    acceptance_check = _run_acceptance_check(
        answer=answer, citations=citations, confidence_band=confidence_band,
        task_contract=effective_contract, language=language, run_id=run_id,
    )
    record_acceptance_check(
        run_id=run_id,
        step_id=None,
        verdict=str(acceptance_check.get("verdict", "unknown")),
        verifier_used=bool(acceptance_check.get("verifier_used")),
        input_value={"citation_ids": [citation.item_id for citation in citations]},
        output_value=acceptance_check,
        metadata={
            "truthfulness_passed": acceptance_check.get("truthfulness", {}).get("passed"),
            "goal_fit_passed": acceptance_check.get("goal_fit", {}).get("passed"),
        },
    )

    audit_result = None
    if answer and answer_mode != "scaffold":
        audit_result = zero_context_audit(
            output_text=answer, output_type="answer", language=language, run_id=run_id,
        )
        steps_log.append({"step": "audit", "status": "done", "passed": str(audit_result.passed)})
        record_audit_result(
            run_id=run_id,
            passed=audit_result.passed,
            score=audit_result.score,
            source=audit_result.source,
            output_type=audit_result.output_type,
            input_value=answer,
            output_value=audit_result.to_dict(),
        )
    else:
        steps_log.append({"step": "audit", "status": "skipped"})

    # --- Step 6b: Coach-turn extensions (R1.9) ---
    # Compute the additional payload only when ``coach_turn=True``. Non-coach
    # callers see the historical response shape (back-compat preserved).
    coach_expert_gap: dict[str, Any] | None = None
    coach_skill_chain: dict[str, Any] | None = None
    coach_next_action: str | None = None
    coach_session_state: str | None = None
    coach_evidence_gathering: dict[str, Any] | None = None
    coach_verdict_allowed: bool | None = None
    if coach_turn:
        # Expert gap is surfaced separately so coach clients do not have to
        # reach into ``orchestration.audit_result`` (R2.3).
        if audit_result is not None and audit_result.expert_gap is not None:
            coach_expert_gap = dict(audit_result.expert_gap)
            if audit_result.rubric_applied:
                coach_expert_gap.setdefault(
                    "rubric_applied", dict(audit_result.rubric_applied)
                )

        # Skill chain pointer comes from the advisor (task 2.11). When the
        # advisor was bypassed (``use_reality_advisor=False``) we leave it
        # ``None`` rather than synthesising a value.
        if advisor_response is not None and advisor_response.skill_chain:
            coach_skill_chain = dict(advisor_response.skill_chain)

        # --- Active Evidence Gathering (Task 3.14, R6.1, R6.3, R6.4) ----
        # When verification reports insufficient_evidence in this coach
        # turn we open + dispatch a tenant-scoped gathering task and
        # surface its id + state on the response. The verdict on any
        # linked DecisionLog stays blocked until every task linked to
        # the decision reaches APPROVED (R6.3 / R11.4).
        evidence_gathering_open = False
        if confidence_band == "insufficient":
            (
                coach_evidence_gathering,
                evidence_gathering_open,
            ) = _open_and_dispatch_evidence_gathering(
                tenant_id=tenant_id,
                actor=actor,
                language=language,
                claim=question,
                coaching_session_id=coaching_session_id,
                decision_log_id=decision_log_id,
                run_id=run_id,
                evidence_storage=evidence_storage,
                evidence_search_runner=evidence_search_runner,
            )

        # ``verdict_allowed`` is computed against the linked decision so
        # callers (the coach-turn endpoint, the decision-memo publisher)
        # can refuse to publish a verdict while pending evidence
        # remains (R6.3, R11.4).
        if decision_log_id is not None:
            coach_verdict_allowed = _evidence_verdict_allowed(
                tenant_id=tenant_id,
                decision_log_id=decision_log_id,
            )
        elif coach_evidence_gathering is not None:
            # No decision log attached — the verdict gate degrades to
            # the single-task predicate so unit tests and dry-run
            # callers can still observe the closure (Property 15).
            coach_verdict_allowed = (
                coach_evidence_gathering.get("state")
                == "approved"
            )

        # Build a SessionSnapshot from what we know about this turn, then
        # fold in the persisted ``CoachingSession`` (if any) so the
        # orchestrator stays usable from tests and unit harnesses without
        # a session.
        coach_session_state, coach_next_action = _resolve_coach_session_state(
            tenant_id=tenant_id,
            coaching_session_id=coaching_session_id,
            confidence_band=confidence_band,
            skill_chain=coach_skill_chain,
            user_confidence_check=user_confidence_check,
            evidence_gathering_open=evidence_gathering_open,
        )
        steps_log.append({
            "step": "coach_turn",
            "status": "applied",
            "session_id": coaching_session_id or "",
            "next_action": coach_next_action or "",
            "session_state": coach_session_state or "",
            "evidence_gathering_task_id": (
                coach_evidence_gathering.get("task_id")
                if coach_evidence_gathering
                else ""
            ),
        })

    # --- Step 7: Record audit ---
    prompt_strategy = _prompt_strategy_for_tier(model_tier)
    audit_id = core._record_audit(
        tenant_id=tenant_id, actor=actor, action="orchestrated_ask", subject=None,
        payload={
            "question": question, "language": language, "mode": mode,
            "model_tier": model_tier, "answer_mode": answer_mode,
            "citation_count": len(citations), "confidence_band": confidence_band,
            "confidence": aggregate, "thinking_model": thinking["id"],
            "rules_applied": len(rules_applied),
            "anchor_used": bool(anchor),
            "audit_passed": audit_result.passed if audit_result else None,
        },
    )

    response = {
        "run_id": run_id,
        "question": question,
        "language": language,
        "answer": answer,
        "confidence": round(aggregate, 3),
        "confidence_band": confidence_band,
        "thinking_model": thinking["label_zh"] if language == "zh-CN" else thinking["label_en"],
        "prompt_strategy": prompt_strategy,
        "citations": [c.to_dict() for c in citations],
        "knowledge_gaps": knowledge_gaps,
        "next_actions": next_actions,
        "audit_id": audit_id,
        "answer_mode": answer_mode,
        "candidate_angles": candidate_angles,
        "open_questions": open_questions,
        "key_tradeoffs": key_tradeoffs,
        "acceptance_check": acceptance_check,
        # RealityAdvisor fields (populated when use_reality_advisor=True)
        "advisor_context": advisor_context_data,
        "skill_framework": advisor_response.skill_framework if advisor_response else None,
        "contradictions": advisor_response.contradictions if advisor_response else None,
        "strategy_used": advisor_response.strategy_used if advisor_response else None,
        # Orchestrator-specific metadata
        "orchestration": {
            "steps": steps_log,
            "rules_applied": rules_applied,
            "anchor_goal": anchor.goal if anchor else None,
            "audit_result": audit_result.to_dict() if audit_result else None,
        },
    }
    if coach_turn:
        # Additive coach-turn fields. Non-coach callers never see these
        # keys so legacy clients (`/api/v2/orchestrate/ask`) keep their
        # historical response shape (R1.9).
        response["coach_turn"] = True
        response["coaching_session_id"] = coaching_session_id
        response["expert_gap"] = coach_expert_gap
        response["skill_chain"] = coach_skill_chain
        response["next_action"] = coach_next_action
        response["session_state"] = coach_session_state
        # Active Evidence Gathering surface (Task 3.14, R6.3, R6.4, R6.6).
        response["evidence_gathering"] = coach_evidence_gathering
        response["verdict_allowed"] = coach_verdict_allowed
        if decision_log_id is not None:
            response["decision_log_id"] = decision_log_id
        if user_confidence_check is not None:
            response["user_confidence_check"] = float(user_confidence_check)
    finish_run(
        run_id,
        output_value={
            "audit_id": audit_id,
            "confidence_band": confidence_band,
            "citation_count": len(citations),
            "acceptance_verdict": acceptance_check.get("verdict"),
        },
    )
    return response


# ---------------------------------------------------------------------------
# Coach-turn helpers (R1.9, R1.5)
# ---------------------------------------------------------------------------


def _resolve_coach_session_state(
    *,
    tenant_id: str,
    coaching_session_id: str | None,
    confidence_band: Literal["solid", "probable", "uncertain", "insufficient"],
    skill_chain: dict[str, Any] | None,
    user_confidence_check: float | None,
    evidence_gathering_open: bool = False,
) -> tuple[str | None, str | None]:
    """Return ``(session_state, next_action)`` for a coach-turn response.

    The orchestrator does **not** persist transitions or mutate the
    aggregate here — that is the responsibility of the
    ``/api/v2/coach/turn`` endpoint (task 2.13). This helper only computes
    the read-only snapshot the response advertises so coach clients can
    render the next prompt and route the user to the right surface
    (R1.3, R1.5, R1.8).

    When the session id is missing or the repo cannot resolve it
    (cross-tenant, archived, or freshly created in the same request) we
    still return a best-effort ``next_action`` derived from
    :class:`SessionSnapshot` so unit tests and the dry-run path can
    exercise the pipeline without first creating a session row.

    ``evidence_gathering_open`` reflects whether Task 3.14's dispatch
    actually opened a ``GatheringTask`` for this turn. Without a
    persisted task the snapshot would be unable to distinguish "no
    gathering task" from "gathering task in flight" — both yield
    ``next_action == "learn"`` instead of ``awaiting_evidence`` (R1.5).
    """

    from . import calibration as calibration_mod
    from . import feature_flags
    from .coaching_session import (
        CoachingSessionRepo,
        SessionSnapshot,
        decide_next_action,
    )
    from .knowledge_core import default_core_path

    # Pull the tenant's calibration history so the snapshot can bias the
    # next action toward ``practice`` when the calibration score is below
    # the configured threshold (R4.5). Cold start (no resolved records)
    # leaves ``calibration_score=0.0`` which already biases toward
    # practice — exactly what R4.5 wants for a brand-new user.
    calibration_score = 0.0
    calibration_records_recent = 0
    try:
        from .knowledge_core import get_core

        core = get_core()
        records = calibration_mod.list_calibration_records(
            core=core, tenant_id=tenant_id
        )
        calibration_score = calibration_mod.calibration_score(records)
        # ``calibration_records_recent`` counts *resolved* reviews — the
        # decision table only triggers calibration practice when the
        # tenant has fewer than 10 resolved data points to learn from.
        calibration_records_recent = sum(
            1 for r in records if r.brier_score is not None
        )
    except Exception:
        # No core / no rows → leave the cold-start defaults in place.
        pass

    snapshot = SessionSnapshot(
        insufficient_evidence=confidence_band == "insufficient",
        evidence_gathering_open=evidence_gathering_open
        or confidence_band == "insufficient",
        calibration_score=calibration_score,
        calibration_threshold=feature_flags.calibration_threshold(),
        calibration_records_recent=calibration_records_recent,
        skill_chain_step_exit_satisfied=bool(
            skill_chain and skill_chain.get("exit_satisfied")
        ),
        skill_chain_has_next_step=bool(skill_chain),
    )

    state: str | None = None
    if coaching_session_id:
        try:
            repo = CoachingSessionRepo(path=default_core_path())
            session = repo.get(tenant_id=tenant_id, session_id=coaching_session_id)
        except Exception:
            session = None
        if session is not None:
            state = session.state

    next_action = decide_next_action(snapshot)
    if state is None:
        # No persisted session → mirror the next_action onto the state
        # field so coach clients still see a coherent view. ``learn`` is a
        # synonym for ``active`` here (R1.5).
        state = "awaiting_evidence" if next_action == "awaiting_evidence" else "active"
    return state, next_action


# ---------------------------------------------------------------------------
# Active Evidence Gathering helpers (Task 3.14, R6.1, R6.3, R6.4, R6.6)
# ---------------------------------------------------------------------------


def _open_and_dispatch_evidence_gathering(
    *,
    tenant_id: str,
    actor: str,
    language: str,
    claim: str,
    coaching_session_id: str | None,
    decision_log_id: str | None,
    run_id: str | None,
    evidence_storage: Any | None,
    evidence_search_runner: Any,
) -> tuple[dict[str, Any] | None, bool]:
    """Open + dispatch a :class:`GatheringTask` for an insufficient turn.

    R6.1 / R6.2: every coach turn whose verifier reports
    ``insufficient_evidence=true`` opens exactly one
    ``evidence_gathering_tasks`` row and dispatches an ``expert_search``
    seeded with the claim. Each result lands in ``pending_knowledge``
    with the documented R11.1 defaults via
    :func:`evidence_gathering.dispatch_search`.

    The function is intentionally robust to missing storage in unit
    harnesses: when ``evidence_storage`` is ``None`` we fall back to
    :func:`apps.api.storage.get_storage`. Any exception during dispatch
    (e.g. a search runner that errors out, a misconfigured pending
    sink) keeps the task in ``INSUFFICIENT`` and returns its id so the
    caller can still render ``next_action="awaiting_evidence"`` and
    block the verdict (R6.3 / R11.4 — fail-closed semantics).

    Returns
    -------
    ``(payload, opened)`` — a dict suitable for the response
    ``evidence_gathering`` field (with ``task_id``, ``state``, claim
    and pending-knowledge ids), and a ``opened`` boolean indicating
    whether a task was successfully created. ``payload=None`` /
    ``opened=False`` when the open call itself failed (e.g. the
    feature flags are off or the schema is missing).
    """

    from .evidence_gathering import (
        GatheringState,
        dispatch_search,
        open_task,
    )
    from .knowledge_core import get_core

    try:
        core = get_core()
    except Exception:
        return None, False

    try:
        task = open_task(
            core=core,
            tenant_id=tenant_id,
            claim=claim,
            session_id=coaching_session_id,
            coach_turn_id=run_id,
            decision_log_id=decision_log_id,
            actor=actor,
        )
    except Exception:
        # Open failed (schema missing, empty claim) — fail-closed by
        # signalling no task and letting the snapshot still flag
        # ``awaiting_evidence`` because ``confidence_band="insufficient"``.
        return None, False

    payload: dict[str, Any] = {
        "task_id": task.id,
        "state": task.state.value,
        "claim": task.claim,
        "session_id": task.session_id,
        "coach_turn_id": task.coach_turn_id,
        "decision_log_id": task.decision_log_id,
        "pending_knowledge_ids": list(task.pending_knowledge_ids),
        "dispatch_status": "skipped",
    }

    storage = evidence_storage
    if storage is None:
        try:
            from ..storage import get_storage  # type: ignore[import-not-found]

            storage = get_storage()
        except Exception:
            storage = None

    if storage is None:
        # No pending sink available → leave the task in INSUFFICIENT.
        # ``verdict_allowed_for_decision`` will still return ``False``
        # because the task exists and is non-approved (R6.3).
        payload["dispatch_status"] = "no_storage"
        return payload, True

    try:
        final_task, pending_records = dispatch_search(
            core=core,
            storage=storage,
            task=task,
            actor=actor,
            language=language,
            search_runner=evidence_search_runner,
        )
        payload.update(
            {
                "task_id": final_task.id,
                "state": final_task.state.value,
                "pending_knowledge_ids": [rec.id for rec in pending_records],
                "dispatch_status": "dispatched",
            }
        )
    except Exception:
        # Dispatch failed — task stays at whatever state ``open_task``
        # left it (INSUFFICIENT) and the verdict remains blocked.
        payload["dispatch_status"] = "failed"

    return payload, True


def _evidence_verdict_allowed(
    *,
    tenant_id: str,
    decision_log_id: str,
) -> bool:
    """Tenant-scoped verdict gate for a decision log (R6.3, R11.4).

    Wraps :func:`evidence_gathering.verdict_allowed_for_decision` so the
    orchestrator stays decoupled from the storage initialisation
    boilerplate. Returns ``True`` when no gathering task is linked to
    the decision (no loop ever opened) or when every linked task has
    reached :attr:`GatheringState.APPROVED`. Any other state — including
    ``REJECTED`` (R6.6) and ``CLOSED`` — keeps the verdict blocked.
    """

    from .evidence_gathering import verdict_allowed_for_decision
    from .knowledge_core import get_core

    try:
        core = get_core()
    except Exception:
        # Without a core we cannot prove the loop is closed; default to
        # blocked so callers fail-closed (R6.3 fail-closed semantics).
        return False
    try:
        return verdict_allowed_for_decision(
            core=core, tenant_id=tenant_id, decision_log_id=decision_log_id
        )
    except Exception:
        return False
