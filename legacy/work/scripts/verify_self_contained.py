from __future__ import annotations

import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]

TEXT_SUFFIXES = {
    ".py",
    ".json",
    ".yml",
    ".yaml",
    ".toml",
    ".ini",
    ".env",
}

SKIP_DIRS = {
    ".git",
    ".venv",
    ".pytest_cache",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
}


def _is_text_candidate(path: Path) -> bool:
    return path.suffix.lower() in TEXT_SUFFIXES or path.name.endswith(".example")


def _relative(path: Path) -> str:
    return str(path.relative_to(ROOT_DIR)).replace("\\", "/")


def main() -> None:
    forbidden_patterns = [
        str(ROOT_DIR).lower(),
        r"d:\userdata\desktop\rag demo",
        r"d:\userdata\desktop\multi-scenario-workflow-agent",
        r"d:\userdata\desktop\data-analyst-agent",
    ]

    violations: list[str] = []
    for path in ROOT_DIR.rglob("*"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if not path.is_file():
            continue
        rel = _relative(path)
        if rel.startswith("legacy/") or rel == "scripts/verify_self_contained.py":
            continue
        if not _is_text_candidate(path):
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                content = path.read_text(encoding="utf-8-sig")
            except UnicodeDecodeError:
                continue
        lowered = content.lower()
        for pattern in forbidden_patterns:
            if pattern in lowered:
                violations.append(f"{rel}: found forbidden reference `{pattern}`")

    if violations:
        print("self-contained verification failed")
        for item in violations:
            print(item)
        raise SystemExit(1)

    print("self-contained verification passed")


if __name__ == "__main__":
    sys.exit(main())
