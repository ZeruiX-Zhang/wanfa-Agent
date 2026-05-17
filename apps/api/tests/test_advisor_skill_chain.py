"""Test for AdvisorResponse.skill_chain integration (Task 2.11)."""

from __future__ import annotations

import pytest

from apps.api.app import reality_advisor, skill_chain


@pytest.fixture(autouse=True)
def reset_chain_cache() -> None:
    skill_chain.reset_cache_for_tests()
    skill_chain.load_all(refresh=True)


def test_advise_returns_skill_chain_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """``RealityAdvisor.advise`` populates ``skill_chain`` when the registry has chains."""

    advisor = reality_advisor.RealityAdvisor()
    response = advisor.advise(
        tenant_id="tnt-skillchain",
        question="我应该如何选择下一个团队投资方向？",
        language="zh-CN",
    )
    assert response.skill_chain is not None
    assert {
        "chain_id",
        "step_idx",
        "step_skill_id",
        "entry_satisfied",
        "exit_satisfied",
    } <= response.skill_chain.keys()
    assert response.skill_chain["step_idx"] == 0


def test_advise_returns_none_when_chain_registry_empty(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setattr(skill_chain, "CHAIN_ROOT", tmp_path)
    skill_chain.reset_cache_for_tests()

    advisor = reality_advisor.RealityAdvisor()
    response = advisor.advise(
        tenant_id="tnt-empty",
        question="test question",
        language="zh-CN",
    )
    assert response.skill_chain is None
