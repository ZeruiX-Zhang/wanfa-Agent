"""Smoke test — feature-flag dark-launch matrix (Task 6.6, R15.2).

With every expert-coaching-loop flag off, the legacy ``/api/v2`` routes
must stay intact; flags can then be flipped per milestone independently.
"""

from __future__ import annotations

from apps.api.app import feature_flags


def test_all_flags_off_legacy_routes_intact(monkeypatch) -> None:
    """Default (flags unset) keeps every new behaviour switched off."""

    for env in (
        "REALITY_OS_COACH_ENABLED",
        "REALITY_OS_EXPERT_GAP_ENABLED",
        "REALITY_OS_HYBRID_RETRIEVAL",
        "REALITY_OS_COACH_AUTOSWITCH",
    ):
        monkeypatch.delenv(env, raising=False)
    monkeypatch.delenv("REALITY_OS_EMBED_MODE", raising=False)

    assert feature_flags.coach_enabled() is False
    assert feature_flags.expert_gap_enabled() is False
    assert feature_flags.hybrid_retrieval_enabled() is False
    assert feature_flags.coach_autoswitch() is False
    assert feature_flags.embed_mode() == "disabled"


def test_flags_can_be_flipped_per_milestone(monkeypatch) -> None:
    """Each flag flips independently so milestones dark-launch in order."""

    # M1 — flip the P0 coaching flags only.
    monkeypatch.setenv("REALITY_OS_COACH_ENABLED", "true")
    monkeypatch.setenv("REALITY_OS_EXPERT_GAP_ENABLED", "true")
    assert feature_flags.coach_enabled() is True
    assert feature_flags.expert_gap_enabled() is True
    # M3 retrieval flags are still off — flipping M1 did not leak.
    assert feature_flags.hybrid_retrieval_enabled() is False
    assert feature_flags.embed_mode() == "disabled"

    # M3 — flip the retrieval flags.
    monkeypatch.setenv("REALITY_OS_HYBRID_RETRIEVAL", "true")
    monkeypatch.setenv("REALITY_OS_EMBED_MODE", "offline")
    assert feature_flags.hybrid_retrieval_enabled() is True
    assert feature_flags.embed_mode() == "offline"
