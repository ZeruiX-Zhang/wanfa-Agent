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
) -> dict[str, Any]:
    """Orchestrated ask — multi-step pipeline with role isolation.

    Unlike the direct `core.ask()`, this version:
    1. Reads context anchor and active rules before processing
    2. Applies rules as pre-conditions on the response
    3. Runs zero-context audit on the output
    4. Returns richer metadata about which steps ran
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
