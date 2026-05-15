"""Model-assisted knowledge summarizer for Reality OS.

Provides structured summarization of knowledge items using configured LLM
models, with graceful degradation to deterministic tokenize + sentence
weighting when no model is available.

Design principles:
- Calls the "generator" model slot via model_registry.call_model()
- Falls back to deterministic logic if the slot is not configured or fails
- Records all model calls and steps to the trace system
- Computes divergence score between original content and generated summary
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Literal

from .knowledge_core import (
    Concept,
    KnowledgeItem,
    SourceKind,
    STOPWORDS,
    tokenize,
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class SummaryResult:
    """Structured summary output from the model summarizer."""

    core_viewpoint: str  # 核心观点
    applicable_scenario: str  # 适用场景
    key_constraints: str  # 关键约束
    full_summary: str  # 完整摘要文本
    model_used: str | None  # 使用的模型名称
    source: Literal["model", "deterministic"]  # 生成来源
    latency_ms: int | None  # 耗时
    token_estimate: float | None  # token 消耗估算
    divergence_score: float  # 与原文的语义偏差 0.0-1.0

    def to_dict(self) -> dict[str, object]:
        return {
            "core_viewpoint": self.core_viewpoint,
            "applicable_scenario": self.applicable_scenario,
            "key_constraints": self.key_constraints,
            "full_summary": self.full_summary,
            "model_used": self.model_used,
            "source": self.source,
            "latency_ms": self.latency_ms,
            "token_estimate": self.token_estimate,
            "divergence_score": round(self.divergence_score, 4),
        }


# ---------------------------------------------------------------------------
# Sentence splitting helpers
# ---------------------------------------------------------------------------

_SENTENCE_RE = re.compile(
    r"[^。！？.!?\n]+[。！？.!?\n]?",
    re.UNICODE,
)


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences using punctuation boundaries."""
    sentences = [s.strip() for s in _SENTENCE_RE.findall(text) if s.strip()]
    # If regex fails to split (e.g. no punctuation), split by newlines
    if len(sentences) <= 1 and "\n" in text:
        sentences = [line.strip() for line in text.split("\n") if line.strip()]
    return sentences


def _score_sentence(sentence: str, token_weights: dict[str, float]) -> float:
    """Score a sentence based on weighted token importance."""
    tokens = tokenize(sentence)
    if not tokens:
        return 0.0
    total = sum(token_weights.get(t, 0.0) for t in tokens)
    # Normalize by sentence length to avoid bias toward long sentences
    return total / len(tokens)


# ---------------------------------------------------------------------------
# ModelSummarizer
# ---------------------------------------------------------------------------


class ModelSummarizer:
    """Generates structured summaries for knowledge items.

    Uses the configured "generator" model slot for LLM-based summarization.
    Falls back to deterministic tokenize + sentence weighting when the model
    is unavailable or fails.
    """

    def summarize(
        self,
        *,
        title: str,
        body: str,
        source_kind: SourceKind,
        language: str = "zh-CN",
        run_id: str | None = None,
    ) -> SummaryResult:
        """Generate a structured summary. Falls back to deterministic logic
        if the generator model slot is not configured or the call fails."""
        from .model_registry import call_model, ModelCallResult
        from . import trace

        step_id = trace.record_step(
            run_id=run_id,
            step_type="model_summarize",
            status="running",
            input_value={"title": title, "source_kind": source_kind},
            model_slot="generator",
        )

        started_perf = time.perf_counter()

        # Build the prompt for structured summarization
        system_prompt = self._build_system_prompt(language)
        user_prompt = self._build_user_prompt(title, body, source_kind, language)

        # Attempt model call
        result: ModelCallResult | None = None
        try:
            result = call_model(
                "generator",
                prompt=user_prompt,
                system=system_prompt,
                temperature=0.0,
                max_tokens=800,
                timeout=15,
                return_result=True,
                run_id=run_id,
                step_id=step_id,
            )
        except Exception:
            result = None

        latency_ms = int((time.perf_counter() - started_perf) * 1000)

        # If model call succeeded, parse the response
        if result and getattr(result, "ok", False) and result.content:
            parsed = self._parse_model_response(result.content, language)
            if parsed:
                core_viewpoint, applicable_scenario, key_constraints, full_summary = parsed
                divergence = self._compute_divergence(body, full_summary)
                summary_result = SummaryResult(
                    core_viewpoint=core_viewpoint,
                    applicable_scenario=applicable_scenario,
                    key_constraints=key_constraints,
                    full_summary=full_summary,
                    model_used=result.model_name,
                    source="model",
                    latency_ms=latency_ms,
                    token_estimate=result.cost_estimate,
                    divergence_score=divergence,
                )
                # Record successful step
                trace.record_step(
                    run_id=run_id,
                    step_type="model_summarize_complete",
                    status="completed",
                    input_value={"title": title, "source_kind": source_kind},
                    output_value={"source": "model", "model_used": result.model_name},
                    cost_estimate=result.cost_estimate,
                    model_slot="generator",
                )
                return summary_result

        # Fall back to deterministic summary
        fallback = self._deterministic_summary(title, body, language)

        # Record fallback step
        trace.record_step(
            run_id=run_id,
            step_type="model_summarize_fallback",
            status="completed",
            input_value={"title": title, "source_kind": source_kind},
            output_value={"source": "deterministic", "reason": "model_unavailable_or_failed"},
            model_slot="generator",
        )

        return fallback

    def summarize_concept(
        self,
        *,
        concept: Concept,
        items: list[KnowledgeItem],
        language: str = "zh-CN",
        run_id: str | None = None,
    ) -> str:
        """Generate a summary for a concept node aggregating its items."""
        if not items:
            return concept.summary or concept.label

        # Collect key sentences from all items under this concept
        all_text_parts: list[str] = []
        for item in items[:10]:  # Limit to 10 items to avoid excessive length
            all_text_parts.append(f"{item.title}: {item.body[:200]}")

        combined = "\n".join(all_text_parts)

        # Use deterministic approach: extract top weighted sentences
        tokens = tokenize(combined)
        token_freq: dict[str, int] = {}
        for t in tokens:
            if t not in STOPWORDS:
                token_freq[t] = token_freq.get(t, 0) + 1

        max_freq = max(token_freq.values()) if token_freq else 1
        token_weights = {t: freq / max_freq for t, freq in token_freq.items()}

        sentences = _split_sentences(combined)
        scored = [(s, _score_sentence(s, token_weights)) for s in sentences]
        scored.sort(key=lambda x: x[1], reverse=True)

        # Take top 3 sentences as concept summary
        top_sentences = [s for s, _ in scored[:3]]
        summary = " ".join(top_sentences)

        return summary if summary else concept.summary or concept.label

    def detect_overlap(
        self,
        *,
        tenant_id: str,
        threshold: float = 0.7,
        run_id: str | None = None,
    ) -> list[tuple[str, str, float]]:
        """Identify knowledge item pairs with token overlap above threshold.

        Returns list of (item_id_a, item_id_b, overlap_score) tuples.
        Uses Jaccard similarity on token sets.
        """
        from .knowledge_core import get_core

        core = get_core()
        # Load all items for the tenant (use a large limit for overlap detection)
        items = core.library_list(tenant_id=tenant_id, limit=500)
        if not items:
            return []

        # Build token sets for each item
        item_tokens: list[tuple[str, set[str]]] = []
        for item in items:
            tokens = set(tokenize(f"{item.title}\n{item.body}"))
            tokens -= STOPWORDS
            if tokens:
                item_tokens.append((item.id, tokens))

        # Compare all pairs
        overlaps: list[tuple[str, str, float]] = []
        for i in range(len(item_tokens)):
            for j in range(i + 1, len(item_tokens)):
                id_a, tokens_a = item_tokens[i]
                id_b, tokens_b = item_tokens[j]
                # Jaccard similarity
                intersection = len(tokens_a & tokens_b)
                union = len(tokens_a | tokens_b)
                if union == 0:
                    continue
                similarity = intersection / union
                if similarity >= threshold:
                    overlaps.append((id_a, id_b, round(similarity, 4)))

        return overlaps

    # ------------------------------------------------------------------
    # Private methods
    # ------------------------------------------------------------------

    def _deterministic_summary(
        self, title: str, body: str, language: str
    ) -> SummaryResult:
        """Deterministic fallback: tokenize + sentence weighting summary."""
        full_text = f"{title}\n{body}"
        tokens = tokenize(full_text)

        # Build token frequency weights (TF-based)
        token_freq: dict[str, int] = {}
        for t in tokens:
            if t not in STOPWORDS:
                token_freq[t] = token_freq.get(t, 0) + 1

        max_freq = max(token_freq.values()) if token_freq else 1
        token_weights = {t: freq / max_freq for t, freq in token_freq.items()}

        # Split into sentences and score them
        sentences = _split_sentences(body)
        if not sentences:
            sentences = [body[:500]] if body else [title]

        scored = [(s, _score_sentence(s, token_weights)) for s in sentences]
        scored.sort(key=lambda x: x[1], reverse=True)

        # Extract structured fields from top sentences
        top_sentences = [s for s, _ in scored[:5]]

        # Core viewpoint: highest scored sentence
        core_viewpoint = top_sentences[0] if top_sentences else title

        # Applicable scenario: derive from source context or second sentence
        if len(top_sentences) > 1:
            applicable_scenario = top_sentences[1]
        else:
            applicable_scenario = (
                "通用场景" if language.startswith("zh") else "General scenario"
            )

        # Key constraints: third sentence or generic
        if len(top_sentences) > 2:
            key_constraints = top_sentences[2]
        else:
            key_constraints = (
                "无特殊约束" if language.startswith("zh") else "No special constraints"
            )

        # Full summary: top 3 sentences joined
        full_summary = " ".join(top_sentences[:3])

        divergence = self._compute_divergence(body, full_summary)

        return SummaryResult(
            core_viewpoint=core_viewpoint,
            applicable_scenario=applicable_scenario,
            key_constraints=key_constraints,
            full_summary=full_summary,
            model_used=None,
            source="deterministic",
            latency_ms=None,
            token_estimate=None,
            divergence_score=divergence,
        )

    def _compute_divergence(self, original: str, summary: str) -> float:
        """Compute semantic divergence between original and summary.

        Uses token overlap ratio: 1.0 - (shared_tokens / summary_tokens).
        A score of 0.0 means the summary is entirely composed of original tokens.
        A score of 1.0 means no overlap at all.
        """
        original_tokens = set(tokenize(original))
        summary_tokens = set(tokenize(summary))

        if not summary_tokens:
            return 0.0

        # Remove stopwords for more meaningful comparison
        original_tokens -= STOPWORDS
        summary_tokens -= STOPWORDS

        if not summary_tokens:
            return 0.0

        shared = len(summary_tokens & original_tokens)
        divergence = 1.0 - (shared / len(summary_tokens))
        return max(0.0, min(1.0, divergence))

    def _build_system_prompt(self, language: str) -> str:
        """Build the system prompt for the summarization model."""
        if language.startswith("zh"):
            return (
                "你是一个知识摘要助手。请根据提供的知识内容生成结构化摘要。\n"
                "输出格式必须严格遵循以下结构（每行一个字段）：\n"
                "核心观点: <一句话概括核心观点>\n"
                "适用场景: <描述适用的场景或条件>\n"
                "关键约束: <列出关键限制或注意事项>\n"
                "完整摘要: <2-3句话的完整摘要>"
            )
        return (
            "You are a knowledge summarization assistant. Generate a structured summary.\n"
            "Output format must strictly follow this structure (one field per line):\n"
            "Core Viewpoint: <one sentence summarizing the core viewpoint>\n"
            "Applicable Scenario: <describe applicable scenarios or conditions>\n"
            "Key Constraints: <list key limitations or considerations>\n"
            "Full Summary: <2-3 sentence complete summary>"
        )

    def _build_user_prompt(
        self, title: str, body: str, source_kind: SourceKind, language: str
    ) -> str:
        """Build the user prompt with the knowledge content."""
        # Truncate body to avoid exceeding token limits
        truncated_body = body[:3000] if len(body) > 3000 else body

        if language.startswith("zh"):
            return (
                f"请为以下知识内容生成结构化摘要：\n\n"
                f"标题: {title}\n"
                f"来源类型: {source_kind}\n"
                f"内容:\n{truncated_body}"
            )
        return (
            f"Please generate a structured summary for the following knowledge:\n\n"
            f"Title: {title}\n"
            f"Source type: {source_kind}\n"
            f"Content:\n{truncated_body}"
        )

    def _parse_model_response(
        self, response: str, language: str
    ) -> tuple[str, str, str, str] | None:
        """Parse the model's structured response into fields.

        Returns (core_viewpoint, applicable_scenario, key_constraints, full_summary)
        or None if parsing fails.
        """
        lines = response.strip().split("\n")

        # Define field markers for both languages
        if language.startswith("zh"):
            markers = {
                "core_viewpoint": ("核心观点:", "核心观点："),
                "applicable_scenario": ("适用场景:", "适用场景："),
                "key_constraints": ("关键约束:", "关键约束："),
                "full_summary": ("完整摘要:", "完整摘要："),
            }
        else:
            markers = {
                "core_viewpoint": ("Core Viewpoint:",),
                "applicable_scenario": ("Applicable Scenario:",),
                "key_constraints": ("Key Constraints:",),
                "full_summary": ("Full Summary:",),
            }

        fields: dict[str, str] = {}
        for line in lines:
            stripped = line.strip()
            for field_name, prefixes in markers.items():
                for prefix in prefixes:
                    if stripped.startswith(prefix):
                        value = stripped[len(prefix):].strip()
                        if value:
                            fields[field_name] = value
                        break

        # All four fields must be present
        required = ("core_viewpoint", "applicable_scenario", "key_constraints", "full_summary")
        if all(f in fields for f in required):
            return (
                fields["core_viewpoint"],
                fields["applicable_scenario"],
                fields["key_constraints"],
                fields["full_summary"],
            )

        # If structured parsing fails, try to use the full response as summary
        if len(response.strip()) > 20:
            # Use first sentence as core viewpoint, rest as summary
            sentences = _split_sentences(response)
            if len(sentences) >= 2:
                return (
                    sentences[0],
                    sentences[1] if len(sentences) > 1 else "",
                    sentences[2] if len(sentences) > 2 else "",
                    response.strip()[:500],
                )

        return None
