from __future__ import annotations

from pathlib import Path

from rag_core.core.config import AGENT_CORE_ROOT


class PathGuardError(ValueError):
    pass


def ensure_within_allowed_path(path: str | Path, allowed_roots: list[Path] | None = None) -> Path:
    roots = [root.resolve() for root in (allowed_roots or [AGENT_CORE_ROOT])]
    resolved = Path(path).resolve()
    for root in roots:
        if resolved == root or root in resolved.parents:
            return resolved
    raise PathGuardError(f"path is outside allowed roots: {resolved}")


def safe_child_path(base: Path, filename: str) -> Path:
    raw = Path(filename)
    if raw.name != filename or ".." in raw.parts or "/" in filename or "\\" in filename:
        raise PathGuardError("filename must not contain path traversal")
    return ensure_within_allowed_path(base / raw.name, [base])


