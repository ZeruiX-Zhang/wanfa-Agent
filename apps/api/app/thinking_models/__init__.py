"""Thinking Models — pluggable reasoning framework registry.

Architecture:
- Code Core: router.py, validators.py, engines/ (deterministic logic)
- Skill Brain: ../thinking_skills/{model-name}/SKILL.md (reasoning instructions)
- Visual Templates: ../thinking_skills/{model-name}/templates/*.html (interactive output)

The registry auto-scans the thinking_skills directory on startup, parses
SKILL.md frontmatter for routing metadata, and loads full body on activation.
This implements the Agent Skills progressive disclosure pattern.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

_SKILLS_DIR: Path | None = None


def _default_skills_dir() -> Path:
    """Return the thinking_skills directory path."""
    return Path(__file__).parent.parent.parent / "thinking_skills"


@dataclass
class ThinkingModelMeta:
    """Lightweight metadata loaded at startup (~100 tokens per model)."""
    id: str
    category: str
    label_zh: str
    label_en: str
    description: str
    intent_signals: list[str]
    applicable_when: list[str]
    not_applicable_when: list[str]
    output_schema: dict[str, Any]
    quality_checks: list[str]
    code_validators: list[dict[str, Any]]
    visual_template: str | None
    skill_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category,
            "label_zh": self.label_zh,
            "label_en": self.label_en,
            "description": self.description,
            "intent_signals": self.intent_signals,
            "applicable_when": self.applicable_when,
            "not_applicable_when": self.not_applicable_when,
            "output_schema": self.output_schema,
            "quality_checks": self.quality_checks,
            "visual_template": self.visual_template,
            "has_references": (self.skill_path / "references").is_dir(),
            "has_templates": (self.skill_path / "templates").is_dir(),
        }


@dataclass
class ThinkingModelFull:
    """Full model loaded on activation (body + references)."""
    meta: ThinkingModelMeta
    body: str  # The markdown body (structured prompt)
    references: dict[str, str]  # filename -> content

    def to_dict(self) -> dict[str, Any]:
        result = self.meta.to_dict()
        result["body"] = self.body
        result["references"] = list(self.references.keys())
        return result


# ---------------------------------------------------------------------------
# YAML frontmatter parser (minimal, no external deps)
# ---------------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _parse_yaml_lite(text: str) -> dict[str, Any]:
    """Minimal YAML parser for SKILL.md frontmatter.

    Handles: scalars, lists, one-level nested dicts, and lists inside nested dicts.
    This is NOT a full YAML parser — it handles exactly the structure we use.
    """
    import json
    result: dict[str, Any] = {}

    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())

        if not stripped or stripped.startswith("#"):
            i += 1
            continue

        # Top-level key (indent == 0)
        if indent == 0 and ":" in stripped and not stripped.startswith("-"):
            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip()

            if value:
                # Inline value
                result[key] = _parse_scalar(value)
            else:
                # Block value — collect everything indented below
                block_lines: list[str] = []
                i += 1
                while i < len(lines):
                    next_line = lines[i]
                    next_indent = len(next_line) - len(next_line.lstrip())
                    next_stripped = next_line.strip()
                    if not next_stripped:
                        i += 1
                        continue
                    if next_indent == 0 and next_stripped and ":" in next_stripped:
                        break  # Next top-level key
                    block_lines.append(next_line)
                    i += 1
                result[key] = _parse_block(block_lines)
                continue
        i += 1

    return result


def _parse_scalar(value: str) -> Any:
    """Parse a YAML scalar value."""
    import json
    if value.startswith("{") or value.startswith("["):
        try:
            return json.loads(value)
        except Exception:
            pass
    if value.lower() in ("true", "false"):
        return value.lower() == "true"
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    return value


def _parse_block(lines: list[str]) -> Any:
    """Parse an indented block as either a list or a dict."""
    if not lines:
        return []

    # Determine if it's a list or dict by looking at first non-empty line
    first = lines[0].strip()
    if first.startswith("- "):
        # It's a list
        items: list[Any] = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("- "):
                items.append(_parse_scalar(stripped[2:].strip()))
        return items
    elif ":" in first:
        # It's a dict (possibly with nested lists)
        result: dict[str, Any] = {}
        current_key: str | None = None
        current_list: list[str] | None = None
        base_indent = len(lines[0]) - len(lines[0].lstrip())

        for line in lines:
            stripped = line.strip()
            indent = len(line) - len(line.lstrip())

            if not stripped:
                continue

            if indent == base_indent and ":" in stripped and not stripped.startswith("-"):
                # Flush previous list
                if current_key and current_list is not None:
                    result[current_key] = current_list

                key, _, val = stripped.partition(":")
                key = key.strip()
                val = val.strip()

                if val:
                    result[key] = _parse_scalar(val)
                    current_key = None
                    current_list = None
                else:
                    current_key = key
                    current_list = []
            elif stripped.startswith("- ") and current_key is not None:
                if current_list is None:
                    current_list = []
                current_list.append(_parse_scalar(stripped[2:].strip()))

        if current_key and current_list is not None:
            result[current_key] = current_list

        return result

    return lines[0].strip()


def _parse_skill_md(path: Path) -> tuple[dict[str, Any], str]:
    """Parse a SKILL.md file into (frontmatter_dict, body_markdown)."""
    content = path.read_text(encoding="utf-8")
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return {}, content

    frontmatter_text = match.group(1)
    body = content[match.end():]
    frontmatter = _parse_yaml_lite(frontmatter_text)

    # Handle nested metadata
    if "metadata" not in frontmatter:
        frontmatter["metadata"] = {}

    return frontmatter, body.strip()


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, ThinkingModelMeta] = {}


def _load_registry(skills_dir: Path | None = None) -> dict[str, ThinkingModelMeta]:
    """Scan thinking_skills directory and build the registry."""
    global _REGISTRY, _SKILLS_DIR
    _SKILLS_DIR = skills_dir or _default_skills_dir()

    if not _SKILLS_DIR.is_dir():
        return {}

    registry: dict[str, ThinkingModelMeta] = {}

    for skill_dir in sorted(_SKILLS_DIR.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue

        try:
            fm, _ = _parse_skill_md(skill_md)
        except Exception:
            continue

        model_id = fm.get("name", skill_dir.name)
        metadata = fm.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}

        # Extract labels from description or metadata
        description = fm.get("description", "")
        label_zh = metadata.get("label_zh", model_id.replace("-", " ").title())
        label_en = metadata.get("label_en", model_id.replace("-", " ").title())

        # Extract list fields (may be in metadata or at top level)
        intent_signals = metadata.get("intent_signals", [])
        if not isinstance(intent_signals, list):
            intent_signals = []
        applicable_when = metadata.get("applicable_when", [])
        if not isinstance(applicable_when, list):
            applicable_when = []
        not_applicable_when = metadata.get("not_applicable_when", [])
        if not isinstance(not_applicable_when, list):
            not_applicable_when = []
        quality_checks = metadata.get("quality_checks", [])
        if not isinstance(quality_checks, list):
            quality_checks = []
        code_validators = metadata.get("code_validators", [])
        if not isinstance(code_validators, list):
            code_validators = []
        output_schema = metadata.get("output_schema", {})
        if not isinstance(output_schema, dict):
            output_schema = {}

        meta = ThinkingModelMeta(
            id=model_id,
            category=metadata.get("category", "general") if isinstance(metadata.get("category"), str) else "general",
            label_zh=label_zh if isinstance(label_zh, str) else model_id.replace("-", " ").title(),
            label_en=label_en if isinstance(label_en, str) else model_id.replace("-", " ").title(),
            description=description if isinstance(description, str) else "",
            intent_signals=intent_signals,
            applicable_when=applicable_when,
            not_applicable_when=not_applicable_when,
            output_schema=output_schema,
            quality_checks=quality_checks,
            code_validators=code_validators,
            visual_template=metadata.get("visual_template") if isinstance(metadata.get("visual_template"), str) else None,
            skill_path=skill_dir,
        )
        registry[model_id] = meta

    _REGISTRY = registry
    return registry


def get_registry() -> dict[str, ThinkingModelMeta]:
    """Get the thinking model registry (lazy-loads on first call)."""
    if not _REGISTRY:
        _load_registry()
    return _REGISTRY


def get_model_meta(model_id: str) -> ThinkingModelMeta | None:
    """Get metadata for a specific model."""
    return get_registry().get(model_id)


def get_model_full(model_id: str) -> ThinkingModelFull | None:
    """Load full model content (body + references) on activation."""
    meta = get_model_meta(model_id)
    if meta is None:
        return None

    skill_md = meta.skill_path / "SKILL.md"
    _, body = _parse_skill_md(skill_md)

    references: dict[str, str] = {}
    refs_dir = meta.skill_path / "references"
    if refs_dir.is_dir():
        for ref_file in refs_dir.iterdir():
            if ref_file.is_file() and ref_file.suffix in (".md", ".txt", ".json"):
                try:
                    references[ref_file.name] = ref_file.read_text(encoding="utf-8")
                except Exception:
                    pass

    return ThinkingModelFull(meta=meta, body=body, references=references)


def get_visual_template(model_id: str) -> str | None:
    """Load the HTML visual template for a model."""
    meta = get_model_meta(model_id)
    if meta is None or not meta.visual_template:
        return None

    template_path = meta.skill_path / meta.visual_template
    if not template_path.exists():
        return None

    try:
        return template_path.read_text(encoding="utf-8")
    except Exception:
        return None


def list_models() -> list[ThinkingModelMeta]:
    """List all registered thinking models."""
    return list(get_registry().values())


def route_model(question: str, language: str = "zh-CN") -> ThinkingModelMeta | None:
    """Route a question to the best matching thinking model.

    Uses intent_signals for deterministic matching.
    Returns None if no model matches (caller should use default).
    """
    registry = get_registry()
    if not registry:
        return None

    question_lower = question.lower()

    # Score each model by signal matches
    best_model: ThinkingModelMeta | None = None
    best_score = 0

    for model in registry.values():
        score = 0
        for signal in model.intent_signals:
            if signal.lower() in question_lower:
                score += 1
        if score > best_score:
            best_score = score
            best_model = model

    return best_model if best_score > 0 else None


def reload_registry(skills_dir: Path | None = None) -> int:
    """Force reload the registry (e.g. after adding a new skill)."""
    registry = _load_registry(skills_dir)
    return len(registry)
