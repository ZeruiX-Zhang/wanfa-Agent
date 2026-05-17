"""Unit tests for the consecutive-fail policy (Task 4.12, R9.3, R9.4)."""

from __future__ import annotations

from apps.api.app.skill_chain import consecutive_fail_policy, count_trailing_fails


def test_count_trailing_fails_resets_on_non_fail() -> None:
    assert count_trailing_fails([]) == 0
    assert count_trailing_fails(["fail", "fail", "fail"]) == 3
    assert count_trailing_fails(["fail", "success", "fail", "fail"]) == 2
    assert count_trailing_fails(["fail", "fail", "partial"]) == 0


def test_three_fails_trigger_chain_switch() -> None:
    """Three trailing fails under the default policy switch the chain."""

    history = ["partial", "fail", "fail", "fail"]
    trailing = count_trailing_fails(history)
    assert trailing == 3

    action = consecutive_fail_policy(trailing_fails=trailing, threshold=3)
    assert action == "chain_switch"

    # Below the threshold no action fires.
    assert consecutive_fail_policy(trailing_fails=2, threshold=3) is None


def test_three_fails_with_policy_human_review() -> None:
    """With the human-review policy, three fails escalate to a human."""

    trailing = count_trailing_fails(["fail", "fail", "fail"])
    action = consecutive_fail_policy(
        trailing_fails=trailing, threshold=3, policy="human_review"
    )
    assert action == "human_review_required"
