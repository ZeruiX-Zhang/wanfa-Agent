"""Tests for the Skill Chain loader (Task 2.9)."""

from __future__ import annotations

import pytest

from apps.api.app import skill_chain


@pytest.fixture(autouse=True)
def fresh_cache() -> None:
    skill_chain.reset_cache_for_tests()
    skill_chain.load_all(refresh=True)


def test_general_decision_chain_present() -> None:
    chain = skill_chain.get_chain("general_decision")
    assert chain is not None
    assert chain.problem_type == "general"
    assert [s.skill_id for s in chain.steps] == [
        "problem-statement",
        "five-whys",
        "jtbd",
        "pre-mortem",
        "decision-matrix",
        "smart",
    ]


def test_loader_validates_skill_ids(tmp_path) -> None:
    bad_chain = tmp_path / "bad.yaml"
    bad_chain.write_text(
        """
id: broken_chain
problem_type: bogus
steps:
  - skill_id: nonexistent_skill
    entry_conditions: [always]
    exit_conditions: [always]
""",
        encoding="utf-8",
    )
    skill_chain.reset_cache_for_tests()
    chains = skill_chain.load_all(root=tmp_path, refresh=True)
    assert "broken_chain" not in chains
    refused = skill_chain.refused_chains()
    assert any("unknown_skill_ids" in reason for (_, reason) in refused)


def test_all_shipped_chains_have_no_unknown_skills() -> None:
    refused = skill_chain.refused_chains()
    assert refused == [], f"refused chains: {refused}"
