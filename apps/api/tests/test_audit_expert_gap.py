"""Tests for the ``expert_gap`` audit dimension wiring (Task 2.8)."""

from __future__ import annotations

import pytest

from apps.api.app import audit_agent, expert_rubric


@pytest.fixture(autouse=True)
def reload_rubrics(monkeypatch: pytest.MonkeyPatch) -> None:
    expert_rubric.reset_cache_for_tests()
    expert_rubric.load_all(refresh=True)
    monkeypatch.setenv("REALITY_OS_EXPERT_GAP_ENABLED", "true")


def test_audit_includes_expert_gap_dimension_when_flag_on() -> None:
    text = (
        "我们必须考虑最坏情况，估算可承受损失，"
        "并在做出选项空间之前明确时间窗口。"
        "依赖资源、二阶效应、机会成本均已经评估。"
        "复盘指标和止损点写入了下一次的下次信号。"
        "数据来源、样本量和对照组的细节也补全。"
    )
    result = audit_agent.zero_context_audit(
        output_text=text,
        output_type="answer",
        language="zh-CN",
        dimensions=audit_agent.ALL_DIMENSIONS,
        domain="general_decision",
    )
    assert result.expert_gap is not None
    assert 0.0 <= result.expert_gap["expert_gap_score"] <= 1.0
    assert result.rubric_applied == {
        "domain": "general_decision",
        "version": "1.0.0",
        "source": "domain",
    }


def test_falls_back_to_5_dims_when_rubric_missing(monkeypatch, tmp_path) -> None:
    """When the rubric directory is empty, no expert_gap dim runs (R2.5)."""

    # Point the loader at an empty directory and bypass the lazy reload
    # that would otherwise re-discover the shipped rubrics.
    monkeypatch.setattr(expert_rubric, "RUBRIC_ROOT", tmp_path)
    expert_rubric.reset_cache_for_tests()

    # Patch the audit_agent's reference so the helper sees no rubric.
    monkeypatch.setattr(
        audit_agent.expert_rubric_mod,
        "load_all",
        lambda *a, **kw: [],
    )
    monkeypatch.setattr(
        audit_agent.expert_rubric_mod,
        "resolve_rubric",
        lambda *a, **kw: (None, "missing"),
    )

    result = audit_agent.zero_context_audit(
        output_text="一个无关紧要的回答",
        output_type="answer",
        language="zh-CN",
        dimensions=audit_agent.ALL_DIMENSIONS,
        domain="general_decision",
    )
    assert result.expert_gap is None
    assert result.rubric_applied is None
    # The other 5 dimensions still ran; result is well-formed.
    assert 0.0 <= result.score <= 1.0
    # No issue with dimension == 'expert_gap' was raised.
    assert all(issue.dimension != "expert_gap" for issue in result.issues)


def test_flag_off_skips_expert_gap_even_when_rubric_loaded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REALITY_OS_EXPERT_GAP_ENABLED", "false")
    expert_rubric.load_all(refresh=True)
    result = audit_agent.zero_context_audit(
        output_text="random body",
        output_type="answer",
        language="zh-CN",
        dimensions=audit_agent.ALL_DIMENSIONS,
        domain="general_decision",
    )
    assert result.expert_gap is None
    assert result.rubric_applied is None
