"""Zero-Context Audit Agent — unbiased verification of any Agent output.

The audit agent receives ONLY the output text (no original question, no
context, no citations). It evaluates the output purely on internal consistency,
logical soundness, and structural quality.

This implements the "red-blue adversarial" pattern: a fresh-context reviewer
that cannot be influenced by sunk-cost bias or context leakage from the
generation step.

Design principles:
- Zero context: auditor sees only the output, never the input
- Configurable dimensions: logic, evidence, feasibility, subjectivity
- Deterministic fallback when no LLM verifier is configured
- Results written to audit_log for /eval tracking
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from .knowledge_core import get_core, _utc_now_iso, _new_id, tokenize, STOPWORDS
from . import expert_rubric as expert_rubric_mod
from .feature_flags import expert_gap_enabled


AuditDimension = Literal[
    "logic",
    "evidence",
    "feasibility",
    "subjectivity",
    "completeness",
    "expert_gap",
]

ALL_DIMENSIONS: list[AuditDimension] = [
    "logic",
    "evidence",
    "feasibility",
    "subjectivity",
    "completeness",
    "expert_gap",
]


@dataclass
class AuditIssue:
    dimension: AuditDimension
    severity: Literal["critical", "warning", "info"]
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension,
            "severity": self.severity,
            "description": self.description,
        }


@dataclass
class AuditResult:
    passed: bool
    score: float  # 0.0 - 1.0
    issues: list[AuditIssue]
    source: Literal["deterministic", "llm"]
    output_type: str
    audited_at: str
    expert_gap: dict[str, Any] | None = None
    rubric_applied: dict[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "score": round(self.score, 3),
            "issues": [i.to_dict() for i in self.issues],
            "source": self.source,
            "output_type": self.output_type,
            "audited_at": self.audited_at,
            "expert_gap": self.expert_gap,
            "rubric_applied": self.rubric_applied,
        }


def zero_context_audit(
    *,
    output_text: str,
    output_type: Literal["answer", "diagnosis", "experiment", "review"] = "answer",
    language: str = "zh-CN",
    dimensions: list[AuditDimension] | None = None,
    run_id: str | None = None,
    domain: str | None = None,
    rubric_version: str | None = None,
) -> AuditResult:
    """Perform a zero-context audit on any Agent output.

    The auditor does NOT see the original question or context.
    It only evaluates the output text itself for internal quality.

    The optional ``domain`` / ``rubric_version`` parameters select which
    Expert Rubric the new ``expert_gap`` dimension applies (R2.3, R2.6).
    When :func:`feature_flags.expert_gap_enabled` is ``False`` the new
    dimension is skipped and the result mirrors the legacy 5-dim shape.
    """
    if not output_text or not output_text.strip():
        return AuditResult(
            passed=True,
            score=1.0,
            issues=[],
            source="deterministic",
            output_type=output_type,
            audited_at=_utc_now_iso(),
        )

    dims = dimensions or ALL_DIMENSIONS
    if "expert_gap" in dims and not expert_gap_enabled():
        dims = [d for d in dims if d != "expert_gap"]
    issues: list[AuditIssue] = []

    expert_gap_payload: dict[str, Any] | None = None
    rubric_applied: dict[str, str] | None = None
    if "expert_gap" in dims:
        expert_gap_payload, rubric_applied, gap_issues = _check_expert_gap(
            output_text, domain=domain, version=rubric_version
        )
        issues.extend(gap_issues)
        # Remove from ``dims`` so the LLM/deterministic branches do not
        # also try to audit it.
        dims = [d for d in dims if d != "expert_gap"]

    # Try LLM audit first
    llm_result = _try_llm_audit(output_text, output_type, language, dims, run_id=run_id)
    if llm_result is not None:
        llm_result.expert_gap = expert_gap_payload
        llm_result.rubric_applied = rubric_applied
        if expert_gap_payload is not None:
            llm_result.issues.extend(issues)
        return llm_result

    # Fallback: deterministic audit
    if "logic" in dims:
        issues.extend(_check_logic(output_text, language))
    if "evidence" in dims:
        issues.extend(_check_evidence(output_text, language))
    if "feasibility" in dims:
        issues.extend(_check_feasibility(output_text, language))
    if "subjectivity" in dims:
        issues.extend(_check_subjectivity(output_text, language))
    if "completeness" in dims:
        issues.extend(_check_completeness(output_text, output_type, language))

    # Score: start at 1.0, deduct per issue
    score = 1.0
    for issue in issues:
        if issue.severity == "critical":
            score -= 0.3
        elif issue.severity == "warning":
            score -= 0.15
        else:
            score -= 0.05
    score = max(0.0, min(1.0, score))

    return AuditResult(
        passed=score >= 0.5 and not any(i.severity == "critical" for i in issues),
        score=score,
        issues=issues,
        source="deterministic",
        output_type=output_type,
        audited_at=_utc_now_iso(),
        expert_gap=expert_gap_payload,
        rubric_applied=rubric_applied,
    )


# ---------------------------------------------------------------------------
# Expert gap audit dimension (R2.3, Property 8)
# ---------------------------------------------------------------------------


def _check_expert_gap(
    text: str,
    *,
    domain: str | None,
    version: str | None,
) -> tuple[dict[str, Any] | None, dict[str, str] | None, list[AuditIssue]]:
    """Score the answer against the active Expert Rubric.

    Returns ``(expert_gap_payload, rubric_applied, issues)``. When the
    rubric loader refused or no rubric (not even ``default``) is available,
    we fall back to no-op (R2.5): payload is ``None`` and no issues are
    raised so the existing five dimensions still cover the answer.
    """

    # Lazily refresh the rubric cache the first time we run.
    expert_rubric_mod.load_all()
    rubric, source = expert_rubric_mod.resolve_rubric(domain, version=version)
    if rubric is None:
        return None, None, []

    gap = expert_rubric_mod.expert_gap_score(text, rubric)
    payload = gap.to_dict()
    rubric_applied = {
        "domain": rubric.domain,
        "version": rubric.version,
        "source": source,
    }
    issues: list[AuditIssue] = []
    if gap.expert_gap_score < 0.5:
        issues.append(
            AuditIssue(
                dimension="expert_gap",
                severity="warning",
                description=(
                    f"answer covers only {gap.expert_gap_score:.2f} of the "
                    f"expert rubric ({rubric.domain}@{rubric.version})"
                ),
            )
        )
    return payload, rubric_applied, issues


# ---------------------------------------------------------------------------
# LLM-powered audit (uses verifier slot)
# ---------------------------------------------------------------------------


def _try_llm_audit(
    output_text: str,
    output_type: str,
    language: str,
    dimensions: list[AuditDimension],
    run_id: str | None = None,
) -> AuditResult | None:
    """Try to use the verifier model for zero-context audit."""
    try:
        from .model_registry import call_model
    except Exception:
        return None

    dims_str = ", ".join(dimensions)
    prompt = (
        "You are a zero-context auditor. You have NO knowledge of the original question or context. "
        "You can ONLY see the output below. Evaluate it strictly on these dimensions: "
        f"{dims_str}.\n\n"
        f"OUTPUT TO AUDIT ({output_type}):\n{output_text[:2000]}\n\n"
        "Respond in JSON:\n"
        '{"passed": true/false, "score": 0.0-1.0, "issues": [{"dimension": "...", "severity": "critical|warning|info", "description": "..."}]}\n'
        "Be strict. Flag any unsupported claims, logical gaps, or vague statements."
    )

    result_text = call_model(
        "verifier",
        prompt=prompt,
        temperature=0.0,
        max_tokens=500,
        timeout=12,
        run_id=run_id,
    )
    if not result_text:
        return None

    try:
        import json
        # Strip markdown fences
        content = result_text.strip()
        if content.startswith("```"):
            content = "\n".join(content.split("\n")[1:])
        if content.endswith("```"):
            content = content[:content.rfind("```")]
        content = content.strip()

        parsed = json.loads(content)
        issues = [
            AuditIssue(
                dimension=i.get("dimension", "logic"),  # type: ignore[arg-type]
                severity=i.get("severity", "warning"),  # type: ignore[arg-type]
                description=str(i.get("description", "")),
            )
            for i in parsed.get("issues", [])
        ]
        return AuditResult(
            passed=bool(parsed.get("passed", True)),
            score=max(0.0, min(1.0, float(parsed.get("score", 0.7)))),
            issues=issues,
            source="llm",
            output_type=output_type,
            audited_at=_utc_now_iso(),
        )
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Deterministic audit checks
# ---------------------------------------------------------------------------


def _check_logic(text: str, language: str) -> list[AuditIssue]:
    """Check for logical inconsistencies in the output."""
    issues: list[AuditIssue] = []

    # Check for contradictions (both X and not-X patterns)
    _CONTRADICTION_ZH = [("是", "不是"), ("可以", "不可以"), ("应该", "不应该"), ("有", "没有")]
    _CONTRADICTION_EN = [("is", "is not"), ("can", "cannot"), ("should", "should not"), ("will", "will not")]

    patterns = _CONTRADICTION_ZH if language == "zh-CN" else _CONTRADICTION_EN
    sentences = [s.strip() for s in re.split(r'[。.!！\n]', text) if s.strip()]

    for pos, neg in patterns:
        has_pos = any(pos in s for s in sentences)
        has_neg = any(neg in s for s in sentences)
        if has_pos and has_neg:
            desc = f"可能存在矛盾：同时出现「{pos}」和「{neg}」" if language == "zh-CN" else f"Potential contradiction: both '{pos}' and '{neg}' appear"
            issues.append(AuditIssue(dimension="logic", severity="warning", description=desc))
            break  # One contradiction flag is enough

    return issues


def _check_evidence(text: str, language: str) -> list[AuditIssue]:
    """Check if claims are backed by citations or markers."""
    issues: list[AuditIssue] = []

    # Check for citation markers
    has_citations = "[[" in text or "[" in text and "]" in text
    has_source_refs = "http" in text.lower() or "来源" in text or "source" in text.lower()

    if not has_citations and not has_source_refs and len(text) > 200:
        desc = "输出超过 200 字但没有任何引用标记或来源引用" if language == "zh-CN" else "Output exceeds 200 chars with no citation markers or source references"
        issues.append(AuditIssue(dimension="evidence", severity="warning", description=desc))

    return issues


def _check_feasibility(text: str, language: str) -> list[AuditIssue]:
    """Check for unrealistic claims or missing constraints."""
    issues: list[AuditIssue] = []

    # Check for absolute claims without qualifiers
    _ABSOLUTE_ZH = ("一定", "绝对", "100%", "肯定能", "必然")
    _ABSOLUTE_EN = ("definitely", "absolutely", "100%", "guaranteed", "certainly will", "always")

    absolutes = _ABSOLUTE_ZH if language == "zh-CN" else _ABSOLUTE_EN
    text_lower = text.lower()
    for word in absolutes:
        if word in text_lower:
            desc = f"使用了绝对化表述「{word}」，缺少不确定性标注" if language == "zh-CN" else f"Absolute claim '{word}' without uncertainty qualifier"
            issues.append(AuditIssue(dimension="feasibility", severity="info", description=desc))
            break

    return issues


def _check_subjectivity(text: str, language: str) -> list[AuditIssue]:
    """Check for unmarked subjective judgments."""
    issues: list[AuditIssue] = []

    # Check if subjective markers are present but not flagged
    _SUBJECTIVE_ZH = ("我认为", "我觉得", "可能", "也许", "大概")
    _SUBJECTIVE_EN = ("i think", "i believe", "probably", "maybe", "perhaps", "likely")

    markers = _SUBJECTIVE_ZH if language == "zh-CN" else _SUBJECTIVE_EN
    text_lower = text.lower()
    unmarked_count = sum(1 for m in markers if m in text_lower)

    if unmarked_count >= 3 and "[?]" not in text:
        desc = "包含多个主观判断词但未标注 [?]" if language == "zh-CN" else "Multiple subjective markers without [?] annotation"
        issues.append(AuditIssue(dimension="subjectivity", severity="warning", description=desc))

    return issues


def _check_completeness(text: str, output_type: str, language: str) -> list[AuditIssue]:
    """Check structural completeness based on output type."""
    issues: list[AuditIssue] = []

    if output_type == "answer" and len(text) < 50:
        desc = "回答过短（<50字），可能不完整" if language == "zh-CN" else "Answer too short (<50 chars), may be incomplete"
        issues.append(AuditIssue(dimension="completeness", severity="info", description=desc))

    if output_type == "diagnosis":
        # A diagnosis should mention at least a problem type and an action
        has_action_words = any(w in text.lower() for w in ("验证", "测试", "找", "问", "verify", "test", "find", "ask"))
        if not has_action_words:
            desc = "诊断中缺少可执行的行动建议" if language == "zh-CN" else "Diagnosis lacks actionable recommendations"
            issues.append(AuditIssue(dimension="completeness", severity="warning", description=desc))

    if output_type == "experiment":
        # An experiment should have a hypothesis and a metric
        has_metric = any(w in text.lower() for w in ("指标", "成功", "失败", "metric", "success", "failure"))
        if not has_metric:
            desc = "实验设计缺少成功/失败指标" if language == "zh-CN" else "Experiment design lacks success/failure metrics"
            issues.append(AuditIssue(dimension="completeness", severity="warning", description=desc))

    return issues
