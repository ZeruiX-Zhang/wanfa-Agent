"""Integration test for ``evidence_gathering.dispatch_search`` (Task 3.13).

Validates Requirement 6.1 — when ``work/verification`` reports
``insufficient_evidence=true`` for a coach turn, an ``expert_search``
task is automatically dispatched seeded with the claim and the
originating coach-turn / decision-log linkage — and Requirement 6.2 —
each search result is written to ``pending_knowledge`` with
``status="pending_review"``, ``formal_knowledge_write=false``,
``external=True``, ``trust_level="untrusted"``, tenant-scoped, and is
linked back to the originating coach turn / ``DecisionLog`` via the
owning ``evidence_gathering_tasks`` row.

Cross-cutting properties this also verifies:

* Audit emission (R13.1 / Property 21) — exactly one
  ``evidence_gathering.dispatched`` row and one
  ``evidence_gathering.pending`` row are emitted in addition to the
  ``evidence_gathering.opened`` row from :func:`open_task`.
* Pending-review default (R11.1) — every pending record carries
  ``status="pending_review"`` and ``formal_knowledge_write=False``.
* Tenant scoping (R12.1) — both the task and every saved pending
  record carry ``task.tenant_id``.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

import pytest

from apps.api.app import audit_events
from apps.api.app.evidence_gathering import (
    GatheringState,
    dispatch_search,
    list_tasks,
    load_task,
    open_task,
)
from apps.api.app.knowledge_core import KnowledgeCore
from apps.api.schemas import PendingKnowledgeRecord


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _PendingStorage:
    """In-memory stand-in for :class:`apps.api.storage.RealityStorage`.

    Implements the minimum surface ``dispatch_search`` calls
    (``save_pending``) so this test stays isolated from the API process
    and the disk-backed ``records`` table.
    """

    def __init__(self) -> None:
        self.records: list[PendingKnowledgeRecord] = []

    def save_pending(
        self, record: PendingKnowledgeRecord
    ) -> PendingKnowledgeRecord:
        self.records.append(record)
        return record


def _fake_search_runner(
    captured_calls: list[dict[str, Any]],
) -> Any:
    """Return a deterministic ``expert_search``-shaped callable.

    The fake records every kwargs call into ``captured_calls`` and
    returns three pre-baked results so the test can assert on the
    pending-knowledge fan-out without hitting the live retrieval
    pipeline.
    """

    def _run(**kwargs: Any) -> dict[str, Any]:
        captured_calls.append(kwargs)
        return {
            "run_id": "run_test",
            "results": [
                {
                    "id": "sr_1",
                    "title": "First principles in venture diligence",
                    "snippet": (
                        "Analysis showing 38% improvement when teams "
                        "anchor on first-principles evidence [1]."
                    ),
                    "url": "https://arxiv.org/abs/test-1",
                    "source_id": "arxiv.org",
                    "snapshot_id": "snap_1",
                    "excerpt_hash": "hash_1",
                },
                {
                    "id": "sr_2",
                    "title": "Counter-argument: confirmation bias risks",
                    "snippet": (
                        "However some argue first-principles framing "
                        "amplifies confirmation bias under deadline pressure."
                    ),
                    "url": "https://hbr.org/article/test-2",
                    "source_id": "hbr.org",
                    "snapshot_id": "snap_2",
                    "excerpt_hash": "hash_2",
                },
                {
                    "id": "sr_3",
                    "title": "Empirical replication note",
                    "snippet": (
                        "Replication study across 12 cohorts; effect "
                        "size 0.42, p<0.05."
                    ),
                    "url": "https://scholar.google.com/article/test-3",
                    "source_id": "scholar.google.com",
                    "snapshot_id": "snap_3",
                    "excerpt_hash": "hash_3",
                },
            ],
            "total_results": 3,
            "absorbed_count": 0,
            "sources_searched": ["arxiv.org", "hbr.org", "scholar.google.com"],
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
# Helpers
# ---------------------------------------------------------------------------


def _new_core(tmp_path) -> KnowledgeCore:
    return KnowledgeCore(path=tmp_path / "kc.sqlite3")


def _read_audit_rows(core: KnowledgeCore, *, action: str) -> list[sqlite3.Row]:
    with sqlite3.connect(core.path) as db:
        db.row_factory = sqlite3.Row
        return list(
            db.execute(
                "select * from audit_log where action = ? order by created_at asc, id asc",
                (action,),
            )
        )


def _read_task_row(core: KnowledgeCore, task_id: str) -> sqlite3.Row | None:
    with sqlite3.connect(core.path) as db:
        db.row_factory = sqlite3.Row
        return db.execute(
            "select * from evidence_gathering_tasks where id = ?", (task_id,)
        ).fetchone()


# ---------------------------------------------------------------------------
# AC: search writes pending_knowledge linked to decision (R6.1, R6.2)
# ---------------------------------------------------------------------------


def test_search_writes_pending_knowledge_linked_to_decision(tmp_path) -> None:
    """``dispatch_search`` writes one ``pending_knowledge`` row per
    search result, links the rows to the originating
    ``evidence_gathering_tasks`` row (which carries the coach_turn /
    decision_log fk), and emits the documented audit events."""

    core = _new_core(tmp_path)
    storage = _PendingStorage()

    tenant_id = "tnt-evdisp"
    session_id = "sess_dispatch_1"
    coach_turn_id = "turn_dispatch_1"
    decision_log_id = "dec_dispatch_1"
    claim = (
        "Adopting first-principles framing improves diligence accuracy "
        "for early-stage AI investments."
    )

    # 1) Open a task in INSUFFICIENT seeded with the claim + linkage.
    task = open_task(
        core=core,
        tenant_id=tenant_id,
        claim=claim,
        session_id=session_id,
        coach_turn_id=coach_turn_id,
        decision_log_id=decision_log_id,
        actor="system",
    )
    assert task.state == GatheringState.INSUFFICIENT
    assert task.coach_turn_id == coach_turn_id
    assert task.decision_log_id == decision_log_id

    # 2) Dispatch the active gathering loop with a deterministic runner.
    captured_calls: list[dict[str, Any]] = []
    runner = _fake_search_runner(captured_calls)

    final_task, pending_records = dispatch_search(
        core=core,
        storage=storage,
        task=task,
        actor="system",
        language="en",
        search_runner=runner,
    )

    # --- 3a) The runner was seeded with the claim + coach/decision ids.
    assert len(captured_calls) == 1
    call = captured_calls[0]
    assert call["tenant_id"] == tenant_id
    assert call["seed_claim"] == claim
    assert call["query"] == claim, (
        "the dispatcher must seed expert_search with the claim, not the raw "
        "user message — R6.1 requires the seed to be the claim itself"
    )
    assert call["session_id"] == session_id
    assert call["coach_turn_id"] == coach_turn_id
    assert call["decision_log_id"] == decision_log_id
    assert call["evidence_gathering_task_id"] == task.id
    assert call["auto_absorb"] is False, (
        "active gathering must default to pending-review only — auto_absorb "
        "would bypass the user approval requirement (R11.1)"
    )

    # --- 3b) Three pending_knowledge rows written, each with the R6.2
    # defaults and tenant-scoped to the task's tenant_id.
    assert len(pending_records) == 3
    assert len(storage.records) == 3, (
        "every result must be persisted via storage.save_pending"
    )
    for rec in pending_records:
        assert rec.tenant_id == tenant_id
        assert rec.status == "pending_review"
        assert rec.review_required is True
        assert rec.formal_knowledge_write is False
        assert rec.external is True
        assert rec.trust_level == "untrusted"
        assert rec.origin == "expert_search"
        assert rec.created_by == "system"
        # Record is linked back to the originating coach turn / decision
        # via tags so a UI can group the pending queue without a join.
        assert f"task:{task.id}" in rec.tags
        assert f"coach_turn:{coach_turn_id}" in rec.tags
        assert f"decision_log:{decision_log_id}" in rec.tags
        assert f"session:{session_id}" in rec.tags

    # The records carry the result snippets (title + body merged).
    titles = {rec.content.split("\n", 1)[0] for rec in pending_records}
    assert any("First principles" in t for t in titles)
    assert any("Counter-argument" in t for t in titles)

    # --- 3c) Task transitioned INSUFFICIENT -> SEARCHING -> PENDING.
    assert final_task.state == GatheringState.PENDING
    assert final_task.id == task.id
    pending_ids_in_task = list(final_task.pending_knowledge_ids)
    saved_ids = [rec.id for rec in pending_records]
    assert pending_ids_in_task == saved_ids, (
        "the task's pending_knowledge_ids must be the ordered ids of the "
        "freshly saved pending_knowledge rows so a verifier can resolve the "
        "review queue from the task alone (R6.2 inverse link)"
    )

    # --- 3d) The DB row reflects the same shape (round-trip persistence).
    row = _read_task_row(core, task.id)
    assert row is not None
    assert row["tenant_id"] == tenant_id
    assert row["state"] == GatheringState.PENDING.value
    assert row["coach_turn_id"] == coach_turn_id
    assert row["decision_log_id"] == decision_log_id
    persisted_pending_ids = json.loads(row["pending_knowledge_ids_json"])
    assert persisted_pending_ids == saved_ids

    # ``load_task`` returns the same shape.
    reloaded = load_task(core=core, tenant_id=tenant_id, task_id=task.id)
    assert reloaded is not None
    assert reloaded.state == GatheringState.PENDING
    assert list(reloaded.pending_knowledge_ids) == saved_ids

    # ``list_tasks`` filtered by decision_log_id finds exactly this task.
    listed = list_tasks(
        core=core, tenant_id=tenant_id, decision_log_id=decision_log_id
    )
    assert [t.id for t in listed] == [task.id]

    # --- 3e) Audit events: opened (from open_task), dispatched, pending.
    opened_rows = _read_audit_rows(
        core, action=audit_events.EVIDENCE_GATHERING_OPENED
    )
    dispatched_rows = _read_audit_rows(
        core, action=audit_events.EVIDENCE_GATHERING_DISPATCHED
    )
    pending_rows = _read_audit_rows(
        core, action=audit_events.EVIDENCE_GATHERING_PENDING
    )
    assert len(opened_rows) == 1, "open_task emits exactly one opened row"
    assert len(dispatched_rows) == 1, (
        "dispatch_search must emit exactly one evidence_gathering.dispatched row"
    )
    assert len(pending_rows) == 1, (
        "dispatch_search must emit exactly one evidence_gathering.pending row"
    )

    dispatched_payload = json.loads(dispatched_rows[0]["payload_json"])
    assert dispatched_payload["task_id"] == task.id
    assert dispatched_payload["state"] == GatheringState.SEARCHING.value
    assert dispatched_payload["coach_turn_id"] == coach_turn_id
    assert dispatched_payload["decision_log_id"] == decision_log_id
    assert dispatched_payload["session_id"] == session_id

    pending_payload = json.loads(pending_rows[0]["payload_json"])
    assert pending_payload["task_id"] == task.id
    assert pending_payload["state"] == GatheringState.PENDING.value
    assert pending_payload["coach_turn_id"] == coach_turn_id
    assert pending_payload["decision_log_id"] == decision_log_id

    # --- 3f) Tenant isolation: a different tenant sees no pending rows
    # nor the task.
    assert (
        list_tasks(core=core, tenant_id="tnt-other", decision_log_id=decision_log_id)
        == []
    )
    assert load_task(core=core, tenant_id="tnt-other", task_id=task.id) is None


def test_dispatch_rejects_task_not_in_insufficient(tmp_path) -> None:
    """Calling ``dispatch_search`` on a task in a terminal state
    (``APPROVED`` or ``CLOSED``) must raise ``ValueError`` from
    :func:`step` and leave both the task and the pending sink
    untouched (Property 21 — illegal events do not mutate state).
    """

    core = _new_core(tmp_path)
    storage = _PendingStorage()
    from apps.api.app.evidence_gathering import apply_step

    # Drive a fresh task through INSUFFICIENT -> CLOSED to land in a
    # terminal state that *cannot* legally transition to SEARCHING.
    task = open_task(
        core=core,
        tenant_id="tnt-bad-state",
        claim="claim already closed with reason",
        session_id="s1",
        coach_turn_id="t1",
        decision_log_id="d1",
        actor="system",
    )
    closed_task = apply_step(
        core=core, task=task, target_state=GatheringState.CLOSED
    )
    assert closed_task.state == GatheringState.CLOSED

    captured_calls: list[dict[str, Any]] = []
    runner = _fake_search_runner(captured_calls)

    with pytest.raises(ValueError):
        dispatch_search(
            core=core,
            storage=storage,
            task=closed_task,  # terminal state
            search_runner=runner,
        )

    # The runner was never invoked and the storage sink stays empty.
    assert captured_calls == []
    assert storage.records == []
    # The persisted task is still CLOSED.
    row = _read_task_row(core, task.id)
    assert row is not None
    assert row["state"] == GatheringState.CLOSED.value
