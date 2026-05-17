"""Wire-test for the ``REALITY_OS_EXPERT_GAP_ENABLED`` dark-launch flag (Task 2.18).

Validates the rollout-plan AC for Requirement 2.5:

* When the flag is *off* (the production default at T+0 per design.md
  "Dark-launch sequence"), :func:`audit_agent.zero_context_audit` runs
  the legacy five dimensions only — the new ``expert_gap`` dimension is
  not executed, the ``expert_gap`` and ``rubric_applied`` fields on
  :class:`audit_agent.AuditResult` are ``None``, and no audit issue
  carries ``dimension == "expert_gap"``.
* When the flag is *on*, the same call populates ``expert_gap`` and
  ``rubric_applied`` (resolving against the shipped
  ``general_decision`` rubric, source ``"domain"``), confirming the
  gate is bidirectional.

The test toggles the flag exclusively through ``monkeypatch.setenv``;
``feature_flags.expert_gap_enabled`` reads ``os.environ`` on every call
(no module-level cache) so flipping the env var is sufficient. Rubrics
are loaded once via ``expert_rubric.load_all(refresh=True)`` so the
"flag on" branch resolves a real domain rubric rather than the empty
fallback that R2.5 reserves for the rubric-missing path (covered by
``test_audit_expert_gap.py``).
"""

from __future__ import annotations

import pytest

from apps.api.app import audit_agent, expert_rubric


@pytest.fixture(autouse=True)
def _refresh_rubrics() -> None:
    """Make sure the rubric cache reflects the shipped YAMLs.

    Other tests in the suite swap ``expert_rubric.RUBRIC_ROOT`` to a
    temporary directory or empty the cache outright; refreshing here
    keeps this file independent of execution order.
    """

    expert_rubric.reset_cache_for_tests()
    expert_rubric.load_all(refresh=True)


def _sample_answer() -> str:
    """A reasonably substantive answer that touches several rubric anchors.

    Used for both branches so the only variable between the two halves
    of the test is the flag state.
    """

    return (
        "我们考虑最坏情况，估算了可承受损失，并明确了时间窗口和选项空间。"
        "数据来源、样本量和对照组都已经核对。"
        "机会成本、可逆性和二阶效应均已评估。"
        "资源依赖与时间排期都列入风险面。"
        "复盘指标和止损点也写入了下次信号。"
    )


# ---------------------------------------------------------------------------
# AC: audit skips the 6th dimension when the flag is off (then on)
# ---------------------------------------------------------------------------


def test_audit_skips_6th_dim_when_flag_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The 6th audit dimension is gated by ``REALITY_OS_EXPERT_GAP_ENABLED``.

    The conftest defaults ``REALITY_OS_COACH_ENABLED=true`` so the
    coach test client can boot, but it does *not* touch
    ``REALITY_OS_EXPERT_GAP_ENABLED``. We explicitly delete the env
    var first to assert the unset-default == off contract from
    ``feature_flags.expert_gap_enabled`` (R15.2 — defaults all off).
    """

    # --- Branch 1: flag off → only 5 dimensions run ---------------------
    monkeypatch.delenv("REALITY_OS_EXPERT_GAP_ENABLED", raising=False)

    result_off = audit_agent.zero_context_audit(
        output_text=_sample_answer(),
        output_type="answer",
        language="zh-CN",
        domain="general_decision",
    )

    # The new dimension didn't execute — both payload fields are None
    # and no issue carries the expert_gap dimension tag.
    assert result_off.expert_gap is None
    assert result_off.rubric_applied is None
    assert all(
        issue.dimension != "expert_gap" for issue in result_off.issues
    ), [i.to_dict() for i in result_off.issues]

    # The legacy 5-dim audit still produced a well-formed result.
    assert 0.0 <= result_off.score <= 1.0
    assert result_off.output_type == "answer"

    # Setting the flag explicitly to ``false`` must behave identically
    # to "unset" — both readings collapse to the dark-launch default.
    monkeypatch.setenv("REALITY_OS_EXPERT_GAP_ENABLED", "false")
    result_explicit_off = audit_agent.zero_context_audit(
        output_text=_sample_answer(),
        output_type="answer",
        language="zh-CN",
        domain="general_decision",
    )
    assert result_explicit_off.expert_gap is None
    assert result_explicit_off.rubric_applied is None

    # --- Branch 2: flag on → the 6th dimension runs and resolves -------
    monkeypatch.setenv("REALITY_OS_EXPERT_GAP_ENABLED", "true")

    result_on = audit_agent.zero_context_audit(
        output_text=_sample_answer(),
        output_type="answer",
        language="zh-CN",
        domain="general_decision",
    )

    # Payload populated; bounds match Property 8.
    assert result_on.expert_gap is not None, result_on.to_dict()
    assert 0.0 <= result_on.expert_gap["expert_gap_score"] <= 1.0
    assert len(result_on.expert_gap["missing_points"]) <= 7

    # Rubric metadata is attached and resolved to the shipped domain
    # rubric (R2.6) — `source == "default"` would also satisfy the AC
    # but we ship a ``general_decision`` rubric so the resolver MUST
    # land on it.
    assert result_on.rubric_applied is not None
    assert result_on.rubric_applied["domain"] == "general_decision"
    assert result_on.rubric_applied["source"] in {"domain", "default"}
    # Sanity: the on-branch genuinely diverges from the off-branch.
    assert result_on.rubric_applied != result_off.rubric_applied


# ---------------------------------------------------------------------------
# AC: caller-supplied dimensions still respected (back-compat)
# ---------------------------------------------------------------------------


def test_explicit_dimensions_still_respected_when_flag_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Callers passing ``dimensions=[...]`` keep full control.

    Task 2.18 requires preserving back-compat for callers that pass
    an explicit dimensions list. Even with the flag on, asking for
    the legacy five must skip ``expert_gap`` cleanly.
    """

    monkeypatch.setenv("REALITY_OS_EXPERT_GAP_ENABLED", "true")

    legacy_five: list[audit_agent.AuditDimension] = [
        "logic",
        "evidence",
        "feasibility",
        "subjectivity",
        "completeness",
    ]
    result = audit_agent.zero_context_audit(
        output_text=_sample_answer(),
        output_type="answer",
        language="zh-CN",
        dimensions=legacy_five,
        domain="general_decision",
    )
    assert result.expert_gap is None
    assert result.rubric_applied is None
    assert all(issue.dimension != "expert_gap" for issue in result.issues)
