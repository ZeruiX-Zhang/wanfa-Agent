"""Skill-driven search strategy engine for Reality OS.

This module implements configurable search strategy selection based on
SKILL.md files with ``type: search_strategy`` in their YAML frontmatter.
Each Search Skill defines intent signals, source selection rules, score
weight adjustments, and post-processing directives.

When a user query matches a Search Skill's intent signals, the engine
applies that Skill's configuration to guide source selection and result
scoring. When no Skill matches, the engine falls back to the existing
``_infer_sources`` deterministic logic from expert_search.py.

Design principles:
- Deterministic routing: intent signal matching is substring-based, no model needed
- Extensible: add new search strategies by dropping SKILL.md files
- Hot-reloadable: call ``reload_skills()`` to pick up changes without restart
- Graceful degradation: if no Skill matches, existing logic is used
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class SearchSkill:
    """Parsed search strategy Skill definition from a SKILL.md file."""

    id: str
    name: str
    intent_signals: list[str]  # Trigger phrases for matching
    source_rules: dict[str, Any]  # Source selection rules
    score_weights: dict[str, float]  # Score weight adjustments
    post_processing: list[str]  # Post-processing directives
    skill_path: Path


@dataclass
class SearchStrategyResult:
    """Result of strategy selection for a search query."""

    strategy_name: str  # Name of the selected strategy
    original_query: str
    optimized_query: str | None  # Model-optimized query (filled by Task 8.2)
    expanded_terms: list[str]  # Semantically expanded terms
    source_selection: list[str]  # Selected source domains
    weight_adjustments: dict[str, float]  # Score weight adjustments
    optimization_source: Literal["model", "deterministic"]


# ---------------------------------------------------------------------------
# SearchStrategyEngine
# ---------------------------------------------------------------------------


class SearchStrategyEngine:
    """Skill-driven search strategy engine.

    Loads search strategy SKILL.md files from a configurable directory and
    selects the best strategy based on query intent signals.
    """

    def __init__(self, skills_dir: Path | None = None) -> None:
        """Load search strategy Skill registry.

        Args:
            skills_dir: Directory to scan for SKILL.md files. Defaults to
                ``thinking_skills/`` relative to this module's parent (the api app).
        """
        if skills_dir is None:
            skills_dir = Path(__file__).resolve().parent.parent / "thinking_skills"
        self._skills_dir = skills_dir
        self._skills: list[SearchSkill] = []
        self._load_skills()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def select_strategy(
        self,
        *,
        query: str,
        language: str = "zh-CN",
        tenant_id: str | None = None,
    ) -> SearchStrategyResult:
        """Select the best search strategy based on query intent signals.

        1. Match the query against all loaded search skills' intent_signals
        2. If a match is found, return a SearchStrategyResult with the skill's config
        3. If no match, call _fallback_strategy() which uses _infer_sources logic

        Args:
            query: The user's search query text.
            language: Language code for the query.
            tenant_id: Optional tenant ID for future personalization.

        Returns:
            SearchStrategyResult with the selected strategy configuration.
        """
        matched_skill = self._match_search_skill(query)

        if matched_skill is not None:
            # Build source selection from skill's source_rules
            source_selection = self._resolve_sources(matched_skill.source_rules)

            return SearchStrategyResult(
                strategy_name=matched_skill.name,
                original_query=query,
                optimized_query=None,  # Will be filled by Task 8.2
                expanded_terms=[],  # Will be filled by Task 8.2
                source_selection=source_selection,
                weight_adjustments=dict(matched_skill.score_weights),
                optimization_source="deterministic",
            )

        # No skill matched — fall back to deterministic logic
        return self._fallback_strategy(query, language)

    def reload_skills(self) -> int:
        """Reload search strategy Skills from disk (hot update support).

        Returns:
            Number of search strategy Skills loaded.
        """
        self._skills.clear()
        self._load_skills()
        return len(self._skills)

    def optimize_query_with_model(
        self,
        *,
        query: str,
        language: str = "zh-CN",
        run_id: str | None = None,
    ) -> tuple[str | None, list[str]]:
        """Call the generator model to semantically expand a search query.

        Uses the configured "generator" model slot to produce synonyms,
        related concepts, and a more precise search query. Falls back to
        tokenize + stopword filtering when the model is unavailable or fails.

        Args:
            query: The user's original search query text.
            language: Language code for the query.
            run_id: Optional trace run ID for observability.

        Returns:
            Tuple of (optimized_query, expanded_terms). optimized_query is
            None when the model is unavailable and fallback is used.
        """
        from .model_registry import call_model, ModelCallResult
        from . import trace
        from .knowledge_core import tokenize, STOPWORDS

        step_id = trace.record_step(
            run_id=run_id,
            step_type="query_optimization",
            status="running",
            input_value={"query": query, "language": language},
            model_slot="generator",
        )

        started_perf = time.perf_counter()

        # Build prompts for query expansion
        system_prompt = self._build_query_optimization_system_prompt(language)
        user_prompt = self._build_query_optimization_user_prompt(query, language)

        # Attempt model call
        result: ModelCallResult | None = None
        try:
            result = call_model(
                "generator",
                prompt=user_prompt,
                system=system_prompt,
                temperature=0.0,
                max_tokens=500,
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
            parsed = self._parse_query_optimization_response(result.content)
            if parsed:
                optimized_query, expanded_terms = parsed
                # Record successful step
                trace.record_step(
                    run_id=run_id,
                    step_type="query_optimization_complete",
                    status="completed",
                    input_value={"query": query, "language": language},
                    output_value={
                        "source": "model",
                        "optimized_query": optimized_query,
                        "expanded_terms_count": len(expanded_terms),
                    },
                    cost_estimate=result.cost_estimate,
                    model_slot="generator",
                    metadata={"latency_ms": latency_ms},
                )
                return optimized_query, expanded_terms

        # Fallback: tokenize + stopword filtering
        tokens = tokenize(query)
        expanded_terms = [t for t in tokens if t not in STOPWORDS and len(t) > 1]

        # Record fallback step
        trace.record_step(
            run_id=run_id,
            step_type="query_optimization_fallback",
            status="completed",
            input_value={"query": query, "language": language},
            output_value={
                "source": "deterministic",
                "reason": "model_unavailable_or_failed",
                "expanded_terms_count": len(expanded_terms),
            },
            model_slot="generator",
            metadata={"latency_ms": latency_ms},
        )
        return None, expanded_terms

    # ------------------------------------------------------------------
    # Query optimization helpers
    # ------------------------------------------------------------------

    def _build_query_optimization_system_prompt(self, language: str) -> str:
        """Build the system prompt for query optimization."""
        if language.startswith("zh"):
            return (
                "你是一个搜索查询优化助手。请对用户的搜索查询进行语义扩展。\n"
                "输出格式必须严格遵循以下结构（每行一个字段）：\n"
                "优化查询: <更精确的搜索查询>\n"
                "同义词: <逗号分隔的同义词列表>\n"
                "相关概念: <逗号分隔的相关概念列表>\n"
                "精确搜索词: <逗号分隔的精确搜索关键词>"
            )
        return (
            "You are a search query optimization assistant. Semantically expand the user's query.\n"
            "Output format must strictly follow this structure (one field per line):\n"
            "Optimized Query: <a more precise search query>\n"
            "Synonyms: <comma-separated list of synonyms>\n"
            "Related Concepts: <comma-separated list of related concepts>\n"
            "Precise Terms: <comma-separated list of precise search keywords>"
        )

    def _build_query_optimization_user_prompt(self, query: str, language: str) -> str:
        """Build the user prompt for query optimization."""
        if language.startswith("zh"):
            return (
                f"请对以下搜索查询进行语义扩展和优化：\n\n"
                f"原始查询: {query}\n\n"
                f"请生成同义词、相关概念和更精确的搜索词。"
            )
        return (
            f"Please semantically expand and optimize the following search query:\n\n"
            f"Original query: {query}\n\n"
            f"Generate synonyms, related concepts, and more precise search terms."
        )

    def _parse_query_optimization_response(
        self, response: str
    ) -> tuple[str, list[str]] | None:
        """Parse the model's query optimization response.

        Returns (optimized_query, expanded_terms) or None if parsing fails.
        """
        lines = response.strip().split("\n")

        # Define field markers for both languages
        markers_optimized = ("优化查询:", "优化查询：", "Optimized Query:")
        markers_synonyms = ("同义词:", "同义词：", "Synonyms:")
        markers_related = ("相关概念:", "相关概念：", "Related Concepts:")
        markers_precise = ("精确搜索词:", "精确搜索词：", "Precise Terms:")

        optimized_query: str | None = None
        expanded_terms: list[str] = []

        for line in lines:
            stripped = line.strip()

            # Check optimized query
            for prefix in markers_optimized:
                if stripped.startswith(prefix):
                    value = stripped[len(prefix):].strip()
                    if value:
                        optimized_query = value
                    break

            # Check synonyms
            for prefix in markers_synonyms:
                if stripped.startswith(prefix):
                    value = stripped[len(prefix):].strip()
                    if value:
                        terms = [t.strip() for t in re.split(r"[,，、;；]", value) if t.strip()]
                        expanded_terms.extend(terms)
                    break

            # Check related concepts
            for prefix in markers_related:
                if stripped.startswith(prefix):
                    value = stripped[len(prefix):].strip()
                    if value:
                        terms = [t.strip() for t in re.split(r"[,，、;；]", value) if t.strip()]
                        expanded_terms.extend(terms)
                    break

            # Check precise terms
            for prefix in markers_precise:
                if stripped.startswith(prefix):
                    value = stripped[len(prefix):].strip()
                    if value:
                        terms = [t.strip() for t in re.split(r"[,，、;；]", value) if t.strip()]
                        expanded_terms.extend(terms)
                    break

        # Must have at least an optimized query or some expanded terms
        if optimized_query or expanded_terms:
            return optimized_query or "", expanded_terms

        return None

    # ------------------------------------------------------------------
    # Matching logic
    # ------------------------------------------------------------------

    def _match_search_skill(self, query: str) -> SearchSkill | None:
        """Match the best search Skill based on intent signals.

        Checks if any intent_signal appears as a substring in the query
        (case-insensitive). If multiple skills match, the one with the most
        matching signals wins.

        Args:
            query: The user's search query text.

        Returns:
            The best matching SearchSkill, or None if no match.
        """
        if not self._skills:
            return None

        query_lower = query.lower()

        best_skill: SearchSkill | None = None
        best_match_count = 0

        for skill in self._skills:
            match_count = 0
            for signal in skill.intent_signals:
                if signal.lower() in query_lower:
                    match_count += 1

            if match_count > best_match_count:
                best_match_count = match_count
                best_skill = skill

        return best_skill if best_match_count > 0 else None

    # ------------------------------------------------------------------
    # Fallback strategy
    # ------------------------------------------------------------------

    def _fallback_strategy(self, query: str, language: str) -> SearchStrategyResult:
        """Fall back to the existing _infer_sources deterministic logic.

        Uses the same source inference logic as expert_search.py to determine
        relevant sources based on query keywords.

        Args:
            query: The user's search query text.
            language: Language code for the query.

        Returns:
            SearchStrategyResult with strategy_name="default" and inferred sources.
        """
        source_domains = _infer_sources(query)

        return SearchStrategyResult(
            strategy_name="default",
            original_query=query,
            optimized_query=None,
            expanded_terms=[],
            source_selection=source_domains,
            weight_adjustments={},
            optimization_source="deterministic",
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_skills(self) -> None:
        """Scan skills_dir for SKILL.md files with type: search_strategy."""
        if not self._skills_dir.is_dir():
            return

        for skill_path in self._skills_dir.rglob("SKILL.md"):
            try:
                skill_def = self._parse_skill_file(skill_path)
                if skill_def is not None:
                    self._skills.append(skill_def)
            except Exception:
                # Skip malformed Skill files gracefully
                continue

    def _parse_skill_file(self, path: Path) -> SearchSkill | None:
        """Parse a SKILL.md file and return a SearchSkill if applicable."""
        content = path.read_text(encoding="utf-8")

        # Extract YAML frontmatter
        frontmatter = _extract_yaml_frontmatter(content)
        if frontmatter is None:
            return None

        # Only load search_strategy type Skills
        skill_type = frontmatter.get("type", "")
        if skill_type != "search_strategy":
            return None

        metadata = frontmatter.get("metadata", {})
        skill_id = frontmatter.get("name", path.parent.name)
        skill_name = metadata.get("label_zh", skill_id)

        # Extract search strategy fields
        intent_signals = metadata.get("intent_signals", [])
        source_rules = metadata.get("source_rules", {})
        score_weights = metadata.get("score_weights", {})
        post_processing = metadata.get("post_processing", [])

        # Validate required fields
        if not isinstance(intent_signals, list) or not intent_signals:
            return None

        return SearchSkill(
            id=skill_id,
            name=skill_name,
            intent_signals=intent_signals if isinstance(intent_signals, list) else [],
            source_rules=source_rules if isinstance(source_rules, dict) else {},
            score_weights=score_weights if isinstance(score_weights, dict) else {},
            post_processing=post_processing if isinstance(post_processing, list) else [],
            skill_path=path,
        )

    def _resolve_sources(self, source_rules: dict[str, Any]) -> list[str]:
        """Resolve source domains from a skill's source_rules configuration.

        The source_rules dict may contain:
        - preferred_categories: list of source categories to include
        - min_trust_score: minimum trust score filter
        - max_sources: maximum number of sources to return
        - explicit_domains: directly specified domain list

        Args:
            source_rules: The skill's source selection rules.

        Returns:
            List of source domain strings.
        """
        # If explicit domains are specified, use them directly
        explicit = source_rules.get("explicit_domains", [])
        if explicit:
            return list(explicit)

        # Otherwise, filter PRESET_SOURCES by category and trust score
        preferred_categories = source_rules.get("preferred_categories", [])
        min_trust_score = source_rules.get("min_trust_score", 0.0)
        max_sources = source_rules.get("max_sources", 10)

        from .expert_search import PRESET_SOURCES

        matched_domains: list[str] = []
        for src in PRESET_SOURCES:
            if preferred_categories and src["category"] not in preferred_categories:
                continue
            if src["trust_score"] < min_trust_score:
                continue
            matched_domains.append(src["domain"])

        # If no categories matched, include all sources above trust threshold
        if not matched_domains and not preferred_categories:
            matched_domains = [
                src["domain"]
                for src in PRESET_SOURCES
                if src["trust_score"] >= min_trust_score
            ]

        return matched_domains[:max_sources]


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _extract_yaml_frontmatter(content: str) -> dict[str, Any] | None:
    """Extract and parse YAML frontmatter from a markdown file."""
    if not content.startswith("---"):
        return None

    # Find the closing ---
    end_idx = content.find("---", 3)
    if end_idx == -1:
        return None

    yaml_text = content[3:end_idx].strip()
    if not yaml_text:
        return None

    try:
        parsed = yaml.safe_load(yaml_text)
        if isinstance(parsed, dict):
            return parsed
    except yaml.YAMLError:
        return None

    return None


def _infer_sources(query: str) -> list[str]:
    """Infer relevant source domains from query keywords.

    This replicates the logic from expert_search._infer_sources to maintain
    consistency when no Search Skill matches.
    """
    from .expert_search import PRESET_SOURCES

    lower = query.lower()
    triggers = {
        "ai_tech": ["ai", "model", "llm", "neural", "transformer", "gpt", "深度学习"],
        "finance": ["stock", "market", "invest", "earnings", "financial", "股票"],
        "crypto": ["crypto", "bitcoin", "ethereum", "defi", "blockchain", "加密"],
        "business": ["strategy", "startup", "venture", "management", "创业"],
        "social_trends": ["trending", "viral", "opinion", "热门"],
    }
    cats = {
        c for c, kws in triggers.items() if any(k in lower for k in kws)
    } or {"general", "ai_tech"}

    return [s["domain"] for s in PRESET_SOURCES if s["category"] in cats]
