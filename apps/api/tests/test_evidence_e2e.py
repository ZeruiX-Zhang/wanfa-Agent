"""Integration test — Active Evidence Gathering closure (Task 6.9).

Covers R6.3-R6.6 and R11.4: a decision verdict stays blocked while any
linked gathering task is non-approved; a rejected round keeps the loop
open until the user approves (or explicitly closes) it.
"""

from __future__ import annotations

from apps.api.app.evidence_gathering import (
    GatheringState,
    apply_step,
    approve_task,
    open_task,
    reject_task,
    verdict_allowed_for_decision,
)
from apps.api.app.knowledge_core import KnowledgeCore


def _verdict(core, tenant, decision_id) -> bool:
    return verdict_allowed_for_decision(
        core=core, tenant_id=tenant, decision_log_id=decision_id
    )


def test_decision_blocked_until_pending_approved(tmp_path) -> None:
    """The verdict unlocks only once the gathering task reaches APPROVED."""

    core = KnowledgeCore(path=tmp_path / "kc.sqlite3")
    tenant = "tnt-ev-e2e"
    decision_id = "dec_e2e"

    # No gathering loop ever opened -> verdict allowed by default (R6.3).
    assert _verdict(core, tenant, decision_id) is True

    task = open_task(
        core=core,
        tenant_id=tenant,
        claim="the migration is safe under concurrent writes",
        decision_log_id=decision_id,
        actor="user",
    )
    # An open loop blocks the verdict.
    assert _verdict(core, tenant, decision_id) is False

    task = apply_step(core=core, task=task, target_state=GatheringState.SEARCHING)
    assert _verdict(core, tenant, decision_id) is False

    task = apply_step(core=core, task=task, target_state=GatheringState.PENDING)
    # Still blocked while evidence is only pending review (R11.4).
    assert _verdict(core, tenant, decision_id) is False

    approve_task(core=core, task=task, actor="user")
    # APPROVED closes the loop -> verdict unlocked.
    assert _verdict(core, tenant, decision_id) is True


def test_rejected_keeps_loop_open_until_approve_or_explicit_close(tmp_path) -> None:
    """A rejected round leaves the verdict blocked until a later approval."""

    core = KnowledgeCore(path=tmp_path / "kc.sqlite3")
    tenant = "tnt-ev-e2e-reject"
    decision_id = "dec_e2e_reject"

    task = open_task(
        core=core,
        tenant_id=tenant,
        claim="the vendor SLA covers this outage class",
        decision_log_id=decision_id,
        actor="user",
    )
    task = apply_step(core=core, task=task, target_state=GatheringState.SEARCHING)
    task = apply_step(core=core, task=task, target_state=GatheringState.PENDING)

    # The user rejects this round of evidence (R6.6).
    task = reject_task(core=core, task=task, actor="user")
    assert task.state == GatheringState.REJECTED
    # REJECTED is closed-but-not-approved -> verdict stays blocked.
    assert _verdict(core, tenant, decision_id) is False

    # The loop re-opens: REJECTED -> SEARCHING -> PENDING -> APPROVED.
    task = apply_step(core=core, task=task, target_state=GatheringState.SEARCHING)
    task = apply_step(core=core, task=task, target_state=GatheringState.PENDING)
    assert _verdict(core, tenant, decision_id) is False

    approve_task(core=core, task=task, actor="user")
    assert _verdict(core, tenant, decision_id) is True
