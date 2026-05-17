"""Smoke test — ``legacy/`` is read-only and not coupled to feature code.

Task 6.7 (R16.1, R16.2): no expert-coaching-loop module may import from
``legacy/``, and ``legacy/`` must not reach into the new feature modules.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
APP_DIR = REPO_ROOT / "apps" / "api" / "app"

# Modules introduced or extended by the expert-coaching-loop feature.
_FEATURE_MODULES: tuple[str, ...] = (
    "coaching_session.py",
    "coaching_schema.py",
    "skill_chain.py",
    "expert_rubric.py",
    "mastery.py",
    "calibration.py",
    "evidence_gathering.py",
    "feature_flags.py",
    "audit_events.py",
    "adapter_metadata.py",
    "mastery_backfill.py",
    "metacognition.py",
    "hybrid_retrieval.py",
)

_LEGACY_IMPORT = re.compile(r"(?:^|\n)\s*(?:import\s+legacy|from\s+\.{0,3}legacy)")


def test_no_new_module_imports_from_legacy() -> None:
    """None of the feature modules import anything from ``legacy/``."""

    for name in _FEATURE_MODULES:
        path = APP_DIR / name
        assert path.exists(), f"feature module missing: {name}"
        text = path.read_text(encoding="utf-8")
        assert not _LEGACY_IMPORT.search(text), f"{name} imports from legacy/"


def test_no_legacy_files_modified_by_feature_paths() -> None:
    """``legacy/`` does not import the new feature modules either.

    The feature is strictly additive (R16.1); coupling in either
    direction would make ``legacy/`` impossible to retire independently.
    """

    legacy_dir = REPO_ROOT / "legacy"
    if not legacy_dir.exists():
        return
    feature_names = {name[:-3] for name in _FEATURE_MODULES}
    for path in legacy_dir.rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for module in feature_names:
            assert f"import {module}" not in text, (
                f"legacy file {path.name} imports feature module {module}"
            )
