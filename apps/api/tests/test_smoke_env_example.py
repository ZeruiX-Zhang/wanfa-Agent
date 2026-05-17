"""Smoke test for ``.env.example`` (Task 1.5)."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
ENV_EXAMPLE = REPO_ROOT / ".env.example"


REQUIRED_KEYS = (
    "REALITY_OS_VECTOR_STORE",
    "REALITY_OS_EMBED_MODE",
    "REALITY_OS_COACH_ENABLED",
    "REALITY_OS_HYBRID_RETRIEVAL",
    "REALITY_OS_EXPERT_GAP_ENABLED",
    "REALITY_OS_COACH_AUTOSWITCH",
    "REALITY_OS_CALIBRATION_THRESHOLD",
    "REALITY_OS_COACH_IDLE_DAYS",
)


def test_env_example_contains_new_keys() -> None:
    assert ENV_EXAMPLE.exists(), f"missing {ENV_EXAMPLE}"
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    for key in REQUIRED_KEYS:
        assert f"{key}=" in text, f"{key} missing from .env.example"
