"""Integration test for orchestrator-driven Active Evidence Gathering (Task 3.14).

Validates Requirements:

* **R6.3** — A ``DecisionLog`` verdict is blocked while any linked
  ``evidence_gathering_tasks`` row remains in a non-``APPROVED`` state.
  Only after the user explicitly approves at least one round and the
  re-run verification no longer reports ``insufficient_evidence`` does
  ``verdict_allowed`` flip to ``True``.
* **R6.4** — Approving the linked pending evidence triggers a
  re-verification pass. The orchestrator advertises the freshened
  state so callers (`/api/v2/coach/turn`,
  ``/api/v2/decisions/{id}/publish``) can release the verdict.
* **R6.6** — Rejecting pending evidence keeps the loop open. The
  ``DecisionLog.verdict`` MUST stay empty until at least one approved
  item exists (or the user explicitly closes the loop with a
  documented reason).

The test drives the *real* :func:`orchestrated_ask` against a
disposable :class:`KnowledgeCore` and a tiny in-memory
``_PendingStorage`` fake (mirrors the pattern in
``test_evidence_dispatch.py``). The ``expert_search`` runner is also a
fake so the closed loop is exercised deterministically without hitting
the live retrieval pipeline.
"""

from __future__ import annotations

import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Iterator

import pytest

import apps.api.app.knowledge_core as kc_mod
import apps.api.app.model_registry as mr_mod
from apps.api.app import audit_events, expert_rubric, skill_chain
from apps.api.app.evidence_gathering import (
    GatheringState,
    apply_step,
    approve_task,
    list_tasks,
    load_task,
    reject_task,
    verdict_allowed_for_decision,
)
from apps.api.app.knowledge_core import reset_core_for_tests
from apps.api.app.orchestrator import orchestrated_ask
from apps.api.schemas import PendingKnowledgeRecord


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _PendingStorage:
    """Minimal stand-in for :class:`apps.api.storage.RealityStorage`.

    Implements the ``save_pending`` surface that
    :func:`evidence_gathering.dispatch_search` calls so the closed loop
    runs without the disk-backed ``records`` table.
    """

    def __init__(self) -> None:
        self.records: list[PendingKnowledgeRecord] = []

    def save_pending(
        self, record: PendingKnowledgeRecord
    ) -> PendingKnowledgeRecord:
        self.records.append(record)
        return record


def _fake_search_runner(captured: list[dict[str, Any]]) -> Any:
    """Deterministic ``expert_search``-shaped callable used by
    :func:`evidence_gathering.dispatch_search`.

    Returns two pre-baked candidates — that is enough to exercise the
    pending → approved / pending → rejected paths without making the
    test sensitive to retrieval ordering.
    """

    def _run(**kwargs: Any) -> dict[str, Any]:
        captured.append(kwargs)
        return {
            "run_id": "run_test_evidence",
            "results": [
                {
                    "id": "sr_1",
                    "title": "Source one",
                    "snippet": "Empirical evidence supporting the claim.",
                    "url": "https://example.com/1",
                    "source_id": "example.com",
                },
                {
                    "id": "sr_2",
                    "title": "Source two",
                    "snippet": "Counter-argument with corroborating data.",
                    "url": "https://example.com/2",
                    "source_id": "example.com",
                },
            ],
            "total_results": 2,
            "absorbed_count": 0,
            "sources_searched": ["example.com"],
            "strategy_name": "default",
            "original_query": kwargs.get("query"),
            "optimized_query": {"original": kwargs.get("query"), "optimized": ""},
            "optimized_query_model": None,
            "optimization_source": "deterministic",
            "seed_claim": kwargs.get("seed_claim"),
            "session_id": kwargs.get("session_id"),
            "coach_turn_id": kwargs.get("coach_turn_id"),
            "decision_log_id": kwargs.get("decision_log_id"),
            "evidence_gathering_task_id": kwargs.get("evidence_gathering_task_id"),
        }

    return _run


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def isolated_core(monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Reset the knowledge_core singleton onto a disposable SQLite file.

    Mirrors the fixture in ``test_orchestrator_coach.py`` so the
    orchestrator's ``get_core()`` lookup lands on the same DB used by
    the test fakes (the ``evidence_gathering_tasks`` rows are written
    by the orchestrator, the ``pending_knowledge`` rows by our in-memory
    sink).
    """

    old_core = kc_mod._CORE
    old_registry = mr_mod._REGISTRY
    with tempfile.TemporaryDirectory(
        prefix="orch-evid-test-", ignore_cleanup_errors=True
    ) as tmp_dir:
        storage_path = os.path.join(tmp_dir, "reality_os_test.sqlite3")
        monkeypatch.setenv("REALITY_OS_API_STORAGE", storage_path)
        db_path = Path(tmp_dir) / "knowledge_core.sqlite3"
        reset_core_for_tests(db_path)
        mr_mod._REGISTRY = None

        # Reset rubric + chain caches so the audit + advisor steps run
        # cleanly under the fresh DB.
        expert_rubric.reset_cache_for_tests()
        expert_rubric.load_all(refresh=True)
        skill_chain.reset_cache_for_tests()
        skill_chain.load_all(refresh=True)

        # Keep the expert-gap audit dimension on so the response shape
        # matches the production coach-turn surface (R2.5 fallback is
        # not the focus here).
        monkeypatch.setenv("REALITY_OS_EXPERT_GAP_ENABLED", "true")

        yield db_path

    kc_mod._CORE = old_core
    mr_mod._REGISTRY = old_registry


def _read_audit_rows(path: Path, *, action: str) -> list[sqlite3.Row]:
    with sqlite3.connect(path) as db:
        db.row_factory = sqlite3.Row
        return list(
            db.execute(
                "select * from audit_log where action = ? "
                "order by created_at asc, id asc",
                (action,),
            )
        )


# ---------------------------------------------------------------------------
# AC: verdict blocked until pending approved (R6.3, R6.4)
# ---------------------------------------------------------------------------


def test_verdict_blocked_until_pending_approved(
    isolated_core: Path,
) -> None:
    """The full Active-Evidence-Gathering closure (R6.3, R6.4).

    Steps:

    1. Trigger a coach turn whose verifier reports
       ``confidence_band="insufficient"`` (no library content → no
       citations → ``aggregate < 0.3``). The orchestrator MUST open an
       ``evidence_gathering_tasks`` row linked to the supplied
       ``decision_log_id``, dispatch ``expert_search``, and surface
       the task id + state on the response.
    2. While the task is in ``PENDING`` (post-dispatch), the
       orchestrator's ``verdict_allowed`` MUST be ``False`` and the
       session MUST sit in ``awaiting_evidence`` with
       ``next_action == "awaiting_evidence"`` (R6.3 / R11.4).
    3. The user approves the pending evidence
       (``apply_step(PENDING -> APPROVED)``). A second coach turn (the
       "re-run verification" call per R6.4) must observe
       ``verdict_allowed=True`` for the same decision log.
    """

    captured: list[dict[str, Any]] = []
    runner = _fake_search_runner(captured)
    storage = _PendingStorage()

    tenant = "tnt-orch-evid-1"
    decision_log_id = "dec_orch_1"
    claim = (
        "Adopting first-principles framing improves diligence accuracy "
        "for early-stage AI investments."
    )

    # 1) Insufficient turn → opens + dispatches a gathering task.
    response = orchestrated_ask(
        tenant_id=tenant,
        question=claim,
        language="en",
        answer_mode="scaffold",
        actor="alice",
        coach_turn=True,
        coaching_session_id=None,
        decision_log_id=decision_log_id,
        evidence_storage=storage,
        evidence_search_runner=runner,
        use_reality_advisor=True,
    )

    # The orchestrator must report insufficient evidence.
    assert response["confidence_band"] == "insufficient"
    assert response["coach_turn"] is True
    assert response["decision_log_id"] == decision_log_id

    # An evidence_gathering payload is attached and the task ended in
    # PENDING after dispatch_search persisted the candidates.
    gathering = response["evidence_gathering"]
    assert gathering is not None, "expected an evidence_gathering payload"
    assert gathering["state"] == GatheringState.PENDING.value
    assert gathering["claim"] == claim
    assert gathering["decision_log_id"] == decision_log_id
    assert gathering["dispatch_status"] == "dispatched"
    pending_ids = gathering["pending_knowledge_ids"]
    assert len(pending_ids) == 2
    assert all(rec.tenant_id == tenant for rec in storage.records)
    assert all(rec.status == "pending_review" for rec in storage.records)
    assert all(
        rec.formal_knowledge_write is False for rec in storage.records
    )

    # The expert_search runner was seeded with the claim + decision id.
    assert len(captured) == 1
    assert captured[0]["seed_claim"] == claim
    assert captured[0]["decision_log_id"] == decision_log_id

    # Coach surface: next_action / session_state advertise the loop.
    assert response["next_action"] == "awaiting_evidence"
    assert response["session_state"] == "awaiting_evidence"

    # Verdict gate: blocked while the task is PENDING (R6.3, R11.4).
    assert response["verdict_allowed"] is False

    # The persisted task row exists for the right tenant.
    task_id = gathering["task_id"]
    task = load_task(core=kc_mod._CORE, tenant_id=tenant, task_id=task_id)
    assert task is not None
    assert task.state == GatheringState.PENDING
    assert task.decision_log_id == decision_log_id

    # Audit trail: opened + dispatched + pending events were emitted.
    opened = _read_audit_rows(
        isolated_core, action=audit_events.EVIDENCE_GATHERING_OPENED
    )
    dispatched = _read_audit_rows(
        isolated_core, action=audit_events.EVIDENCE_GATHERING_DISPATCHED
    )
    pending = _read_audit_rows(
        isolated_core, action=audit_events.EVIDENCE_GATHERING_PENDING
    )
    assert len(opened) == 1
    assert len(dispatched) == 1
    assert len(pending) == 1

    # 2) verdict_allowed_for_decision agrees with the orchestrator gate.
    assert (
        verdict_allowed_for_decision(
            core=kc_mod._CORE, tenant_id=tenant, decision_log_id=decision_log_id
        )
        is False
    )

    # 3) User approves the pending evidence (R6.4).
    approved = approve_task(core=kc_mod._CORE, task=task, actor="alice")
    assert approved.state == GatheringState.APPROVED
    approval_audits = _read_audit_rows(
        isolated_core, action=audit_events.EVIDENCE_GATHERING_APPROVED
    )
    assert len(approval_audits) == 1

    # The verdict gate now flips: every linked task is APPROVED.
    assert (
        verdict_allowed_for_decision(
            core=kc_mod._CORE, tenant_id=tenant, decision_log_id=decision_log_id
        )
        is True
    )

    # R6.4 — once every linked task is APPROVED the orchestrator's
    # ``verdict_allowed`` MUST report ``True`` for any read-only query
    # against the same decision. We use the orchestrator's helper
    # directly here rather than re-running the coach turn — the latter
    # would open a *fresh* gathering task on the same insufficient
    # claim (legitimate behaviour: the user is asking again about
    # something the system still cannot ground), and that fresh task
    # is *not* part of the original loop the user just approved.
    from apps.api.app.orchestrator import _evidence_verdict_allowed

    assert (
        _evidence_verdict_allowed(
            tenant_id=tenant, decision_log_id=decision_log_id
        )
        is True
    )


# ---------------------------------------------------------------------------
# AC: rejected keeps loop open (R6.6)
# ---------------------------------------------------------------------------


def test_rejected_keeps_loop_open(isolated_core: Path) -> None:
    """Rejecting pending evidence keeps the loop open (R6.6).

    After the orchestrator opens + dispatches a task and the user
    rejects it (``PENDING -> REJECTED``), the verdict gate MUST stay
    blocked. The decision log's verdict can only be released when at
    least one approved item exists for the linked gathering task —
    rejection does *not* release it on its own.

    To prove the gate also unblocks once a fresh round is approved we
    drive ``REJECTED -> SEARCHING -> PENDING -> APPROVED`` and assert
    the gate flips on the final approval.
    """

    captured: list[dict[str, Any]] = []
    runner = _fake_search_runner(captured)
    storage = _PendingStorage()

    tenant = "tnt-orch-evid-2"
    decision_log_id = "dec_orch_2"
    claim = "Pre-mortems reduce shipping defects in regulated software."

    response = orchestrated_ask(
        tenant_id=tenant,
        question=claim,
        language="en",
        answer_mode="scaffold",
        actor="bob",
        coach_turn=True,
        decision_log_id=decision_log_id,
        evidence_storage=storage,
        evidence_search_runner=runner,
        use_reality_advisor=True,
    )

    gathering = response["evidence_gathering"]
    assert gathering is not None
    assert gathering["state"] == GatheringState.PENDING.value
    assert gathering["decision_log_id"] == decision_log_id
    task_id = gathering["task_id"]

    task = load_task(core=kc_mod._CORE, tenant_id=tenant, task_id=task_id)
    assert task is not None
    assert task.state == GatheringState.PENDING

    # User rejects — loop must stay open (R6.6).
    rejected = reject_task(core=kc_mod._CORE, task=task, actor="bob")
    assert rejected.state == GatheringState.REJECTED

    rejection_audits = _read_audit_rows(
        isolated_core, action=audit_events.EVIDENCE_GATHERING_REJECTED
    )
    assert len(rejection_audits) == 1

    # Verdict gate stays blocked: REJECTED is *not* APPROVED.
    assert (
        verdict_allowed_for_decision(
            core=kc_mod._CORE, tenant_id=tenant, decision_log_id=decision_log_id
        )
        is False
    )

    # And a re-run coach turn confirms the same: verdict_allowed=False.
    response_after_reject = orchestrated_ask(
        tenant_id=tenant,
        question=claim,
        language="en",
        answer_mode="scaffold",
        actor="bob",
        coach_turn=True,
        decision_log_id=decision_log_id,
        evidence_storage=storage,
        evidence_search_runner=_fake_search_runner([]),
        use_reality_advisor=True,
    )
    # The re-run opened *another* gathering task (R6.1 fires whenever
    # the verifier reports insufficient), but the gate stays blocked
    # because none of the linked tasks is APPROVED.
    assert response_after_reject["verdict_allowed"] is False

    # Drive the original task through a fresh search → pending → approve
    # cycle (R6.6 closure path: rejection keeps the loop open until
    # *another* round is approved).
    searching_again = apply_step(
        core=kc_mod._CORE, task=rejected, target_state=GatheringState.SEARCHING
    )
    pending_again = apply_step(
        core=kc_mod._CORE,
        task=searching_again,
        target_state=GatheringState.PENDING,
    )
    approved_again = approve_task(
        core=kc_mod._CORE, task=pending_again, actor="bob"
    )
    assert approved_again.state == GatheringState.APPROVED

    # The other task spawned by the re-run still blocks the gate.
    assert (
        verdict_allowed_for_decision(
            core=kc_mod._CORE, tenant_id=tenant, decision_log_id=decision_log_id
        )
        is False
    )

    # Approve every other linked task too — the gate finally flips.
    other_tasks = [
        t
        for t in list_tasks(
            core=kc_mod._CORE,
            tenant_id=tenant,
            decision_log_id=decision_log_id,
        )
        if t.id != approved_again.id and t.state != GatheringState.APPROVED
    ]
    for t in other_tasks:
        if t.state == GatheringState.PENDING:
            approve_task(core=kc_mod._CORE, task=t, actor="bob")
        else:
            # Any task in INSUFFICIENT or SEARCHING is force-driven
            # through the canonical INSUFFICIENT → SEARCHING → PENDING →
            # APPROVED path so the gate can release.
            current = t
            if current.state == GatheringState.INSUFFICIENT:
                current = apply_step(
                    core=kc_mod._CORE,
                    task=current,
                    target_state=GatheringState.SEARCHING,
                )
            if current.state == GatheringState.SEARCHING:
                current = apply_step(
                    core=kc_mod._CORE,
                    task=current,
                    target_state=GatheringState.PENDING,
                )
            if current.state == GatheringState.PENDING:
                approve_task(core=kc_mod._CORE, task=current, actor="bob")

    assert (
        verdict_allowed_for_decision(
            core=kc_mod._CORE, tenant_id=tenant, decision_log_id=decision_log_id
        )
        is True
    )
