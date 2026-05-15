"""Deterministic, mock-safe helpers for three compat features:

* vision caption + OCR localized to the user's UI language,
* first-principles supervisor digest,
* model-intelligence probing that maps scores to a workflow strategy.

All functions are pure-Python, have no external model calls, and return
stable shapes. They exist so the web can exercise the feature surface in
mock-safe mode; when a real Model_Gateway provider is wired up the wrappers
in the compat router are the only place that changes.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Literal


Language = Literal["zh-CN", "en"]

_LOCALIZED_TEXT: dict[str, dict[Language, str]] = {
    "caption_fallback": {
        "zh-CN": "未检测到模型，返回结构化占位说明。",
        "en": "No vision model was invoked; returning a structured placeholder description.",
    },
    "caption_generic": {
        "zh-CN": "图像包含屏幕截图或文档内容，含文本区块与结构化布局。",
        "en": "The image appears to contain a screenshot or document with structured text blocks.",
    },
    "ocr_empty": {
        "zh-CN": "未在图像中识别出文字。",
        "en": "No text was detected in the image.",
    },
    "ocr_truncated_suffix": {
        "zh-CN": "（已截断）",
        "en": " (truncated)",
    },
    "visual_bullet_layout": {
        "zh-CN": "布局以网格为主，视觉重心偏上方。",
        "en": "Grid-biased layout with the visual weight toward the upper region.",
    },
    "visual_bullet_palette": {
        "zh-CN": "配色冷静，留白充足，适合长时间阅读。",
        "en": "Calm palette with generous whitespace, suited for long reading sessions.",
    },
    "visual_bullet_focus": {
        "zh-CN": "主要主体位于画面中部。",
        "en": "The primary subject sits near the centre of the frame.",
    },
    "supervisor_no_tasks": {
        "zh-CN": "当前没有进行中的 Agent 任务。",
        "en": "No Agent task is active right now.",
    },
    "supervisor_next_action": {
        "zh-CN": "下一步：{action}",
        "en": "Next step: {action}",
    },
    "supervisor_blocked_on": {
        "zh-CN": "当前被以下事项阻塞：{blocker}",
        "en": "Currently blocked on: {blocker}",
    },
    "supervisor_drift_safe": {
        "zh-CN": "所有步骤都在计划范围内，无漂移。",
        "en": "Every step is within plan tolerance; no drift detected.",
    },
    "supervisor_drift_alert": {
        "zh-CN": "检测到 {n} 项潜在漂移或待审批步骤，需关注。",
        "en": "{n} potential drift or pending-approval step(s) detected.",
    },
}


def localized(key: str, language: Language, /, **params: Any) -> str:
    entry = _LOCALIZED_TEXT.get(key, {}).get(language) or _LOCALIZED_TEXT.get(key, {}).get("en", key)
    if params:
        try:
            return entry.format(**params)
        except (KeyError, IndexError):
            return entry
    return entry


# ---------------------------------------------------------------------------
# 1. Vision
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VisionDescription:
    language: Language
    source: Literal["mock-safe", "provider"]
    caption: str
    ocr_text: str
    visual_description: list[str]
    warnings: list[str]
    evidence_hash: str


def describe_image(
    *,
    language: Language,
    image_bytes: bytes | None,
    image_hint: str | None,
    user_notes: str | None,
) -> VisionDescription:
    """Deterministic stand-in for a vision-capable model.

    The implementation is intentionally mock-safe: it never uploads the image
    and it never calls an external model from the browser or the server. It
    returns a structured, language-aware description so the rest of the UI
    (clarification, decision memo, evidence ledger) has a predictable payload
    to consume until a real provider is configured.
    """

    warnings: list[str] = []
    payload = image_bytes or b""
    digest = hashlib.sha256(payload).hexdigest()[:16] if payload else "no-bytes"

    hint = (image_hint or "").strip()
    notes = (user_notes or "").strip()

    caption_parts = [localized("caption_generic", language)]
    if hint:
        caption_parts.append(
            (
                "用户提示：{0}。".format(hint)
                if language == "zh-CN"
                else "User hint: {0}.".format(hint)
            )
        )
    if notes:
        caption_parts.append(
            (
                "附加说明：{0}。".format(notes)
                if language == "zh-CN"
                else "Additional notes: {0}.".format(notes)
            )
        )

    caption = " ".join(caption_parts).strip() or localized("caption_fallback", language)

    ocr_candidate = _derive_ocr(hint, notes)
    if not ocr_candidate:
        ocr = localized("ocr_empty", language)
    else:
        ocr = ocr_candidate
        if len(ocr) > 400:
            ocr = ocr[:400] + localized("ocr_truncated_suffix", language)

    visual = [
        localized("visual_bullet_layout", language),
        localized("visual_bullet_palette", language),
        localized("visual_bullet_focus", language),
    ]

    if not image_bytes:
        warnings.append(
            "No image payload was provided; response is a language-aware placeholder only."
        )

    return VisionDescription(
        language=language,
        source="mock-safe",
        caption=caption,
        ocr_text=ocr,
        visual_description=visual,
        warnings=warnings,
        evidence_hash=digest,
    )


_WORD_RE = re.compile(r"[\w\u4e00-\u9fff]+")


def _derive_ocr(*snippets: str) -> str:
    tokens: list[str] = []
    for snippet in snippets:
        tokens.extend(_WORD_RE.findall(snippet or ""))
    if not tokens:
        return ""
    joined = " ".join(tokens)
    return joined


# ---------------------------------------------------------------------------
# 2. Supervisor first-principles digest
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SupervisorDigest:
    language: Language
    goal: str
    single_next_action: str
    blocked_on: list[str]
    drift_alert: str
    risk_counts: dict[str, int]
    approvals_waiting: int
    generated_from: list[str]


def summarize_supervisor(snapshot: dict[str, Any], language: Language) -> SupervisorDigest:
    """Reduce a supervisor snapshot to the first-principles essentials.

    Heuristic (first-principles cut, reproducible with a fixed input):
      * goal = workflow name.
      * blocked_on = tasks with status containing "blocked" or "approval_required".
      * single_next_action = first running or approval-required step we find; if
        none, the first pending step.
      * drift_alert = count of steps with status in {blocked, approval_required}
        plus approvals with status != approved.
      * risk_counts = histogram of `task.risk`.
    """

    workflow = snapshot.get("workflow") or {}
    tasks: list[dict[str, Any]] = snapshot.get("agentTasks") or []
    steps: list[dict[str, Any]] = snapshot.get("steps") or []
    approvals: list[dict[str, Any]] = snapshot.get("approvalRequests") or []

    goal = str(workflow.get("name") or "").strip() or (
        "未命名监督流程" if language == "zh-CN" else "Unnamed supervisor workflow"
    )

    blocked_on: list[str] = []
    for task in tasks:
        status = str(task.get("status") or "").lower()
        title = str(task.get("title") or "").strip()
        if any(marker in status for marker in ("blocked", "approval", "waiting", "pending")) and title:
            blocked_on.append(title)

    next_action = _pick_next_action(steps, tasks, language)

    drift_count = 0
    for step in steps:
        status = str(step.get("status") or "").lower()
        if any(marker in status for marker in ("blocked", "approval", "drift", "violation")):
            drift_count += 1
    for approval in approvals:
        if str(approval.get("status") or "").lower() != "approved":
            drift_count += 1

    drift_alert = (
        localized("supervisor_drift_alert", language, n=drift_count)
        if drift_count
        else localized("supervisor_drift_safe", language)
    )

    risk_counts: dict[str, int] = {}
    for task in tasks:
        risk = str(task.get("risk") or "").lower() or "unknown"
        risk_counts[risk] = risk_counts.get(risk, 0) + 1

    approvals_waiting = sum(
        1 for approval in approvals if str(approval.get("status") or "").lower() != "approved"
    )

    generated_from = [
        "workflow.name",
        "agentTasks[*].status",
        "agentTasks[*].risk",
        "steps[*].status",
        "approvalRequests[*].status",
    ]

    return SupervisorDigest(
        language=language,
        goal=goal,
        single_next_action=next_action,
        blocked_on=blocked_on,
        drift_alert=drift_alert,
        risk_counts=risk_counts,
        approvals_waiting=approvals_waiting,
        generated_from=generated_from,
    )


def _pick_next_action(
    steps: list[dict[str, Any]], tasks: list[dict[str, Any]], language: Language
) -> str:
    priority_status = ("running", "approval_required", "waiting_approval", "pending_review")
    for target_status in priority_status:
        for step in steps:
            if str(step.get("status") or "").lower() == target_status:
                label = str(step.get("label") or "").strip()
                if label:
                    return localized("supervisor_next_action", language, action=label)
    if tasks:
        first = str(tasks[0].get("title") or "").strip()
        if first:
            return localized("supervisor_next_action", language, action=first)
    return localized("supervisor_no_tasks", language)


# ---------------------------------------------------------------------------
# 3. Model intelligence probe + workflow strategy
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ModelProbeResult:
    id: str
    label: str
    expected: str
    actual: str
    passed: bool
    score: float
    detail: str


@dataclass(frozen=True)
class ModelIntelligenceReport:
    language: Language
    provider: str
    model: str
    source: Literal["mock-safe", "provider"]
    tier: Literal["flagship", "mid", "basic", "insufficient"]
    aggregate_score: float
    probes: list[ModelProbeResult]
    workflow_strategy: dict[str, Any]
    recommendation: str
    notes: list[str]


_PROBES_DEFINITION: list[dict[str, Any]] = [
    {
        "id": "instruction_following",
        "label": {
            "zh-CN": "指令遵循",
            "en": "Instruction following",
        },
        "prompt": {
            "zh-CN": "请只回复单词 READY，不要任何其他字符。",
            "en": "Reply with the single word READY and nothing else.",
        },
        "expected": "READY",
    },
    {
        "id": "concise_output",
        "label": {
            "zh-CN": "简洁输出",
            "en": "Concise output",
        },
        "prompt": {
            "zh-CN": "用不超过 10 个字描述“第一性原理”。",
            "en": "Describe 'first principles' in ten words or fewer.",
        },
        "expected": "brief",
    },
    {
        "id": "structured_json",
        "label": {
            "zh-CN": "结构化 JSON",
            "en": "Structured JSON",
        },
        "prompt": {
            "zh-CN": "返回 JSON：{\"ok\": true}，不要 markdown，不要注释。",
            "en": 'Return JSON: {"ok": true}. No markdown, no commentary.',
        },
        "expected": '{"ok": true}',
    },
    {
        "id": "multi_step_reasoning",
        "label": {
            "zh-CN": "多步推理",
            "en": "Multi-step reasoning",
        },
        "prompt": {
            "zh-CN": "一个苹果原本 5 元，打八折后再买二送一，买 3 个实际付多少元？只返回数字。",
            "en": "An apple is $5, 20% off, buy-2-get-1. Paying for 3 apples, how much? Return the number only.",
        },
        "expected": "8",
    },
]


def run_model_probes(
    *,
    provider: str,
    model: str,
    language: Language,
    runner: Any | None = None,
) -> ModelIntelligenceReport:
    """Run the deterministic probe battery and derive a workflow strategy.

    ``runner`` may be a callable ``(prompt: str) -> str`` that actually hits a
    provider. If it is not supplied (the default in this iteration), each probe
    is scored via a mock-safe heuristic that uses the model string to derive a
    stable tier (so the UI shows meaningful differences across models without
    having to call a real provider).
    """

    probes: list[ModelProbeResult] = []
    used_runner = bool(runner)

    for definition in _PROBES_DEFINITION:
        label_map = definition["label"]
        prompt = definition["prompt"].get(language) or definition["prompt"]["en"]
        expected = definition["expected"]

        if runner is None:
            passed, score, actual, detail = _mock_probe_score(definition["id"], provider, model)
        else:
            try:
                actual_raw = runner(prompt)
                actual = str(actual_raw).strip()
            except Exception as exc:  # pragma: no cover - provider errors
                actual = ""
                passed = False
                score = 0.0
                detail = f"Provider call raised: {exc}"
            else:
                passed, score, detail = _grade_probe(definition["id"], expected, actual)

        probes.append(
            ModelProbeResult(
                id=definition["id"],
                label=label_map.get(language) or label_map["en"],
                expected=expected,
                actual=actual if used_runner else "",
                passed=passed,
                score=round(score, 3),
                detail=detail,
            )
        )

    aggregate = sum(probe.score for probe in probes) / max(len(probes), 1)
    tier = _classify_tier(aggregate)
    strategy = _strategy_for_tier(tier, language)
    recommendation = _recommendation_for_tier(tier, language)

    notes: list[str] = []
    if not used_runner:
        notes.append(
            "Mock-safe probes: no provider was invoked. Scores are derived deterministically from the model id."
            if language == "en"
            else "当前为 mock-safe 评估：未调用真实提供方，分数由模型 id 稳定推导。"
        )

    return ModelIntelligenceReport(
        language=language,
        provider=provider,
        model=model,
        source="provider" if used_runner else "mock-safe",
        tier=tier,
        aggregate_score=round(aggregate, 3),
        probes=probes,
        workflow_strategy=strategy,
        recommendation=recommendation,
        notes=notes,
    )


def _grade_probe(probe_id: str, expected: str, actual: str) -> tuple[bool, float, str]:
    stripped = actual.strip()
    if probe_id == "instruction_following":
        exact = stripped.upper() == "READY"
        return exact, (1.0 if exact else 0.1), (
            "Exact single-word match." if exact else "Did not reply with exactly READY."
        )
    if probe_id == "concise_output":
        words = len([token for token in stripped.split() if token])
        if words == 0:
            return False, 0.0, "Empty response."
        if words <= 10:
            return True, 1.0, f"Returned {words} words."
        if words <= 20:
            return False, 0.6, f"Returned {words} words; expected <= 10."
        return False, 0.2, f"Returned {words} words; expected <= 10."
    if probe_id == "structured_json":
        compact = stripped.replace(" ", "").lower()
        if compact == '{"ok":true}':
            return True, 1.0, "Exact JSON match."
        if "ok" in compact and "true" in compact:
            return False, 0.55, "JSON-ish but not exact."
        return False, 0.1, "Not recognisable JSON."
    if probe_id == "multi_step_reasoning":
        if stripped == "8":
            return True, 1.0, "Correct numeric answer."
        if "8" in stripped and len(stripped) <= 8:
            return False, 0.5, "Answer includes 8 but not clean."
        return False, 0.1, "Did not produce 8."
    return False, 0.0, "Unknown probe."


def _mock_probe_score(probe_id: str, provider: str, model: str) -> tuple[bool, float, str, str]:
    seed = f"{provider}:{model}:{probe_id}".encode("utf-8")
    digest = hashlib.sha256(seed).digest()
    # Derive a 0..1 deterministic per-probe score.
    score = digest[0] / 255.0
    tier_bias = _mock_tier_bias(model)
    # Nudge score toward the tier bias (flagship models should win more probes).
    blended = max(0.0, min(1.0, 0.3 + 0.5 * tier_bias + 0.2 * score))
    passed = blended >= 0.6
    detail = "Mock-safe heuristic score derived from the model id; no provider was invoked."
    return passed, blended, "", detail


def _mock_tier_bias(model: str) -> float:
    lowered = model.lower()
    if any(marker in lowered for marker in ("gpt-4", "claude-3.5", "claude-3-opus", "o1", "sonnet", "flagship")):
        return 1.0
    if any(marker in lowered for marker in ("gpt-3.5", "haiku", "mid", "mistral-medium", "llama3-70")):
        return 0.55
    if any(marker in lowered for marker in ("tinyllama", "gemma-2b", "phi-2", "basic")):
        return 0.25
    # server-configured / unknown → mid-range default
    return 0.5


def _classify_tier(
    aggregate: float,
) -> Literal["flagship", "mid", "basic", "insufficient"]:
    if aggregate >= 0.85:
        return "flagship"
    if aggregate >= 0.6:
        return "mid"
    if aggregate >= 0.35:
        return "basic"
    return "insufficient"


def _strategy_for_tier(
    tier: Literal["flagship", "mid", "basic", "insufficient"],
    language: Language,
) -> dict[str, Any]:
    if tier == "flagship":
        return {
            "prompt_strategy": "single_stage_instruction",
            "description": (
                "Top-tier model: one well-structured prompt is enough. Retrieval is kept lean, context budget stays default."
                if language == "en"
                else "顶级模型：单条结构化提示即可完成；检索与上下文预算保持默认。"
            ),
            "planner_depth": 1,
            "retrieval_top_k": 6,
            "enable_self_consistency": False,
            "enable_decompose_and_solve": False,
            "quality_threshold": 75,
        }
    if tier == "mid":
        return {
            "prompt_strategy": "two_stage_clarify_then_answer",
            "description": (
                "Mid-tier model: separate clarification from answering; reuse retrieved evidence verbatim."
                if language == "en"
                else "中等模型：将澄清与回答分两步；证据尽量逐字复用，避免压缩歧义。"
            ),
            "planner_depth": 2,
            "retrieval_top_k": 8,
            "enable_self_consistency": False,
            "enable_decompose_and_solve": True,
            "quality_threshold": 70,
        }
    if tier == "basic":
        return {
            "prompt_strategy": "multi_stage_decompose_verify",
            "description": (
                "Basic model: decompose sub-questions, verify each answer, then synthesise with self-consistency."
                if language == "en"
                else "基础模型：逐个子问题分解回答并验证，再做多次一致性检查后汇总。"
            ),
            "planner_depth": 4,
            "retrieval_top_k": 12,
            "enable_self_consistency": True,
            "enable_decompose_and_solve": True,
            "quality_threshold": 65,
        }
    return {
        "prompt_strategy": "not_recommended",
        "description": (
            "Model scored below the minimum bar for Reality OS workflows. Pick another provider or model."
            if language == "en"
            else "当前模型低于 Reality OS 的最低可用标准，请更换提供方或型号。"
        ),
        "planner_depth": 0,
        "retrieval_top_k": 0,
        "enable_self_consistency": False,
        "enable_decompose_and_solve": False,
        "quality_threshold": 0,
    }


def _recommendation_for_tier(
    tier: Literal["flagship", "mid", "basic", "insufficient"],
    language: Language,
) -> str:
    if language == "en":
        mapping = {
            "flagship": "Use single-stage prompts. Keep context lean; rely on the model for orchestration.",
            "mid": "Split clarification and answering. Keep evidence citations verbatim.",
            "basic": "Decompose every question, verify each intermediate answer, then cross-check.",
            "insufficient": "Do not use for decision-critical flows. Switch provider / model.",
        }
    else:
        mapping = {
            "flagship": "走单阶段提示即可，不再拆分；上下文可留足空间给证据。",
            "mid": "澄清与回答分两步；证据逐字引用，避免模型改写。",
            "basic": "逐个子问题拆解并验证，再做一致性交叉检查。",
            "insufficient": "不建议承担决策闭环任务，请更换提供方或型号。",
        }
    return mapping[tier]
