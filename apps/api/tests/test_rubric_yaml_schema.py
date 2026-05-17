"""Schema tests for shipped expert_rubrics YAML files (Task 2.6 / R2.1, R2.7)."""

from __future__ import annotations

import pytest

from apps.api.app import expert_rubric


@pytest.fixture(autouse=True)
def fresh_cache() -> None:
    expert_rubric.reset_cache_for_tests()


def test_all_shipped_rubrics_validate() -> None:
    results = expert_rubric.load_all(refresh=True)
    refused = [r for r in results if r.rubric is None]
    assert not refused, f"refused rubrics: {[r.refused_reason for r in refused]}"

    domains = {r.rubric.domain for r in results if r.rubric is not None}
    # ``default`` is mandatory (R2.7 fallback).
    assert "default" in domains
    # We ship at least three additional domains per design.
    assert {"general_decision", "technology", "finance"} <= domains


def test_default_rubric_resolves_for_unknown_domain() -> None:
    expert_rubric.load_all(refresh=True)
    rubric, source = expert_rubric.resolve_rubric("nonexistent_domain_xyz")
    assert source == "default"
    assert rubric is not None
    assert rubric.domain == "default"
