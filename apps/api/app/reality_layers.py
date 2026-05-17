"""Reality OS 8-layer product logic.

Layer 1: User Reality Profile (industry, level, resources, goals, constraints,
          current tasks, decision history, error patterns).
Layer 2: Industry Knowledge (handled by knowledge_core.absorb + concept graph).
Layer 3: Reality Diagnosis (problem reframing, key variables, evidence gaps,
          expert-first-look, minimum verifiable action).
Layer 4: Thinking Model Router (auto-select 1–3 models per question type).
Layer 5: Evidence Classification (fact / interpretation / hypothesis / inference
          / recommendation / risk).
Layer 6: Action Experiment (hypothesis → experiment → cost → metric → failure
          signal → review date → next step).
Layer 7: Learning Iteration (original judgment → actual result → gap → root
          cause → signal for next time → knowledge card).
Layer 8: Safety & Governance (handled by security.py + supervisor + audit).

This module provides the data models and deterministic logic for layers 1, 3,
5, 6, 7. Layers 2, 4, 8 are already covered by knowledge_core.py,
intelligence.py, and security.py respectively.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import uuid4
from datetime import datetime, timezone


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


# ---------------------------------------------------------------------------
# Layer 1: User Reality Profile
# ---------------------------------------------------------------------------


@dataclass
class UserProfile:
    id: str
    tenant_id: str
    industry: str
    level: Literal["beginner", "intermediate", "independent", "expert"]
    resources: dict[str, Any]  # time, money, network, tools, data
    goals: list[str]
    constraints: list[str]
    current_tasks: list[str]
    decision_history: list[dict[str, Any]]
    error_patterns: list[str]
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "industry": self.industry,
            "level": self.level,
            "resources": self.resources,
            "goals": self.goals,
            "constraints": self.constraints,
            "current_tasks": self.current_tasks,
            "decision_history": self.decision_history,
            "error_patterns": self.error_patterns,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# ---------------------------------------------------------------------------
# Layer 3: Reality Diagnosis
# ---------------------------------------------------------------------------


@dataclass
class Diagnosis:
    id: str
    tenant_id: str
    surface_question: str
    real_question: str
    problem_type: str
    key_variables: list[str]
    evidence_status: list[dict[str, str]]  # [{type, content, status}]
    subjective_judgments: list[str]
    needs_external_verification: list[str]
    common_failure_reasons: list[str]
    expert_first_look: str
    minimum_verifiable_action: str
    thinking_models_used: list[str]
    created_at: str
    # Step 2: Decision anchors — items the human must explicitly accept/reject
    decision_anchors: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "surface_question": self.surface_question,
            "real_question": self.real_question,
            "problem_type": self.problem_type,
            "key_variables": self.key_variables,
            "evidence_status": self.evidence_status,
            "subjective_judgments": self.subjective_judgments,
            "needs_external_verification": self.needs_external_verification,
            "common_failure_reasons": self.common_failure_reasons,
            "expert_first_look": self.expert_first_look,
            "minimum_verifiable_action": self.minimum_verifiable_action,
            "thinking_models_used": self.thinking_models_used,
            "created_at": self.created_at,
            "decision_anchors": list(self.decision_anchors),
        }


# ---------------------------------------------------------------------------
# Layer 5: Evidence Classification
# ---------------------------------------------------------------------------


EvidenceType = Literal["fact", "interpretation", "hypothesis", "inference", "recommendation", "risk"]


@dataclass
class ClassifiedEvidence:
    type: EvidenceType
    content: str
    source: str | None
    confidence: float
    needs_verification: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "content": self.content,
            "source": self.source,
            "confidence": round(self.confidence, 3),
            "needs_verification": self.needs_verification,
        }


# ---------------------------------------------------------------------------
# Layer 6: Action Experiment
# ---------------------------------------------------------------------------


@dataclass
class ActionExperiment:
    id: str
    tenant_id: str
    hypothesis: str
    experiment: str
    cost: dict[str, str]  # time, money, effort
    success_metric: str
    failure_signal: str
    review_date: str
    next_if_success: str
    next_if_failure: str
    status: Literal["planned", "running", "succeeded", "failed", "abandoned"]
    actual_result: str
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "hypothesis": self.hypothesis,
            "experiment": self.experiment,
            "cost": self.cost,
            "success_metric": self.success_metric,
            "failure_signal": self.failure_signal,
            "review_date": self.review_date,
            "next_if_success": self.next_if_success,
            "next_if_failure": self.next_if_failure,
            "status": self.status,
            "actual_result": self.actual_result,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# ---------------------------------------------------------------------------
# Layer 7: Learning Review (post-action retrospective)
# ---------------------------------------------------------------------------


@dataclass
class LearningReview:
    id: str
    tenant_id: str
    experiment_id: str | None
    original_judgment: str
    actual_result: str
    gap: str
    root_cause: Literal["fact_wrong", "model_wrong", "execution_wrong", "unknown"]
    signal_for_next_time: str
    knowledge_card_title: str
    knowledge_card_body: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "experiment_id": self.experiment_id,
            "original_judgment": self.original_judgment,
            "actual_result": self.actual_result,
            "gap": self.gap,
            "root_cause": self.root_cause,
            "signal_for_next_time": self.signal_for_next_time,
            "knowledge_card_title": self.knowledge_card_title,
            "knowledge_card_body": self.knowledge_card_body,
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# Structured experiment review (expert-coaching-loop, R9.1)
# ---------------------------------------------------------------------------


@dataclass
class KeyMetric:
    """One measured outcome of an experiment (R9.1, design data model 8).

    ``breached`` is the per-metric breach predicate from Property 20:
    the metric breaches when the observed ``value`` deviates from
    ``target`` by more than ``tolerance``.
    """

    name: str
    target: float
    value: float
    tolerance: float = 0.0

    @property
    def breached(self) -> bool:
        return abs(self.value - self.target) > self.tolerance

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "target": self.target,
            "value": self.value,
            "tolerance": self.tolerance,
            "breached": self.breached,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "KeyMetric":
        return cls(
            name=str(data.get("name", "")),
            target=float(data.get("target", 0.0)),
            value=float(data.get("value", 0.0)),
            tolerance=float(data.get("tolerance", 0.0)),
        )


@dataclass
class ExperimentReview:
    """Structured post-experiment review (R9.1).

    Distinct from the free-text ``ActionExperiment.actual_result``, which
    is kept verbatim for backward compatibility. This aggregate is what
    the mastery hard-binding (R9.2) and consecutive-fail policy (R9.3)
    operate on. Mirrors the ``experiment_reviews`` table.
    """

    id: str
    tenant_id: str
    experiment_id: str
    result_class: Literal["success", "partial", "fail"]
    key_metrics: list[KeyMetric]
    notes: str
    created_at: str

    @property
    def metric_breach(self) -> bool:
        """True when any key metric exceeds its tolerance (Property 20)."""

        return any(metric.breached for metric in self.key_metrics)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "experiment_id": self.experiment_id,
            "result_class": self.result_class,
            "key_metrics": [metric.to_dict() for metric in self.key_metrics],
            "metric_breach": self.metric_breach,
            "notes": self.notes,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExperimentReview":
        return cls(
            id=str(data["id"]),
            tenant_id=str(data["tenant_id"]),
            experiment_id=str(data["experiment_id"]),
            result_class=data["result_class"],
            key_metrics=[
                KeyMetric.from_dict(metric)
                for metric in (data.get("key_metrics") or [])
            ],
            notes=str(data.get("notes", "")),
            created_at=str(data["created_at"]),
        )


# ---------------------------------------------------------------------------
# Decision Log (cross-cutting, referenced by Layer 7)
# ---------------------------------------------------------------------------


@dataclass
class DecisionLog:
    id: str
    tenant_id: str
    decision: str
    reasoning: list[str]
    evidence: list[str]
    assumptions: list[str]
    risks: list[str]
    success_metric: str
    review_date: str
    status: Literal["active", "succeeded", "failed", "revised"]
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "decision": self.decision,
            "reasoning": self.reasoning,
            "evidence": self.evidence,
            "assumptions": self.assumptions,
            "risks": self.risks,
            "success_metric": self.success_metric,
            "review_date": self.review_date,
            "status": self.status,
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# Deterministic diagnosis engine (Layer 3 + 4 + 5 combined)
# ---------------------------------------------------------------------------


PROBLEM_TYPES = {
    "efficiency": {"triggers": ("效率", "慢", "低效", "slow", "inefficient", "bottleneck"), "models": ["DMAIC", "流程挖掘", "瓶颈理论"]},
    "no_customers": {"triggers": ("没人买", "没客户", "no sales", "no customers", "转化"), "models": ["JTBD", "价值主张画布", "漏斗分析"]},
    "uncertainty": {"triggers": ("不确定", "该不该", "should i", "uncertain", "risk"), "models": ["RPD", "预演失败", "贝叶斯更新"]},
    "platform_risk": {"triggers": ("替代", "平台", "replace", "platform", "compete"), "models": ["护城河", "价值链", "替代性分析"]},
    "capability_gap": {"triggers": ("不会", "学不会", "能力", "skill", "learn", "转行"), "models": ["刻意练习", "反馈回路", "任务分级"]},
    "knowledge_chaos": {"triggers": ("知识", "混乱", "找不到", "knowledge", "organize"), "models": ["KCS", "知识图谱", "权限矩阵"]},
    "ai_reliability": {"triggers": ("幻觉", "不准", "hallucin", "unreliable", "wrong answer"), "models": ["RAG 评测", "NIST AI RMF", "人工审核"]},
    "process_improvement": {"triggers": ("流程", "改进", "优化", "process", "improve"), "models": ["DMAIC", "设计思维", "流程挖掘"]},
}


def classify_problem(question: str) -> tuple[str, list[str]]:
    lower = question.lower()
    for ptype, config in PROBLEM_TYPES.items():
        if any(trigger in lower for trigger in config["triggers"]):
            return ptype, config["models"]
    return "general", ["第一性原理", "OODA", "期望值"]


def generate_diagnosis(
    *,
    question: str,
    profile: UserProfile | None,
    language: str,
) -> Diagnosis:
    """Deterministic diagnosis — no LLM call required.

    If a user profile exists, we use it to tailor the reframe, the key variables,
    the failure reasons, and the minimum verifiable action. This is the
    personalization backbone of layer 1 → layer 3.
    """

    problem_type, models = classify_problem(question)

    real_question = _reframe_with_profile(question, profile, language)
    expert_first_look = _expert_first_look(problem_type, language)
    mva = _tailored_mva(problem_type, profile, language)

    key_variables = _derive_key_variables(question, profile, language)
    evidence_status = _derive_evidence_status(question, language)
    subjective = _derive_subjective(question, language)
    external_verify = _derive_external_verify(question, language)
    failure_reasons = _derive_failure_reasons(problem_type, profile, language)

    return Diagnosis(
        id=_id("diag"),
        tenant_id=profile.tenant_id if profile else "local",
        surface_question=question,
        real_question=real_question,
        problem_type=problem_type,
        key_variables=key_variables,
        evidence_status=evidence_status,
        subjective_judgments=subjective,
        needs_external_verification=external_verify,
        common_failure_reasons=failure_reasons,
        expert_first_look=expert_first_look,
        minimum_verifiable_action=mva,
        thinking_models_used=models,
        created_at=_utc(),
        decision_anchors=_generate_decision_anchors(
            question=question,
            key_variables=key_variables,
            subjective=subjective,
            language=language,
        ),
    )


# ---------------------------------------------------------------------------
# Profile-aware helpers for the diagnosis pipeline
# ---------------------------------------------------------------------------


def _reframe_with_profile(question: str, profile: UserProfile | None, language: str) -> str:
    """Incorporate the user's level and constraints into the reframe."""

    base_zh = f"你表面问的是「{question[:60]}」，但真实问题可能是："
    base_en = f"You asked '{question[:60]}', but the real question is likely: "
    if not profile:
        if language == "zh-CN":
            return base_zh + "在你当前的资源和约束下，什么是最小成本验证这个方向的方式？"
        return base_en + "given your resources and constraints, what is the minimum-cost way to validate this direction?"

    # Tailor to the user's level
    level_modifier_zh = {
        "beginner": "作为新手，你最该问的是「我是否真的理解这个问题的边界」",
        "intermediate": "在你当前水平下，真正的瓶颈更可能在交付而非理解",
        "independent": "作为能独立交付的人，问题更可能是「取舍与时机」而非技术",
        "expert": "作为专家，你的真正问题常常是「别人没发现的空白」",
    }
    level_modifier_en = {
        "beginner": "As a beginner, the real question is whether you truly understand the problem boundary",
        "intermediate": "At your level, the bottleneck is likely delivery rather than comprehension",
        "independent": "As someone who can deliver independently, the real question is tradeoff and timing, not tech",
        "expert": "As an expert, the real question is usually 'what are others missing', not 'how'",
    }

    suffix_zh = level_modifier_zh.get(profile.level, level_modifier_zh["intermediate"])
    suffix_en = level_modifier_en.get(profile.level, level_modifier_en["intermediate"])

    # Splice the top 2 constraints into the reframe so the answer lives in the
    # real-world. This is the single most impactful personalization signal.
    if profile.constraints:
        top = "、".join(profile.constraints[:2]) if language == "zh-CN" else ", ".join(profile.constraints[:2])
        if language == "zh-CN":
            return f"{base_zh}{suffix_zh}，而且答案必须在「{top}」这些约束下仍然成立。"
        return f"{base_en}{suffix_en}, and the answer must still hold under your constraints: {top}."

    return base_zh + suffix_zh + "。" if language == "zh-CN" else base_en + suffix_en + "."


def _expert_first_look(problem_type: str, language: str) -> str:
    mapping_zh = {
        "no_customers": "先看「谁愿意付多少钱」而不是「功能够不够多」",
        "platform_risk": "先看「平台内置这个功能的边际成本」和「你有哪些平台拿不到的数据」",
        "uncertainty": "先看「这个判断错了最多损失多少」以及「多久能拿到一个反馈信号」",
        "capability_gap": "先看「最小可交付的任务」和「每周可以复盘的次数」",
        "knowledge_chaos": "先看「谁决定知识入库标准」和「现在检索命中率是多少」",
        "ai_reliability": "先看「错误答案的成本」和「人工审核在哪一步插入」",
        "efficiency": "先看「哪一步是真正瓶颈」而不是最烦的那一步",
        "process_improvement": "先测基线，再动刀",
        "general": "先看「如果这个判断错了会怎样」和「你最缺哪个信号」",
    }
    mapping_en = {
        "no_customers": "First check 'who pays how much', not 'do I have enough features'",
        "platform_risk": "First check the platform's marginal cost to build this, and what data you have that they don't",
        "uncertainty": "First check the worst-case loss and how fast you can get a feedback signal",
        "capability_gap": "First check the smallest deliverable task and how many retros you can run per week",
        "knowledge_chaos": "First check who decides ingest standards and what your current retrieval hit rate is",
        "ai_reliability": "First check the cost of a wrong answer and where human review enters the loop",
        "efficiency": "First check which step is the real bottleneck, not the most annoying one",
        "process_improvement": "Measure the baseline first, then act",
        "general": "First check what happens if you are wrong and which signal you lack most",
    }
    mapping = mapping_zh if language == "zh-CN" else mapping_en
    return mapping.get(problem_type, mapping["general"])


def _tailored_mva(problem_type: str, profile: UserProfile | None, language: str) -> str:
    """Minimum verifiable action, scaled to the user's resources."""

    time_budget = "本周" if language == "zh-CN" else "this week"
    if profile and isinstance(profile.resources, dict):
        raw_time = str(profile.resources.get("time") or "").lower()
        if any(marker in raw_time for marker in ("few hours", "1h", "2h", "低", "少")):
            time_budget = "今天 1 小时内" if language == "zh-CN" else "in 1 hour today"

    mapping_zh = {
        "no_customers": f"{time_budget}找 3 个目标用户，问他们是否愿意付费，以及愿意付多少。",
        "platform_risk": f"{time_budget}写下 3 个「只有你能做、大模型平台做不了」的理由，每个必须有证据。",
        "uncertainty": f"{time_budget}列出你的赌注和最差结果，算一下最大可承受损失。",
        "capability_gap": f"{time_budget}做一个最小可交付的版本，不求完美，求拿到一次完整反馈。",
        "knowledge_chaos": f"{time_budget}挑 5 条最高频被查的知识，检查它们的入库标准是否统一。",
        "ai_reliability": f"{time_budget}准备 10 个已知正确答案的测试用例，跑一遍现有系统看通过率。",
        "efficiency": f"{time_budget}测量现有流程的基线耗时，找出真正瓶颈步骤。",
        "process_improvement": f"{time_budget}画出现有流程的每一步耗时，再决定改哪一步。",
        "general": f"{time_budget}找 3 个潜在用户，问他们是否愿意为这个问题的解决方案付费。",
    }
    mapping_en = {
        "no_customers": f"{time_budget}, find 3 target users and ask if they would pay and how much.",
        "platform_risk": f"{time_budget}, write 3 reasons only you can do this, each with evidence.",
        "uncertainty": f"{time_budget}, list your bets and worst cases; compute the max tolerable loss.",
        "capability_gap": f"{time_budget}, ship a minimum deliverable to get one complete feedback cycle.",
        "knowledge_chaos": f"{time_budget}, audit the 5 most-queried knowledge items for consistent ingest standards.",
        "ai_reliability": f"{time_budget}, prepare 10 ground-truth test cases and measure the current pass rate.",
        "efficiency": f"{time_budget}, measure the baseline durations and identify the true bottleneck.",
        "process_improvement": f"{time_budget}, chart each step's duration before changing anything.",
        "general": f"{time_budget}, find 3 potential users and ask if they would pay for this.",
    }
    mapping = mapping_zh if language == "zh-CN" else mapping_en
    return mapping.get(problem_type, mapping["general"])


def _derive_key_variables(question: str, profile: UserProfile | None, language: str) -> list[str]:
    base_zh = ["目标客户痛点强度", "付费意愿", "技术可行性", "你的不可替代性", "时间窗口"]
    base_en = ["Customer pain intensity", "Willingness to pay", "Technical feasibility", "Your irreplaceability", "Time window"]
    if profile:
        if language == "zh-CN":
            base_zh.append(f"你当前水平：{profile.level}")
            if profile.constraints:
                base_zh.append(f"约束：{', '.join(profile.constraints[:3])}")
        else:
            base_en.append(f"Your current level: {profile.level}")
            if profile.constraints:
                base_en.append(f"Constraints: {', '.join(profile.constraints[:3])}")
    return base_zh if language == "zh-CN" else base_en


def _derive_evidence_status(question: str, language: str) -> list[dict[str, str]]:
    if language == "zh-CN":
        return [
            {"type": "fact", "content": "你提出了这个问题", "status": "confirmed"},
            {"type": "hypothesis", "content": "这个方向有市场需求", "status": "unverified"},
            {"type": "hypothesis", "content": "你有能力交付", "status": "unverified"},
        ]
    return [
        {"type": "fact", "content": "You raised this question", "status": "confirmed"},
        {"type": "hypothesis", "content": "There is market demand for this", "status": "unverified"},
        {"type": "hypothesis", "content": "You can deliver this", "status": "unverified"},
    ]


def _derive_subjective(question: str, language: str) -> list[str]:
    if language == "zh-CN":
        return ["「这个方向有前景」是你的主观判断，需要用户访谈验证", "「我能做出来」需要看你的技术栈和时间"]
    return ["'This direction has potential' is subjective — validate with user interviews", "'I can build this' depends on your stack and time"]


def _derive_external_verify(question: str, language: str) -> list[str]:
    if language == "zh-CN":
        return ["目标用户是否真的有这个痛点", "竞品是否已经解决了", "平台是否会内置"]
    return ["Do target users actually have this pain", "Have competitors solved it", "Will the platform build it in"]


def _derive_failure_reasons(
    problem_type: str,
    profile: UserProfile | None = None,
    language: str = "zh-CN",
) -> list[str]:
    mapping_zh: dict[str, list[str]] = {
        "no_customers": ["没有验证付费意愿就开始开发", "解决的是伪需求", "定价错误"],
        "platform_risk": ["护城河不够深", "平台一更新就失效", "没有独有数据"],
        "uncertainty": ["信息不足就做了大投入", "忽略了沉没成本", "没有设置止损点"],
        "capability_gap": ["跳过基础直接做高级", "没有刻意练习", "缺少反馈"],
        "efficiency": ["优化了不重要的环节", "没有测量基线", "改了流程没改激励"],
    }
    mapping_en: dict[str, list[str]] = {
        "no_customers": ["Built before validating willingness to pay", "Solved a fake problem", "Wrong pricing"],
        "platform_risk": ["Moat too shallow", "Platform update kills the product", "No proprietary data"],
        "uncertainty": ["Big bet on insufficient info", "Ignored sunk cost", "No stop-loss"],
        "capability_gap": ["Skipped fundamentals", "No deliberate practice", "No feedback loop"],
        "efficiency": ["Optimised the wrong step", "No baseline measurement", "Changed process not incentives"],
    }
    mapping = mapping_zh if language == "zh-CN" else mapping_en
    base = mapping.get(problem_type, mapping.get("uncertainty", []))

    # Prepend the user's own documented error patterns if we know them.
    # These are the single most important failure signals for this user.
    if profile and profile.error_patterns:
        prefix_label = "你自己的错误模式：" if language == "zh-CN" else "Your documented failure patterns: "
        personalized = [prefix_label + pattern for pattern in profile.error_patterns[:3]]
        return personalized + list(base)
    return list(base)


def _generate_decision_anchors(
    *,
    question: str,
    key_variables: list[str],
    subjective: list[str],
    language: str,
) -> list[dict[str, Any]]:
    """Generate decision anchors that the human must explicitly accept/reject.

    These represent items the Agent proposes but CANNOT decide for the user:
    - Key variables (what matters most)
    - Assumptions (subjective judgments)
    - Success criterion (what counts as done)
    """
    anchors: list[dict[str, Any]] = []

    # Top 2 key variables as anchors
    for var in key_variables[:2]:
        anchors.append({
            "type": "key_variable",
            "content": var,
            "status": "proposed_by_agent",
            "owner": "human",
            "user_action": None,  # accept|reject|rewrite|defer
            "user_input": None,
        })

    # Top subjective judgment as anchor
    if subjective:
        anchors.append({
            "type": "assumption",
            "content": subjective[0],
            "status": "proposed_by_agent",
            "owner": "human",
            "user_action": None,
            "user_input": None,
        })

    # Success criterion anchor
    if language == "zh-CN":
        criterion = "你认为什么结果算「成功回答了这个问题」？"
    else:
        criterion = "What outcome would count as 'successfully answering this question'?"
    anchors.append({
        "type": "success_criterion",
        "content": criterion,
        "status": "proposed_by_agent",
        "owner": "human",
        "user_action": None,
        "user_input": None,
    })

    return anchors


# ---------------------------------------------------------------------------
# Action experiment generator (Layer 6)
# ---------------------------------------------------------------------------


def generate_experiment(
    *,
    diagnosis: Diagnosis,
    language: str,
) -> ActionExperiment:
    if language == "zh-CN":
        hypothesis = f"假设：{diagnosis.real_question[:80]} 的方向是可行的"
        experiment = diagnosis.minimum_verifiable_action
        cost = {"time": "本周", "money": "0 元", "effort": "3–5 小时"}
        success_metric = "至少 1 个潜在用户明确表示愿意付费或试用"
        failure_signal = "5 个用户都说不需要，或者已有免费替代"
        review_date = "7 天后"
        next_success = "做一个最小 demo 给愿意试用的用户"
        next_failure = "换一个方向或换一个客户群体重新验证"
    else:
        hypothesis = f"Hypothesis: the direction '{diagnosis.real_question[:80]}' is viable"
        experiment = diagnosis.minimum_verifiable_action
        cost = {"time": "this week", "money": "$0", "effort": "3–5 hours"}
        success_metric = "At least 1 potential user explicitly willing to pay or trial"
        failure_signal = "5 users say no need, or a free alternative already exists"
        review_date = "7 days"
        next_success = "Build a minimal demo for the willing user"
        next_failure = "Pivot direction or target a different customer segment"

    return ActionExperiment(
        id=_id("exp"),
        tenant_id=diagnosis.tenant_id,
        hypothesis=hypothesis,
        experiment=experiment,
        cost=cost,
        success_metric=success_metric,
        failure_signal=failure_signal,
        review_date=review_date,
        next_if_success=next_success,
        next_if_failure=next_failure,
        status="planned",
        actual_result="",
        created_at=_utc(),
        updated_at=_utc(),
    )


# ---------------------------------------------------------------------------
# Learning review generator (Layer 7)
# ---------------------------------------------------------------------------


def generate_review_template(
    *,
    experiment: ActionExperiment,
    language: str,
) -> LearningReview:
    if language == "zh-CN":
        return LearningReview(
            id=_id("rev"),
            tenant_id=experiment.tenant_id,
            experiment_id=experiment.id,
            original_judgment=experiment.hypothesis,
            actual_result="（待填写：实际发生了什么）",
            gap="（待填写：判断与现实的差异）",
            root_cause="unknown",
            signal_for_next_time="（待填写：下次遇到类似问题先看什么信号）",
            knowledge_card_title="（待填写：这次经验沉淀成什么标题）",
            knowledge_card_body="（待填写：核心教训 + 可复用的 SOP）",
            created_at=_utc(),
        )
    return LearningReview(
        id=_id("rev"),
        tenant_id=experiment.tenant_id,
        experiment_id=experiment.id,
        original_judgment=experiment.hypothesis,
        actual_result="(fill in: what actually happened)",
        gap="(fill in: difference between judgment and reality)",
        root_cause="unknown",
        signal_for_next_time="(fill in: what signal to check first next time)",
        knowledge_card_title="(fill in: title for the lesson learned)",
        knowledge_card_body="(fill in: core lesson + reusable SOP)",
        created_at=_utc(),
    )


# ---------------------------------------------------------------------------
# Full diagnosis pipeline (combines layers 3 + 4 + 5 + 6)
# ---------------------------------------------------------------------------


def full_diagnosis_pipeline(
    *,
    question: str,
    profile: UserProfile | None,
    language: str,
) -> dict[str, Any]:
    """Run the complete diagnosis → experiment → review-template pipeline."""

    diagnosis = generate_diagnosis(question=question, profile=profile, language=language)
    experiment = generate_experiment(diagnosis=diagnosis, language=language)
    review = generate_review_template(experiment=experiment, language=language)

    return {
        "diagnosis": diagnosis.to_dict(),
        "experiment": experiment.to_dict(),
        "review_template": review.to_dict(),
    }


# ---------------------------------------------------------------------------
# Persistence helpers (extend the existing SQLite schema)
# ---------------------------------------------------------------------------


def ensure_layers_schema(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        create table if not exists user_profiles (
          id text primary key,
          tenant_id text not null unique,
          data_json text not null,
          created_at text not null,
          updated_at text not null
        );

        create table if not exists diagnoses (
          id text primary key,
          tenant_id text not null,
          data_json text not null,
          created_at text not null
        );

        create table if not exists experiments (
          id text primary key,
          tenant_id text not null,
          data_json text not null,
          status text not null default 'planned',
          created_at text not null,
          updated_at text not null
        );

        create table if not exists learning_reviews (
          id text primary key,
          tenant_id text not null,
          experiment_id text,
          data_json text not null,
          created_at text not null
        );

        create table if not exists decision_logs (
          id text primary key,
          tenant_id text not null,
          data_json text not null,
          status text not null default 'active',
          created_at text not null
        );
        """
    )
