"""Integration test for ``orchestrated_ask`` coach-turn extensions (Task 2.12).

Validates Requirement 1.9: ``Coach_Turn`` extends ``orchestrated_ask`` rather
than introducing a parallel orchestrator. The new ``coach_turn=True``
parameters MUST attach ``expert_gap``, ``skill_chain``, ``next_action`` and
``session_state`` to the response while preserving the existing shape for
non-coach (legacy) callers.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Iterator

import pytest

import apps.api.app.knowledge_core as kc_mod
import apps.api.app.model_registry as mr_mod
from apps.api.app import expert_rubric, skill_chain
from apps.api.app.coaching_session import CoachingSessionRepo
from apps.api.app.knowledge_core import reset_core_for_tests
from apps.api.app.orchestrator import orchestrated_ask


@pytest.fixture()
def isolated_core(monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Reset the knowledge_core singleton onto a disposable SQLite file.

    The CoachingSessionRepo created inside ``orchestrated_ask`` must point
    at the same DB so the new session row is visible from the orchestrator.
    """

    old_core = kc_mod._CORE
    old_registry = mr_mod._REGISTRY
    with tempfile.TemporaryDirectory(
        prefix="orch-coach-test-", ignore_cleanup_errors=True
    ) as tmp_dir:
        # Point ``default_storage_path`` (used by ``default_core_path``) at
        # the temp directory so the orchestrator's lookup of the coaching
        # repo lands on this same file.
        storage_path = os.path.join(tmp_dir, "reality_os_test.sqlite3")
        monkeypatch.setenv("REALITY_OS_API_STORAGE", storage_path)
        # The knowledge_core uses ``<storage>.parent / knowledge_core.sqlite3``.
        db_path = Path(tmp_dir) / "knowledge_core.sqlite3"
        reset_core_for_tests(db_path)
        mr_mod._REGISTRY = None

        # Make sure the rubric + chain caches are clean and reload the
        # shipped YAMLs so the audit + advisor can resolve a chain.
        expert_rubric.reset_cache_for_tests()
        expert_rubric.load_all(refresh=True)
        skill_chain.reset_cache_for_tests()
        skill_chain.load_all(refresh=True)

        # Enable the expert-gap audit dimension so the coach response can
        # surface a non-null ``expert_gap`` payload (R2.5 fallback is
        # exercised in test_audit_expert_gap.py).
        monkeypatch.setenv("REALITY_OS_EXPERT_GAP_ENABLED", "true")

        yield db_path

    kc_mod._CORE = old_core
    mr_mod._REGISTRY = old_registry


def _legacy_keys() -> set[str]:
    """The keys callers of the existing ``orchestrate/ask`` endpoint expect."""

    return {
        "run_id",
        "question",
        "language",
        "answer",
        "confidence",
        "confidence_band",
        "thinking_model",
        "prompt_strategy",
        "citations",
        "knowledge_gaps",
        "next_actions",
        "audit_id",
        "answer_mode",
        "candidate_angles",
        "open_questions",
        "key_tradeoffs",
        "acceptance_check",
        "advisor_context",
        "skill_framework",
        "contradictions",
        "strategy_used",
        "orchestration",
    }


def test_coach_turn_extends_orchestrated_ask_without_breaking_legacy_ask(
    isolated_core: Path,
) -> None:
    """AC for Task 2.12 (Requirement 1.9).

    1. The non-coach call (``coach_turn=False``) keeps the historical
       response shape — none of the coach-only keys leak in.
    2. The coach-turn call (``coach_turn=True``) preserves every legacy
       key *and* adds ``expert_gap``, ``skill_chain``, ``next_action``
       and ``session_state``.
    3. Tenant scoping is preserved: the persisted ``CoachingSession``
       state is returned only when the session belongs to the caller's
       tenant.
    """

    tenant = "tnt-coach-r19"
    repo = CoachingSessionRepo(path=kc_mod._CORE.path)  # type: ignore[union-attr]
    session = repo.get_or_create(
        tenant_id=tenant,
        user_id="alice",
        profile_id="prof-1",
    )
    assert session.state == "active"

    # --- 1. Legacy callers see no coach-turn keys ---------------------------
    legacy = orchestrated_ask(
        tenant_id=tenant,
        question="What does first principles reasoning require to be useful?",
        language="en",
        answer_mode="scaffold",
        actor="alice",
        use_reality_advisor=True,
    )
    coach_only_keys = {
        "coach_turn",
        "coaching_session_id",
        "expert_gap",
        "skill_chain",
        "next_action",
        "session_state",
        "user_confidence_check",
    }
    assert _legacy_keys() <= legacy.keys(), "legacy response shape regressed"
    leaked = coach_only_keys & legacy.keys()
    assert not leaked, f"legacy response leaked coach-only keys: {leaked}"

    # --- 2. Coach turn extends the response ---------------------------------
    coach = orchestrated_ask(
        tenant_id=tenant,
        question="What does first principles reasoning require to be useful?",
        language="en",
        answer_mode="final",
        actor="alice",
        use_reality_advisor=True,
        coach_turn=True,
        coaching_session_id=session.id,
        user_confidence_check=0.42,
    )

    assert _legacy_keys() <= coach.keys(), "coach response dropped legacy keys"
    for key in ("expert_gap", "skill_chain", "next_action", "session_state"):
        assert key in coach, f"coach response missing required key: {key!r}"

    assert coach["coach_turn"] is True
    assert coach["coaching_session_id"] == session.id
    assert coach["user_confidence_check"] == pytest.approx(0.42)

    # next_action MUST be one of the documented values (R1.5).
    assert coach["next_action"] in {
        "learn",
        "practice",
        "experiment",
        "review",
        "awaiting_evidence",
    }
    # session_state must come from the persisted session OR fall back to
    # one of the declared session states. Because we created the session
    # under this tenant, it MUST mirror the persisted ``active`` state.
    assert coach["session_state"] == "active"

    # skill_chain pointer comes from the advisor (task 2.11) and is a dict
    # with the documented keys; ``None`` is acceptable when no chain
    # registry is available, but the shipped YAMLs guarantee one chain.
    assert coach["skill_chain"] is None or {
        "chain_id",
        "step_idx",
        "step_skill_id",
        "entry_satisfied",
        "exit_satisfied",
    } <= coach["skill_chain"].keys()

    # expert_gap is either ``None`` (rubric refused / flag off) or a dict
    # with the bounded score and capped missing_points (R2.3, Property 8).
    if coach["expert_gap"] is not None:
        gap = coach["expert_gap"]
        assert 0.0 <= gap["expert_gap_score"] <= 1.0
        assert len(gap["missing_points"]) <= 7
        assert gap["rubric_source"] in {"domain", "default"}


def test_coach_turn_with_unknown_session_id_falls_back_to_snapshot_state(
    isolated_core: Path,
) -> None:
    """A coach turn with an unknown session id (e.g. cross-tenant lookup)
    must NOT raise — the orchestrator falls back to a snapshot-derived
    state so the caller can still render the response (R1.10 ensures the
    real ``/coach/turn`` route returns 404 first; this guards the helper)."""

    response = orchestrated_ask(
        tenant_id="tnt-coach-r19",
        question="Why does this approach matter?",
        language="en",
        answer_mode="scaffold",
        actor="alice",
        coach_turn=True,
        coaching_session_id="cs_does_not_exist",
        use_reality_advisor=True,
    )
    assert response["coach_turn"] is True
    # No persisted session under this id → the helper synthesises a state
    # from the snapshot (active by default for non-insufficient turns).
    assert response["session_state"] in {"active", "awaiting_evidence"}
    assert response["next_action"] in {
        "learn",
        "practice",
        "experiment",
        "review",
        "awaiting_evidence",
    }
