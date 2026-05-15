"""Skill-driven knowledge validator for Reality OS.

This module implements structured validation of knowledge items using rules
defined in SKILL.md files. Each validation Skill specifies domain-specific
rules for checking fact consistency, timeliness, completeness, and source
credibility.

The validator scans a configurable directory for SKILL.md files with
``type: validation`` in their YAML frontmatter, and uses matched rules to
evaluate incoming knowledge items before ingestion.

Design principles:
- Deterministic: no model calls, pure rule-based validation
- Extensible: add new validation rules by dropping SKILL.md files
- Hot-reloadable: call ``reload_skills()`` to pick up changes without restart
- Graceful degradation: if no Skill matches, built-in defaults are used
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import yaml

from .knowledge_core import KnowledgeItem, SourceKind, tokenize, STOPWORDS


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ValidationDimension:
    """Result of a single validation dimension check."""

    name: str  # fact_consistency | timeliness | completeness | source_credibility
    passed: bool
    score: float  # 0.0-1.0
    severity: Literal["critical", "warning", "info", "pass"]
    details: str


@dataclass
class ValidationResult:
    """Aggregate result of all validation dimensions."""

    passed: bool
    dimensions: list[ValidationDimension]
    skill_used: str | None  # ID of the validation Skill used
    overall_severity: Literal["critical", "warning", "info", "pass"]
    warnings: list[str]
    blocking_issues: list[str]


# ---------------------------------------------------------------------------
# Internal Skill representation
# ---------------------------------------------------------------------------


@dataclass
class _ValidationSkillDef:
    """Parsed validation Skill definition from a SKILL.md file."""

    id: str
    name: str
    domains: list[str]
    rules: dict[str, Any]
    skill_path: Path


# ---------------------------------------------------------------------------
# Constants / defaults
# ---------------------------------------------------------------------------

_SEVERITY_ORDER: dict[str, int] = {
    "pass": 0,
    "info": 1,
    "warning": 2,
    "critical": 3,
}

_DEFAULT_MAX_AGE_DAYS = 90
_DEFAULT_MIN_TITLE_LENGTH = 5
_DEFAULT_MIN_BODY_LENGTH = 50

_TRUSTED_DOMAINS: list[str] = [
    "github.com",
    "stackoverflow.com",
    "arxiv.org",
    "wikipedia.org",
    "docs.python.org",
    "developer.mozilla.org",
    "microsoft.com",
    "google.com",
    "apple.com",
    "aws.amazon.com",
    "cloud.google.com",
    "learn.microsoft.com",
]

_HIGH_TRUST_SOURCE_KINDS: set[str] = {"direct_import", "memory_note"}


# ---------------------------------------------------------------------------
# SkillValidator
# ---------------------------------------------------------------------------


class SkillValidator:
    """Skill-driven knowledge validator.

    Loads validation SKILL.md files from a configurable directory and uses
    matched rules to evaluate knowledge items across four dimensions.
    """

    def __init__(self, skills_dir: Path | None = None) -> None:
        """Load validation Skill registry.

        Args:
            skills_dir: Directory to scan for SKILL.md files. Defaults to
                ``thinking_skills/`` relative to this module's parent (the api app).
        """
        if skills_dir is None:
            skills_dir = Path(__file__).resolve().parent.parent / "thinking_skills"
        self._skills_dir = skills_dir
        self._skills: list[_ValidationSkillDef] = []
        self._load_skills()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate(
        self,
        *,
        item_title: str,
        item_body: str,
        source_kind: SourceKind,
        tags: list[str],
        existing_items: list[KnowledgeItem] | None = None,
        freshness_date: str | None = None,
        source_url: str | None = None,
    ) -> ValidationResult:
        """Execute the full validation flow.

        Always returns exactly 4 dimensions: fact_consistency, timeliness,
        completeness, source_credibility.
        """
        skill_id = self._match_skill(tags, source_kind)
        skill_rules = self._get_skill_rules(skill_id)

        # Run all four dimension checks
        dim_fact = self._check_fact_consistency(
            item_body, existing_items or [], skill_rules
        )
        dim_time = self._check_timeliness(freshness_date, skill_rules)
        dim_complete = self._check_completeness(item_title, item_body, skill_rules)
        dim_source = self._check_source_credibility(
            source_kind, source_url, skill_rules
        )

        dimensions = [dim_fact, dim_time, dim_complete, dim_source]

        # Determine overall severity (highest among all dimensions)
        overall_severity = _highest_severity(dimensions)

        # Collect warnings and blocking issues
        warnings: list[str] = []
        blocking_issues: list[str] = []
        for dim in dimensions:
            if dim.severity == "warning":
                warnings.append(f"[{dim.name}] {dim.details}")
            elif dim.severity == "critical":
                blocking_issues.append(f"[{dim.name}] {dim.details}")

        passed = overall_severity in ("pass", "info")

        return ValidationResult(
            passed=passed,
            dimensions=dimensions,
            skill_used=skill_id,
            overall_severity=overall_severity,
            warnings=warnings,
            blocking_issues=blocking_issues,
        )

    def reload_skills(self) -> int:
        """Reload validation Skills from disk (hot update support).

        Returns:
            Number of validation Skills loaded.
        """
        self._skills.clear()
        self._load_skills()
        return len(self._skills)

    # ------------------------------------------------------------------
    # Skill matching
    # ------------------------------------------------------------------

    def _match_skill(self, tags: list[str], source_kind: str) -> str | None:
        """Match the best validation Skill based on domain tags.

        Returns the Skill ID if a match is found, None otherwise.
        """
        if not self._skills:
            return None

        tags_lower = {t.lower() for t in tags}

        best_skill: _ValidationSkillDef | None = None
        best_overlap = 0

        for skill in self._skills:
            skill_domains = {d.lower() for d in skill.domains}
            overlap = len(tags_lower & skill_domains)
            if overlap > best_overlap:
                best_overlap = overlap
                best_skill = skill

        if best_skill and best_overlap > 0:
            return best_skill.id

        return None

    # ------------------------------------------------------------------
    # Dimension checks
    # ------------------------------------------------------------------

    def _check_fact_consistency(
        self,
        body: str,
        existing_items: list[KnowledgeItem],
        skill_rules: dict[str, Any],
    ) -> ValidationDimension:
        """Check fact consistency against existing knowledge items.

        Uses token overlap to detect potential contradictions. If the new item
        shares significant vocabulary with an existing item but contains
        contradiction keywords, it flags a potential inconsistency.
        """
        if not existing_items:
            return ValidationDimension(
                name="fact_consistency",
                passed=True,
                score=1.0,
                severity="pass",
                details="No existing items to compare against.",
            )

        rules = skill_rules.get("fact_consistency", {})
        contradiction_keywords = rules.get("contradiction_keywords", [])

        body_tokens = set(tokenize(body)) - STOPWORDS
        if not body_tokens:
            return ValidationDimension(
                name="fact_consistency",
                passed=True,
                score=1.0,
                severity="pass",
                details="Body has no meaningful tokens to compare.",
            )

        # Check for contradictions with existing items
        max_overlap = 0.0
        contradictions_found: list[str] = []

        for item in existing_items:
            item_tokens = set(tokenize(item.body)) - STOPWORDS
            if not item_tokens:
                continue

            # Jaccard similarity
            intersection = body_tokens & item_tokens
            union = body_tokens | item_tokens
            overlap = len(intersection) / len(union) if union else 0.0
            max_overlap = max(max_overlap, overlap)

            # If high overlap, check for contradiction keywords
            if overlap > 0.3 and contradiction_keywords:
                body_lower = body.lower()
                item_body_lower = item.body.lower()
                for kw in contradiction_keywords:
                    kw_lower = kw.lower()
                    if kw_lower in body_lower and kw_lower in item_body_lower:
                        contradictions_found.append(
                            f"Potential contradiction with item '{item.title}' "
                            f"on keyword '{kw}'"
                        )

        if contradictions_found:
            return ValidationDimension(
                name="fact_consistency",
                passed=False,
                score=max(0.0, 1.0 - len(contradictions_found) * 0.3),
                severity="critical" if len(contradictions_found) >= 2 else "warning",
                details="; ".join(contradictions_found[:3]),
            )

        # High overlap without contradiction keywords is just informational
        if max_overlap > 0.7:
            return ValidationDimension(
                name="fact_consistency",
                passed=True,
                score=0.7,
                severity="info",
                details=f"High content overlap ({max_overlap:.0%}) with existing items.",
            )

        return ValidationDimension(
            name="fact_consistency",
            passed=True,
            score=1.0,
            severity="pass",
            details="No contradictions detected.",
        )

    def _check_timeliness(
        self,
        freshness_date: str | None,
        skill_rules: dict[str, Any],
    ) -> ValidationDimension:
        """Check if the knowledge item is still timely.

        Compares freshness_date against a configurable threshold (default 90 days).
        """
        if not freshness_date:
            return ValidationDimension(
                name="timeliness",
                passed=True,
                score=0.8,
                severity="info",
                details="No freshness date provided; cannot assess timeliness.",
            )

        rules = skill_rules.get("timeliness", {})
        max_age_days = rules.get("max_age_days", _DEFAULT_MAX_AGE_DAYS)

        try:
            # Parse ISO format date
            if "T" in freshness_date:
                parsed = datetime.fromisoformat(freshness_date.replace("Z", "+00:00"))
            else:
                parsed = datetime.fromisoformat(freshness_date).replace(
                    tzinfo=timezone.utc
                )
        except (ValueError, TypeError):
            return ValidationDimension(
                name="timeliness",
                passed=True,
                score=0.6,
                severity="info",
                details=f"Could not parse freshness_date: '{freshness_date}'.",
            )

        now = datetime.now(timezone.utc)
        age_days = (now - parsed).days

        if age_days < 0:
            # Future date — likely an error but not blocking
            return ValidationDimension(
                name="timeliness",
                passed=True,
                score=0.9,
                severity="info",
                details="Freshness date is in the future.",
            )

        if age_days <= max_age_days:
            # Within threshold
            freshness_score = max(0.5, 1.0 - (age_days / max_age_days) * 0.5)
            return ValidationDimension(
                name="timeliness",
                passed=True,
                score=round(freshness_score, 3),
                severity="pass",
                details=f"Content is {age_days} days old (threshold: {max_age_days}).",
            )

        # Exceeded threshold
        overage_ratio = age_days / max_age_days
        if overage_ratio > 3.0:
            return ValidationDimension(
                name="timeliness",
                passed=False,
                score=0.1,
                severity="critical",
                details=f"Content is {age_days} days old, far exceeding threshold of {max_age_days} days.",
            )

        return ValidationDimension(
            name="timeliness",
            passed=False,
            score=max(0.2, 1.0 - overage_ratio * 0.3),
            severity="warning",
            details=f"Content is {age_days} days old, exceeding threshold of {max_age_days} days.",
        )

    def _check_completeness(
        self,
        title: str,
        body: str,
        skill_rules: dict[str, Any],
    ) -> ValidationDimension:
        """Check that title and body meet minimum length and section requirements."""
        rules = skill_rules.get("completeness", {})
        min_title_length = rules.get("min_title_length", _DEFAULT_MIN_TITLE_LENGTH)
        min_body_length = rules.get("min_body_length", _DEFAULT_MIN_BODY_LENGTH)
        required_sections = rules.get("required_sections", [])

        issues: list[str] = []

        # Title length check
        title_stripped = title.strip()
        if len(title_stripped) < min_title_length:
            issues.append(
                f"Title too short ({len(title_stripped)} chars, min {min_title_length})"
            )

        # Body length check
        body_stripped = body.strip()
        if len(body_stripped) < min_body_length:
            issues.append(
                f"Body too short ({len(body_stripped)} chars, min {min_body_length})"
            )

        # Required sections check
        if required_sections:
            body_lower = body.lower()
            missing_sections: list[str] = []
            for section in required_sections:
                if section.lower() not in body_lower:
                    missing_sections.append(section)
            if missing_sections:
                issues.append(
                    f"Missing sections: {', '.join(missing_sections)}"
                )

        if not issues:
            return ValidationDimension(
                name="completeness",
                passed=True,
                score=1.0,
                severity="pass",
                details="All completeness checks passed.",
            )

        # Determine severity based on number and type of issues
        has_length_issue = any("too short" in i for i in issues)
        has_section_issue = any("Missing sections" in i for i in issues)

        if has_length_issue and len(body_stripped) < 10:
            severity: Literal["critical", "warning", "info", "pass"] = "critical"
        elif has_length_issue and has_section_issue:
            severity = "warning"
        elif has_length_issue:
            severity = "warning"
        else:
            severity = "info"

        score = max(0.0, 1.0 - len(issues) * 0.25)

        return ValidationDimension(
            name="completeness",
            passed=severity in ("pass", "info"),
            score=round(score, 3),
            severity=severity,
            details="; ".join(issues),
        )

    def _check_source_credibility(
        self,
        source_kind: str,
        source_url: str | None,
        skill_rules: dict[str, Any],
    ) -> ValidationDimension:
        """Evaluate source credibility based on source_kind and source_url.

        Internal sources (direct_import, memory_note) are trusted by default.
        External sources are evaluated against trusted domain lists.
        """
        # Internal sources are inherently trusted
        if source_kind in _HIGH_TRUST_SOURCE_KINDS:
            return ValidationDimension(
                name="source_credibility",
                passed=True,
                score=1.0,
                severity="pass",
                details=f"Source kind '{source_kind}' is internally trusted.",
            )

        rules = skill_rules.get("source_credibility", {})
        trusted_domains = rules.get("trusted_domains", _TRUSTED_DOMAINS)
        min_trust_score = rules.get("min_trust_score", 0.5)

        # No URL provided for external source
        if not source_url:
            return ValidationDimension(
                name="source_credibility",
                passed=False,
                score=0.3,
                severity="warning",
                details=f"No source URL provided for '{source_kind}' content.",
            )

        # Extract domain from URL
        domain = _extract_domain(source_url)
        if not domain:
            return ValidationDimension(
                name="source_credibility",
                passed=False,
                score=0.3,
                severity="warning",
                details=f"Could not extract domain from URL: '{source_url[:100]}'.",
            )

        # Check against trusted domains
        is_trusted = any(
            domain == td or domain.endswith("." + td)
            for td in trusted_domains
        )

        if is_trusted:
            return ValidationDimension(
                name="source_credibility",
                passed=True,
                score=0.9,
                severity="pass",
                details=f"Domain '{domain}' is in the trusted list.",
            )

        # Unknown domain — not blocking but flagged
        # Score based on source_kind risk level
        if source_kind == "expert_search":
            score = 0.5
            severity: Literal["critical", "warning", "info", "pass"] = "warning"
        elif source_kind == "browser_capture":
            score = 0.4
            severity = "warning"
        elif source_kind == "ai_answer_capture":
            score = 0.4
            severity = "warning"
        else:
            score = 0.5
            severity = "info"

        if score < min_trust_score:
            severity = "warning"

        return ValidationDimension(
            name="source_credibility",
            passed=severity in ("pass", "info"),
            score=round(score, 3),
            severity=severity,
            details=f"Domain '{domain}' is not in the trusted list for source kind '{source_kind}'.",
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_skills(self) -> None:
        """Scan skills_dir for SKILL.md files with type: validation."""
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

    def _parse_skill_file(self, path: Path) -> _ValidationSkillDef | None:
        """Parse a SKILL.md file and return a validation Skill def if applicable."""
        content = path.read_text(encoding="utf-8")

        # Extract YAML frontmatter
        frontmatter = _extract_yaml_frontmatter(content)
        if frontmatter is None:
            return None

        # Only load validation type Skills
        skill_type = frontmatter.get("type", "")
        if skill_type != "validation":
            return None

        metadata = frontmatter.get("metadata", {})
        skill_id = frontmatter.get("name", path.parent.name)
        domains = metadata.get("domains", [])
        rules = metadata.get("rules", {})

        return _ValidationSkillDef(
            id=skill_id,
            name=metadata.get("label_zh", skill_id),
            domains=domains if isinstance(domains, list) else [],
            rules=rules if isinstance(rules, dict) else {},
            skill_path=path,
        )

    def _get_skill_rules(self, skill_id: str | None) -> dict[str, Any]:
        """Get the rules dict for a matched Skill, or empty dict for defaults."""
        if skill_id is None:
            return {}
        for skill in self._skills:
            if skill.id == skill_id:
                return skill.rules
        return {}


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


def _extract_domain(url: str) -> str | None:
    """Extract the domain from a URL string."""
    url = url.strip()
    if not url:
        return None

    # Handle URLs without scheme
    if not url.startswith(("http://", "https://", "//")):
        url = "https://" + url

    # Simple regex-based domain extraction
    match = re.match(r"(?:https?://|//)([^/:?#]+)", url)
    if match:
        domain = match.group(1).lower()
        # Strip www. prefix
        if domain.startswith("www."):
            domain = domain[4:]
        return domain

    return None


def _highest_severity(
    dimensions: list[ValidationDimension],
) -> Literal["critical", "warning", "info", "pass"]:
    """Return the highest severity among all dimensions."""
    max_level = 0
    for dim in dimensions:
        level = _SEVERITY_ORDER.get(dim.severity, 0)
        if level > max_level:
            max_level = level

    for sev, level in _SEVERITY_ORDER.items():
        if level == max_level:
            return sev  # type: ignore[return-value]

    return "pass"
