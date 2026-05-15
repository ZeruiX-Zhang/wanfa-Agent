"""Thinking Model Router — deterministic + LLM-upgradeable model selection.

This is the Code Core that decides:
1. Which thinking model(s) to activate for a given question
2. How many models to use (based on user level + question complexity)
3. What prompt strategy to compose (based on selected models + user profile)

Design:
- Deterministic path: intent_signals matching (always available, no LLM needed)
- LLM-enhanced path: when classifier slot is configured, uses model descriptions
  for semantic matching (more accurate but requires API)
- Level-aware: beginner gets 1 model with more guidance; expert gets 2-3 models
  with minimal scaffolding
"""

from __future__ import annotations

from typing import Any, Literal

from . import (
    ThinkingModelMeta,
    ThinkingModelFull,
    get_model_full,
    get_registry,
    route_model,
)


# ---------------------------------------------------------------------------
# Level-aware model count decision
# ---------------------------------------------------------------------------

UserLevel = Literal["beginner", "intermediate", "independent", "expert"]


def decide_model_count(
    *,
    user_level: UserLevel | None,
    question_complexity: Literal["simple", "moderate", "complex"],
    available_models: int,
) -> int:
    """Decide how many thinking models to activate based on user level and complexity.

    Principles:
    - Beginner: 1 model, deeply guided (avoid cognitive overload)
    - Intermediate: 1-2 models (primary + optional contrast)
    - Independent: 2 models (primary + adversarial check)
    - Expert: 2-3 models (multi-lens analysis, minimal scaffolding)

    Complexity also matters:
    - Simple questions: max 1 model regardless of level
    - Moderate: level-based
    - Complex: level-based + 1
    """
    if available_models == 0:
        return 0

    level = user_level or "intermediate"

    base_count = {
        "beginner": 1,
        "intermediate": 1,
        "independent": 2,
        "expert": 2,
    }[level]

    complexity_bonus = {
        "simple": 0,
        "moderate": 0,
        "complex": 1,
    }[question_complexity]

    # Simple questions: always 1
    if question_complexity == "simple":
        return 1

    count = base_count + complexity_bonus
    return min(count, min(3, available_models))


def estimate_complexity(question: str) -> Literal["simple", "moderate", "complex"]:
    """Estimate question complexity from surface features.

    Heuristics:
    - Short questions with single intent → simple
    - Questions with multiple clauses or conditions → moderate
    - Questions with trade-offs, multi-stakeholder, or systemic aspects → complex
    """
    length = len(question)
    # Count complexity markers
    _COMPLEX_ZH = ("而且", "但是", "同时", "一方面", "另一方面", "权衡", "取舍", "系统", "多个", "各方")
    _COMPLEX_EN = ("however", "on the other hand", "tradeoff", "multiple", "stakeholder", "systemic", "balance", "versus")
    _MODERATE_ZH = ("如何", "怎么", "应该", "可以", "需要")
    _MODERATE_EN = ("how", "should", "could", "need to", "want to")

    q_lower = question.lower()
    complex_hits = sum(1 for m in _COMPLEX_ZH if m in q_lower) + sum(1 for m in _COMPLEX_EN if m in q_lower)
    moderate_hits = sum(1 for m in _MODERATE_ZH if m in q_lower) + sum(1 for m in _MODERATE_EN if m in q_lower)

    if complex_hits >= 2 or length > 200:
        return "complex"
    if moderate_hits >= 1 or length > 80:
        return "moderate"
    return "simple"


# ---------------------------------------------------------------------------
# Multi-model routing
# ---------------------------------------------------------------------------


def select_models(
    *,
    question: str,
    language: str = "zh-CN",
    user_level: UserLevel | None = None,
    max_models: int | None = None,
) -> list[ThinkingModelMeta]:
    """Select the best thinking model(s) for a question.

    Returns an ordered list: [primary_model, contrast_model?, ...]
    """
    registry = get_registry()
    if not registry:
        return []

    complexity = estimate_complexity(question)
    count = max_models or decide_model_count(
        user_level=user_level,
        question_complexity=complexity,
        available_models=len(registry),
    )

    # Score all models
    question_lower = question.lower()
    scored: list[tuple[ThinkingModelMeta, int]] = []

    for model in registry.values():
        score = 0
        for signal in model.intent_signals:
            if signal.lower() in question_lower:
                score += 1
        if score > 0:
            scored.append((model, score))

    # Sort by score descending
    scored.sort(key=lambda x: x[1], reverse=True)

    if not scored:
        # No match — pick by category heuristic
        return _fallback_selection(question, language, count)

    # Take top N, ensuring category diversity for multi-model
    selected: list[ThinkingModelMeta] = [scored[0][0]]
    if count > 1:
        primary_category = scored[0][0].category
        for model, _ in scored[1:]:
            if model.category != primary_category:
                selected.append(model)
                break
        # If still need more, just take next best
        if len(selected) < count:
            for model, _ in scored[1:]:
                if model not in selected:
                    selected.append(model)
                    if len(selected) >= count:
                        break

    return selected[:count]


def _fallback_selection(question: str, language: str, count: int) -> list[ThinkingModelMeta]:
    """When no intent signals match, pick based on question structure."""
    registry = get_registry()

    # Default: problem-statement for unclear questions, five-w-two-h for broad ones
    fallback_ids = ["problem-statement", "five-w-two-h", "mece"]
    result: list[ThinkingModelMeta] = []
    for fid in fallback_ids:
        if fid in registry:
            result.append(registry[fid])
            if len(result) >= count:
                break

    # If still empty, just take first available
    if not result:
        result = list(registry.values())[:count]

    return result


# ---------------------------------------------------------------------------
# Prompt composition (level-aware)
# ---------------------------------------------------------------------------


def compose_model_prompt(
    *,
    question: str,
    models: list[ThinkingModelFull],
    user_level: UserLevel | None = None,
    language: str = "zh-CN",
    user_constraints: list[str] | None = None,
) -> str:
    """Compose the structured prompt that gets injected into the LLM call.

    This is where thinking models actually change the reasoning:
    - The model's body (SKILL.md instructions) becomes the system prompt
    - User level determines how much scaffolding to include
    - Multiple models get composed as "primary lens + contrast lens"
    """
    level = user_level or "intermediate"

    # Level-specific preamble
    preamble = _level_preamble(level, language)

    # Primary model instructions
    primary = models[0] if models else None
    if not primary:
        return preamble + f"\n\n问题：{question}" if language == "zh-CN" else preamble + f"\n\nQuestion: {question}"

    sections: list[str] = [preamble]

    # Primary model
    if language == "zh-CN":
        sections.append(f"## 主要分析框架：{primary.meta.label_zh}\n\n{primary.body}")
    else:
        sections.append(f"## Primary Framework: {primary.meta.label_en}\n\n{primary.body}")

    # Contrast model (if multi-model)
    if len(models) > 1:
        contrast = models[1]
        if language == "zh-CN":
            sections.append(f"\n## 对比视角：{contrast.meta.label_zh}\n\n在用主要框架分析后，再从「{contrast.meta.label_zh}」的角度检查是否有遗漏。")
        else:
            sections.append(f"\n## Contrast Lens: {contrast.meta.label_en}\n\nAfter the primary analysis, check from the '{contrast.meta.label_en}' perspective for blind spots.")

    # User constraints
    if user_constraints:
        constraints_str = "\n".join(f"- {c}" for c in user_constraints[:5])
        if language == "zh-CN":
            sections.append(f"\n## 用户约束（答案必须在这些条件下成立）\n{constraints_str}")
        else:
            sections.append(f"\n## User Constraints (answer must hold under these)\n{constraints_str}")

    # Question
    if language == "zh-CN":
        sections.append(f"\n## 用户问题\n{question}")
    else:
        sections.append(f"\n## User Question\n{question}")

    # Level-specific output guidance
    sections.append(_level_output_guidance(level, language))

    return "\n\n".join(sections)


def _level_preamble(level: UserLevel, language: str) -> str:
    """Level-specific system preamble."""
    if language == "zh-CN":
        mapping = {
            "beginner": "你是一位耐心的导师。用户是新手，请用简单语言解释每一步，避免术语，多给具体例子。",
            "intermediate": "你是一位专业顾问。用户有一定基础，可以使用专业术语但需要解释关键概念。",
            "independent": "你是一位同行专家。用户能独立交付，直接给出核心洞察和行动建议，不需要基础解释。",
            "expert": "你是一位顶级同行。用户是专家，只需要指出盲点、提供反例、挑战假设。不要解释基础概念。",
        }
    else:
        mapping = {
            "beginner": "You are a patient mentor. The user is a beginner — use simple language, avoid jargon, give concrete examples.",
            "intermediate": "You are a professional advisor. The user has solid foundations — use domain terms but explain key concepts.",
            "independent": "You are a peer expert. The user delivers independently — give core insights and action items directly.",
            "expert": "You are a top peer. The user is an expert — only point out blind spots, provide counterexamples, challenge assumptions.",
        }
    return mapping.get(level, mapping["intermediate"])


def _level_output_guidance(level: UserLevel, language: str) -> str:
    """Level-specific output format guidance."""
    if language == "zh-CN":
        mapping = {
            "beginner": "\n## 输出要求\n- 每个结论用一句话总结\n- 标注哪些是事实 ✓ 哪些是假设 [?]\n- 给出「下一步做什么」的具体行动（不超过 3 个）\n- 如果有不确定的地方，明确说「我不确定，建议你验证」",
            "intermediate": "\n## 输出要求\n- 按框架结构输出\n- 标注证据类型（事实/假设/推断）\n- 给出行动建议和优先级\n- 指出关键风险",
            "independent": "\n## 输出要求\n- 直接给结论和行动项\n- 只标注高风险假设\n- 如果有反直觉的发现，重点说明",
            "expert": "\n## 输出要求\n- 只说你认为用户可能没想到的\n- 提供反例或边界条件\n- 如果分析结果和常识一致，直接说「无新发现」",
        }
    else:
        mapping = {
            "beginner": "\n## Output Requirements\n- Summarize each conclusion in one sentence\n- Mark facts ✓ and assumptions [?]\n- Give specific next actions (max 3)\n- If uncertain, say so explicitly",
            "intermediate": "\n## Output Requirements\n- Follow the framework structure\n- Mark evidence types (fact/assumption/inference)\n- Give prioritized action items\n- Flag key risks",
            "independent": "\n## Output Requirements\n- Lead with conclusions and action items\n- Only flag high-risk assumptions\n- Highlight counterintuitive findings",
            "expert": "\n## Output Requirements\n- Only mention what the user likely hasn't considered\n- Provide counterexamples or boundary conditions\n- If analysis aligns with common sense, say 'no new findings'",
        }
    return mapping.get(level, mapping["intermediate"])
