"""Reality Advisor — hybrid reasoning engine for Reality OS.

Combines deterministic Skill routing with LLM generation to produce
context-aware advice. The flow:

1. Build user context (profile, anchor, mastery, history)
2. Detect domain repetition → boost retrieval depth
3. Execute Skill routing → structured framework
4. Call LLM with framework + user profile injected
5. Detect contradictions between Skill output and LLM output
6. Format output based on user level
7. Record strategy selection to trace
8. Record query to query_history table

Design principles:
- Skill framework always runs first (deterministic, no LLM needed)
- LLM generation is optional and gracefully degrades
- User profile personalizes both the prompt and the output format
- All strategy decisions are traced for observability
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import uuid4

from .knowledge_core import get_core, _utc_now_iso, _new_id, tokenize, STOPWORDS


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class AdvisorContext:
    """User context assembled from profile, anchor, mastery, and history."""

    user_level: str | None
    user_constraints: list[str]
    error_patterns: list[str]
    context_anchor_goal: str | None
    context_anchor_constraints: list[str]
    concept_mastery: dict[str, float]  # concept_id -> mastery_score
    recent_domains: list[str]  # recent query domains
    retrieval_depth_boost: int  # boost based on domain repetition


@dataclass
class AdvisorResponse:
    """Response from the hybrid reasoning pipeline."""

    skill_framework: dict[str, Any]  # Skill router structured framework
    llm_advice: str | None  # LLM-generated advice
    contradictions: list[dict[str, str]]  # contradiction points
    action_guide: list[str] | None  # step-by-step guide (beginner)
    glossary: dict[str, str] | None  # term explanations (beginner)
    strategy_used: str  # reasoning strategy name
    strategy_reason: str  # reason for strategy selection
    # R3.2 — additive: optional Skill Chain pointer for the active turn.
    # ``None`` when the chain registry has no qualifying chain or the
    # caller did not request chain selection (back-compat preserved).
    skill_chain: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# RealityAdvisor
# ---------------------------------------------------------------------------


class RealityAdvisor:
    """Hybrid reasoning engine combining Skill frameworks with LLM generation."""

    def advise(
        self,
        *,
        tenant_id: str,
        question: str,
        language: str = "zh-CN",
        run_id: str | None = None,
    ) -> AdvisorResponse:
        """Execute hybrid reasoning and return context-aware advice.

        Flow:
        1. Build user context
        2. Detect domain repetition
        3. Execute Skill routing
        4. Call LLM with framework + profile
        5. Detect contradictions
        6. Format for user level
        7. Record to trace
        8. Record to query_history
        """
        from .trace import record_step

        # Step 1: Build user context
        context = self._build_context(tenant_id)

        # Step 2: Detect domain repetition and update boost
        depth_boost = self._detect_domain_repetition(tenant_id, question)
        context.retrieval_depth_boost = depth_boost

        # Step 3: Execute Skill routing to get structured framework
        skill_framework = self._execute_skill_routing(question, language, context.user_level)

        # Determine strategy
        strategy_used, strategy_reason = self._select_strategy(context, skill_framework)

        # R3.2 — Additive: select an active Skill Chain (if registry has one).
        skill_chain_payload = self._select_skill_chain(skill_framework)

        # Step 4: Call LLM with framework + user profile
        llm_advice = self._call_llm(
            question=question,
            language=language,
            context=context,
            skill_framework=skill_framework,
            run_id=run_id,
        )

        # Step 5: Detect contradictions
        contradictions = self._detect_contradictions(skill_framework, llm_advice or "")

        # Build initial response
        response = AdvisorResponse(
            skill_framework=skill_framework,
            llm_advice=llm_advice,
            contradictions=contradictions,
            action_guide=None,
            glossary=None,
            strategy_used=strategy_used,
            strategy_reason=strategy_reason,
            skill_chain=skill_chain_payload,
        )

        # Step 6: Format for user level
        response = self._format_for_level(
            response=response,
            user_level=context.user_level or "intermediate",
            language=language,
        )

        # Step 7: Record strategy selection to trace
        record_step(
            run_id=run_id,
            step_type="reality_advisor_strategy",
            status="completed",
            input_value={
                "question_length": len(question),
                "user_level": context.user_level,
                "depth_boost": depth_boost,
            },
            output_value={
                "strategy_used": strategy_used,
                "strategy_reason": strategy_reason,
                "has_llm_advice": llm_advice is not None,
                "contradiction_count": len(contradictions),
            },
            metadata={
                "strategy_used": strategy_used,
                "user_level": context.user_level or "intermediate",
                "depth_boost": depth_boost,
                "skill_model_ids": skill_framework.get("model_ids", []),
            },
        )

        # Step 8: Record query to query_history
        self._record_query_history(
            tenant_id=tenant_id,
            question=question,
            skill_framework=skill_framework,
            strategy_used=strategy_used,
        )

        return response

    # ------------------------------------------------------------------
    # Context building
    # ------------------------------------------------------------------

    def _build_context(self, tenant_id: str) -> AdvisorContext:
        """Build user context from profile, anchor, learning signals, and history."""
        user_level: str | None = None
        user_constraints: list[str] = []
        error_patterns: list[str] = []
        context_anchor_goal: str | None = None
        context_anchor_constraints: list[str] = []
        concept_mastery: dict[str, float] = {}
        recent_domains: list[str] = []

        core = get_core()

        # Read user profile
        try:
            from .reality_layers import ensure_layers_schema

            with core._lock, core._connect() as db:
                ensure_layers_schema(db)
                profile_row = db.execute(
                    "select data_json from user_profiles where tenant_id = ?",
                    (tenant_id,),
                ).fetchone()
                if profile_row:
                    profile_data = json.loads(profile_row["data_json"])
                    user_level = profile_data.get("level")
                    user_constraints = profile_data.get("constraints", [])
                    error_patterns = profile_data.get("error_patterns", [])
        except Exception:
            pass

        # Read context anchor
        try:
            from .context_anchor import get_current_anchor

            anchor = get_current_anchor(tenant_id)
            if anchor:
                context_anchor_goal = anchor.goal
                context_anchor_constraints = (
                    [anchor.current_blocker] if anchor.current_blocker else []
                )
        except Exception:
            pass

        # Read learning signals for concept mastery
        try:
            with core._lock, core._connect() as db:
                rows = db.execute(
                    """
                    select concept_id, count(*) as signal_count
                    from learning_signals
                    where tenant_id = ?
                    group by concept_id
                    """,
                    (tenant_id,),
                ).fetchall()
                for row in rows:
                    # Simple mastery heuristic: more signals = higher mastery
                    # Cap at 1.0, each signal adds 0.1
                    concept_id = row["concept_id"]
                    signal_count = row["signal_count"]
                    concept_mastery[concept_id] = min(1.0, signal_count * 0.1)
        except Exception:
            pass

        # Read recent query domains from query_history
        try:
            with core._lock, core._connect() as db:
                history_rows = db.execute(
                    """
                    select domain_concepts from query_history
                    where tenant_id = ?
                    order by created_at desc
                    limit 10
                    """,
                    (tenant_id,),
                ).fetchall()
                for row in history_rows:
                    try:
                        domains = json.loads(row["domain_concepts"])
                        if isinstance(domains, list):
                            recent_domains.extend(domains)
                    except (json.JSONDecodeError, TypeError):
                        pass
        except Exception:
            pass

        return AdvisorContext(
            user_level=user_level,
            user_constraints=user_constraints,
            error_patterns=error_patterns,
            context_anchor_goal=context_anchor_goal,
            context_anchor_constraints=context_anchor_constraints,
            concept_mastery=concept_mastery,
            recent_domains=recent_domains,
            retrieval_depth_boost=0,
        )

    # ------------------------------------------------------------------
    # Domain repetition detection
    # ------------------------------------------------------------------

    def _detect_domain_repetition(self, tenant_id: str, question: str) -> int:
        """Detect consecutive same-domain queries and return depth boost value.

        If the user has queried the same domain >= 3 times recently,
        boost retrieval depth (top_k increase).
        """
        core = get_core()

        # Extract domain concepts from the current question
        current_tokens = set(tokenize(question)) - STOPWORDS
        if not current_tokens:
            return 0

        try:
            with core._lock, core._connect() as db:
                rows = db.execute(
                    """
                    select domain_concepts from query_history
                    where tenant_id = ?
                    order by created_at desc
                    limit 10
                    """,
                    (tenant_id,),
                ).fetchall()
        except Exception:
            return 0

        if not rows:
            return 0

        # Count consecutive queries with overlapping domain concepts
        consecutive_count = 0
        for row in rows:
            try:
                past_domains = json.loads(row["domain_concepts"])
                if not isinstance(past_domains, list):
                    break
                past_tokens = set()
                for domain in past_domains:
                    past_tokens.update(tokenize(domain))
                past_tokens -= STOPWORDS

                # Check overlap between current question tokens and past domains
                if current_tokens & past_tokens:
                    consecutive_count += 1
                else:
                    break  # Stop at first non-matching query
            except (json.JSONDecodeError, TypeError):
                break

        # Return depth boost: 0 if < 3, otherwise boost by (count - 2)
        if consecutive_count >= 3:
            return min(consecutive_count - 2, 4)  # Cap boost at 4
        return 0

    # ------------------------------------------------------------------
    # Skill routing
    # ------------------------------------------------------------------

    def _execute_skill_routing(
        self,
        question: str,
        language: str,
        user_level: str | None,
    ) -> dict[str, Any]:
        """Execute Skill routing to get a structured analysis framework.

        Uses the thinking_models router to select and compose models.
        """
        from .thinking_models import get_model_full, get_registry
        from .thinking_models.router import (
            compose_model_prompt,
            estimate_complexity,
            select_models,
        )

        selected_models = select_models(
            question=question,
            language=language,
            user_level=user_level,
        )

        # Load full model content
        full_models = []
        for meta in selected_models:
            full = get_model_full(meta.id)
            if full:
                full_models.append(full)

        if not full_models:
            # Fallback: return a minimal framework
            return {
                "model_ids": [],
                "labels": [],
                "complexity": estimate_complexity(question),
                "body": "",
                "structured_prompt": "",
            }

        # Compose the structured prompt (this is the framework)
        structured_prompt = compose_model_prompt(
            question=question,
            models=full_models,
            user_level=user_level,
            language=language,
        )

        return {
            "model_ids": [m.meta.id for m in full_models],
            "labels": [
                m.meta.label_zh if language == "zh-CN" else m.meta.label_en
                for m in full_models
            ],
            "complexity": estimate_complexity(question),
            "body": full_models[0].body if full_models else "",
            "structured_prompt": structured_prompt,
        }

    # ------------------------------------------------------------------
    # LLM call
    # ------------------------------------------------------------------

    def _call_llm(
        self,
        *,
        question: str,
        language: str,
        context: AdvisorContext,
        skill_framework: dict[str, Any],
        run_id: str | None,
    ) -> str | None:
        """Call LLM with Skill framework + user profile injected into prompt.

        Returns None if LLM is not configured or call fails.
        """
        from .model_registry import call_model

        structured_prompt = skill_framework.get("structured_prompt", "")
        if not structured_prompt:
            return None

        # Inject user profile into the prompt
        profile_section = self._compose_profile_section(context, language)
        anchor_section = self._compose_anchor_section(context, language)

        # Build the full prompt
        full_prompt = structured_prompt

        if profile_section:
            full_prompt += f"\n\n{profile_section}"

        if anchor_section:
            full_prompt += f"\n\n{anchor_section}"

        try:
            result = call_model(
                "generator",
                prompt=full_prompt,
                temperature=0.3,
                max_tokens=2000,
                timeout=20,
                run_id=run_id,
            )
            return result
        except Exception:
            return None

    def _compose_profile_section(self, context: AdvisorContext, language: str) -> str:
        """Compose user profile section for LLM prompt injection."""
        parts: list[str] = []

        if language == "zh-CN":
            if context.user_level:
                parts.append(f"用户水平：{context.user_level}")
            if context.user_constraints:
                constraints_str = "、".join(context.user_constraints[:5])
                parts.append(f"用户约束：{constraints_str}")
            if context.error_patterns:
                patterns_str = "、".join(context.error_patterns[:3])
                parts.append(f"用户常见错误模式：{patterns_str}")
            if parts:
                return "## 用户画像\n" + "\n".join(f"- {p}" for p in parts)
        else:
            if context.user_level:
                parts.append(f"User level: {context.user_level}")
            if context.user_constraints:
                constraints_str = ", ".join(context.user_constraints[:5])
                parts.append(f"User constraints: {constraints_str}")
            if context.error_patterns:
                patterns_str = ", ".join(context.error_patterns[:3])
                parts.append(f"Common error patterns: {patterns_str}")
            if parts:
                return "## User Profile\n" + "\n".join(f"- {p}" for p in parts)

        return ""

    def _compose_anchor_section(self, context: AdvisorContext, language: str) -> str:
        """Compose context anchor section for LLM prompt injection."""
        if not context.context_anchor_goal:
            return ""

        if language == "zh-CN":
            section = f"## 当前目标（Context Anchor）\n- 目标：{context.context_anchor_goal}"
            if context.context_anchor_constraints:
                constraints_str = "、".join(context.context_anchor_constraints)
                section += f"\n- 当前阻碍：{constraints_str}"
            return section
        else:
            section = f"## Current Goal (Context Anchor)\n- Goal: {context.context_anchor_goal}"
            if context.context_anchor_constraints:
                constraints_str = ", ".join(context.context_anchor_constraints)
                section += f"\n- Current blockers: {constraints_str}"
            return section

    # ------------------------------------------------------------------
    # Contradiction detection
    # ------------------------------------------------------------------

    def _detect_contradictions(
        self, skill_output: dict[str, Any], llm_output: str
    ) -> list[dict[str, str]]:
        """Detect contradictions between Skill framework and LLM advice.

        Uses simple keyword/phrase matching to identify when the LLM output
        contradicts key assertions from the Skill framework.
        """
        if not llm_output:
            return []

        contradictions: list[dict[str, str]] = []
        skill_body = skill_output.get("body", "")
        if not skill_body:
            return []

        # Extract key assertions from skill body (lines starting with - or *)
        skill_assertions: list[str] = []
        for line in skill_body.split("\n"):
            stripped = line.strip()
            if stripped.startswith(("- ", "* ", "1.", "2.", "3.", "4.", "5.")):
                # Clean the assertion
                clean = re.sub(r"^[-*\d.]+\s*", "", stripped).strip()
                if len(clean) > 10:
                    skill_assertions.append(clean)

        if not skill_assertions:
            return []

        # Contradiction patterns: negation words near skill keywords
        _NEGATION_ZH = ("不", "没有", "无法", "不应", "不需要", "不必", "不是", "并非")
        _NEGATION_EN = ("not", "don't", "doesn't", "shouldn't", "cannot", "never", "no need")

        llm_lower = llm_output.lower()

        for assertion in skill_assertions[:10]:  # Check top 10 assertions
            # Extract key tokens from the assertion
            assertion_tokens = set(tokenize(assertion)) - STOPWORDS
            significant_tokens = {t for t in assertion_tokens if len(t) > 1}

            if not significant_tokens:
                continue

            # Check if LLM output contains negation near these tokens
            for token in list(significant_tokens)[:5]:
                if token.lower() not in llm_lower:
                    continue

                # Find the token in LLM output and check surrounding context
                token_lower = token.lower()
                idx = llm_lower.find(token_lower)
                while idx != -1:
                    # Check 30 chars before the token for negation
                    context_start = max(0, idx - 30)
                    context_window = llm_lower[context_start:idx]

                    has_negation = any(
                        neg in context_window
                        for neg in (*_NEGATION_ZH, *_NEGATION_EN)
                    )

                    if has_negation:
                        # Extract the contradicting sentence from LLM output
                        sentence_start = max(0, llm_output.rfind("\n", 0, idx))
                        sentence_end = llm_output.find("\n", idx)
                        if sentence_end == -1:
                            sentence_end = min(len(llm_output), idx + 100)
                        llm_sentence = llm_output[sentence_start:sentence_end].strip()

                        contradictions.append({
                            "skill_assertion": assertion[:200],
                            "llm_statement": llm_sentence[:200],
                            "type": "potential_contradiction",
                        })
                        break  # One contradiction per assertion is enough

                    # Look for next occurrence
                    idx = llm_lower.find(token_lower, idx + 1)

        # Deduplicate by llm_statement
        seen: set[str] = set()
        unique: list[dict[str, str]] = []
        for c in contradictions:
            key = c["llm_statement"]
            if key not in seen:
                seen.add(key)
                unique.append(c)

        return unique[:5]  # Cap at 5 contradictions

    # ------------------------------------------------------------------
    # Level-aware formatting
    # ------------------------------------------------------------------

    def _format_for_level(
        self,
        *,
        response: AdvisorResponse,
        user_level: str,
        language: str,
    ) -> AdvisorResponse:
        """Adjust output format based on user level.

        - beginner: add action_guide + glossary
        - intermediate/independent: moderate formatting (no extras)
        - expert: action_guide=None, glossary=None, core insights only
        """
        if user_level == "beginner":
            response.action_guide = self._generate_action_guide(response, language)
            response.glossary = self._generate_glossary(response, language)
        elif user_level == "expert":
            response.action_guide = None
            response.glossary = None
        else:
            # intermediate / independent: no extras
            response.action_guide = None
            response.glossary = None

        return response

    def _generate_action_guide(
        self, response: AdvisorResponse, language: str
    ) -> list[str]:
        """Generate step-by-step action guide for beginners."""
        guide: list[str] = []

        # Extract actionable steps from LLM advice or skill framework
        source_text = response.llm_advice or response.skill_framework.get("body", "")

        if not source_text:
            if language == "zh-CN":
                return ["明确你的核心问题", "收集相关证据", "验证你的假设"]
            return ["Clarify your core question", "Gather relevant evidence", "Validate your assumptions"]

        # Extract action items from the text
        lines = source_text.split("\n")
        for line in lines:
            stripped = line.strip()
            # Look for action-oriented lines
            if stripped.startswith(("- ", "* ", "1.", "2.", "3.", "4.", "5.")):
                clean = re.sub(r"^[-*\d.]+\s*", "", stripped).strip()
                if clean and len(clean) > 5:
                    guide.append(clean)
                    if len(guide) >= 5:
                        break

        if not guide:
            if language == "zh-CN":
                guide = ["明确你的核心问题", "收集相关证据", "验证你的假设"]
            else:
                guide = ["Clarify your core question", "Gather relevant evidence", "Validate your assumptions"]

        return guide

    def _generate_glossary(
        self, response: AdvisorResponse, language: str
    ) -> dict[str, str]:
        """Generate glossary of technical terms for beginners."""
        glossary: dict[str, str] = {}

        # Extract terms from skill framework labels and body
        model_ids = response.skill_framework.get("model_ids", [])
        labels = response.skill_framework.get("labels", [])

        # Add framework model names to glossary
        _TERM_EXPLANATIONS_ZH: dict[str, str] = {
            "mece": "相互独立、完全穷尽 — 一种确保分析不遗漏不重叠的分类方法",
            "five-whys": "五个为什么 — 通过连续追问根因来找到问题本质的方法",
            "five-w-two-h": "5W2H — 用 What/Why/Who/When/Where/How/How much 全面分析问题",
            "jtbd": "Jobs to be Done — 关注用户要完成的任务而非产品功能",
            "pareto": "帕累托法则 — 80% 的结果来自 20% 的原因",
            "pdca": "计划-执行-检查-行动循环 — 持续改进的基本方法",
            "pre-mortem": "预演失败 — 假设项目已经失败，倒推可能的原因",
            "smart": "SMART 目标 — 具体、可衡量、可达成、相关、有时限",
            "decision-matrix": "决策矩阵 — 用加权评分比较多个选项",
            "fishbone": "鱼骨图 — 系统化分析问题原因的可视化工具",
            "problem-statement": "问题陈述 — 清晰定义问题的边界和期望结果",
            "mvp": "最小可行产品 — 用最少资源验证核心假设",
        }

        _TERM_EXPLANATIONS_EN: dict[str, str] = {
            "mece": "Mutually Exclusive, Collectively Exhaustive — a classification method ensuring no overlaps or gaps",
            "five-whys": "Five Whys — repeatedly asking 'why' to find the root cause",
            "five-w-two-h": "5W2H — analyzing with What/Why/Who/When/Where/How/How much",
            "jtbd": "Jobs to be Done — focusing on the task users want to accomplish",
            "pareto": "Pareto Principle — 80% of results come from 20% of causes",
            "pdca": "Plan-Do-Check-Act — a continuous improvement cycle",
            "pre-mortem": "Pre-mortem — imagining failure and working backward to find causes",
            "smart": "SMART Goals — Specific, Measurable, Achievable, Relevant, Time-bound",
            "decision-matrix": "Decision Matrix — comparing options with weighted scoring",
            "fishbone": "Fishbone Diagram — a visual tool for systematic cause analysis",
            "problem-statement": "Problem Statement — clearly defining the problem boundary and expected outcome",
            "mvp": "Minimum Viable Product — validating core assumptions with minimal resources",
        }

        explanations = _TERM_EXPLANATIONS_ZH if language == "zh-CN" else _TERM_EXPLANATIONS_EN

        for model_id in model_ids:
            if model_id in explanations:
                glossary[model_id] = explanations[model_id]

        # Add labels as terms if they differ from IDs
        for label in labels:
            label_lower = label.lower().replace(" ", "-")
            if label_lower in explanations and label_lower not in glossary:
                glossary[label] = explanations[label_lower]

        # Ensure at least some entries for beginners
        if not glossary:
            if language == "zh-CN":
                glossary["结构化分析"] = "按照固定框架逐步分析问题，避免遗漏"
                glossary["假设验证"] = "先提出假设，再用证据检验是否成立"
            else:
                glossary["Structured Analysis"] = "Analyzing problems step by step using a fixed framework"
                glossary["Hypothesis Validation"] = "Proposing a hypothesis first, then testing it with evidence"

        return glossary

    # ------------------------------------------------------------------
    # Strategy selection
    # ------------------------------------------------------------------

    def _select_strategy(
        self, context: AdvisorContext, skill_framework: dict[str, Any]
    ) -> tuple[str, str]:
        """Select reasoning strategy based on context.

        Returns (strategy_name, strategy_reason).
        """
        model_ids = skill_framework.get("model_ids", [])
        complexity = skill_framework.get("complexity", "moderate")

        # Strategy selection logic
        if context.retrieval_depth_boost > 0:
            return (
                "deep_domain_focus",
                f"User has queried this domain repeatedly (boost={context.retrieval_depth_boost}), "
                f"increasing depth and specificity",
            )

        if context.context_anchor_goal:
            return (
                "goal_aligned",
                f"Active context anchor detected, aligning reasoning with goal: "
                f"{context.context_anchor_goal[:60]}",
            )

        if context.user_level == "beginner":
            return (
                "guided_exploration",
                "User is a beginner, providing step-by-step guidance with explanations",
            )

        if context.user_level == "expert":
            return (
                "expert_challenge",
                "User is an expert, focusing on blind spots and counterexamples",
            )

        if complexity == "complex":
            return (
                "multi_lens_analysis",
                f"Complex question detected, using multiple frameworks: "
                f"{', '.join(model_ids[:3])}",
            )

        return (
            "standard_hybrid",
            "Standard hybrid reasoning with Skill framework + LLM generation",
        )

    def _select_skill_chain(
        self, skill_framework: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Pick an active :class:`SkillChain` for this turn (R3.2).

        The pointer is purely informational at this layer — orchestration
        decides whether to advance the chain. We pick the chain whose
        ``problem_type`` matches the framework's first model_id, falling
        back to ``general``. Returns ``None`` when the registry is empty.
        """

        try:
            from . import skill_chain as chain_mod
        except Exception:
            return None
        chain_mod.load_all()  # idempotent
        chains = chain_mod.list_chains()
        if not chains:
            return None
        problem_type = skill_framework.get("problem_type") or "general"
        chain = chain_mod.select_chain(
            problem_type=problem_type, chains=chains, context={"always": True}
        )
        if chain is None:
            return None
        state = chain_mod.initial_state(chain, {"always": True})
        return {
            "chain_id": state.chain_id,
            "step_idx": state.step_idx,
            "step_skill_id": state.step_skill_id,
            "entry_satisfied": state.entry_satisfied,
            "exit_satisfied": state.exit_satisfied,
        }

    # ------------------------------------------------------------------
    # Query history recording
    # ------------------------------------------------------------------

    def _record_query_history(
        self,
        *,
        tenant_id: str,
        question: str,
        skill_framework: dict[str, Any],
        strategy_used: str,
    ) -> None:
        """Record query to query_history table for context awareness."""
        core = get_core()

        # Extract domain concepts from the question and skill framework
        domain_concepts = skill_framework.get("model_ids", [])
        # Also add significant tokens from the question as domain markers
        question_tokens = set(tokenize(question)) - STOPWORDS
        significant = [t for t in question_tokens if len(t) > 2][:5]
        domain_concepts = list(set(domain_concepts + significant))

        try:
            with core._lock, core._connect() as db:
                db.execute(
                    """
                    insert into query_history(id, tenant_id, query, domain_concepts, strategy_used, created_at)
                    values(?, ?, ?, ?, ?, ?)
                    """,
                    (
                        _new_id("qh"),
                        tenant_id,
                        question[:500],  # Truncate long queries
                        json.dumps(domain_concepts, ensure_ascii=False),
                        strategy_used,
                        _utc_now_iso(),
                    ),
                )
        except Exception:
            pass  # Non-critical, don't block the response
