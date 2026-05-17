"""Audit event emission for P0 state changes (Task 2.19, R13.1, R13.4).

Validates that every documented P0 state change emits exactly one
``audit_log`` row with the documented payload keys per design.md
"Audit log event_type catalogue":

* ``coaching_session.created`` — payload: ``session_id``, ``profile_id``
* ``coaching_session_transition`` — payload: ``from_state``, ``to_state``,
  ``session_id``, ``reason``, ``actor``
* ``coaching_session.archived`` — payload: ``session_id``, ``reason``
* ``rubric_check`` — payload: ``domain``, ``version``, ``status``,
  ``cited_evidence_ids``
* ``skill_chain.advance`` — payload: ``session_id``, ``chain_id``,
  ``prev_idx``, ``next_idx``
* ``skill_chain.switch`` — payload: ``session_id``, ``from_chain``,
  ``to_chain``, ``trigger_reason``
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any

import pytest

from apps.api.app import audit_events, expert_rubric, skill_chain
from apps.api.app.coaching_session import CoachingSessionRepo


# ---------------------------------------------------------------------------
# Fake audit sink: lets the rubric/skill_chain helpers emit without
# spinning up a full ``KnowledgeCore`` instance. The real production
# wiring uses ``KnowledgeCore._record_audit`` which has the same shape.
# ---------------------------------------------------------------------------


class _FakeCore:
    """Mimics ``KnowledgeCore._record_audit`` for unit tests."""

    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    def _record_audit(
        self,
        *,
        tenant_id: str,
        actor: str,
        action: str,
        subject: str | None,
        payload: dict[str, Any] | None,
    ) -> str:
        self.records.append(
            {
                "tenant_id": tenant_id,
                "actor": actor,
                "action": action,
                "subject": subject,
                "payload": dict(payload or {}),
            }
        )
        return f"aud_{len(self.records)}"

    def by_action(self, action: str) -> list[dict[str, Any]]:
        return [r for r in self.records if r["action"] == action]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def repo(tmp_path: Path) -> CoachingSessionRepo:
    return CoachingSessionRepo(path=tmp_path / "coach.sqlite3")


@pytest.fixture()
def fake_core() -> _FakeCore:
    return _FakeCore()


# Two minimal YAML rubrics — one valid, one missing the ``author`` field
# so the loader refuses it (R2.5). Both are written into a tmp dir so
# they do not collide with the shipped ``apps/api/expert_rubrics/*``.
_VALID_RUBRIC = textwrap.dedent(
    """
    domain: pbt_event_audit_valid
    version: "0.1.0"
    author: AC Test
    source: tests/test_audit_events_p0.py
    cited_evidence_ids: ["ev-pbt-001", "ev-pbt-002"]
    dimensions:
      - id: framing
        weight: 0.5
        anchors: ["scope", "假设"]
      - id: review
        weight: 0.5
        anchors: ["复盘", "next-step"]
    examples:
      - "States scope and a review trigger."
    """
).strip()


_REFUSED_RUBRIC = textwrap.dedent(
    """
    domain: pbt_event_audit_refused
    version: "0.1.0"
    cited_evidence_ids: []
    dimensions:
      - id: framing
        weight: 1.0
        anchors: ["scope"]
    """
).strip()  # missing ``author`` and ``source``


# ---------------------------------------------------------------------------
# The acceptance criteria test
# ---------------------------------------------------------------------------


def test_p0_audit_events_emitted_with_documented_keys(
    tmp_path: Path,
    repo: CoachingSessionRepo,
    fake_core: _FakeCore,
) -> None:
    """All six P0 audit event types are emitted with documented payload keys."""

    tenant_id = "tnt-p0-events"
    actor = "alice"

    # ------------------------------------------------------------------
    # (a) CoachingSession lifecycle: created → transition → archived
    # ------------------------------------------------------------------
    session = repo.get_or_create(
        tenant_id=tenant_id,
        user_id=actor,
        profile_id="prof_p0",
        actor=actor,
    )
    repo.transition(
        tenant_id=tenant_id,
        session_id=session.id,
        to_state="awaiting_practice",
        reason="mastery_low",
        actor=actor,
    )
    repo.transition(
        tenant_id=tenant_id,
        session_id=session.id,
        to_state="active",
        reason="practice_completed",
        actor=actor,
    )
    repo.transition(
        tenant_id=tenant_id,
        session_id=session.id,
        to_state="archived",
        reason="manual",
        actor=actor,
    )

    # Read the on-disk audit_log rows that the repo writes.
    coaching_rows = _read_audit_log(repo, tenant_id=tenant_id)

    created = [r for r in coaching_rows if r["action"] == audit_events.COACHING_SESSION_CREATED]
    transitions = [
        r for r in coaching_rows if r["action"] == audit_events.COACHING_SESSION_TRANSITION
    ]
    archived = [
        r for r in coaching_rows if r["action"] == audit_events.COACHING_SESSION_ARCHIVED
    ]

    assert len(created) == 1, f"expected 1 created event, got {len(created)}"
    assert len(transitions) == 3, f"expected 3 transition events, got {len(transitions)}"
    assert len(archived) == 1, f"expected 1 archived event, got {len(archived)}"

    # Documented payload keys per design.md "Audit log event_type catalogue".
    created_payload = created[0]["payload"]
    assert {"session_id", "profile_id"} <= set(created_payload.keys())
    assert created_payload["session_id"] == session.id
    assert created_payload["profile_id"] == "prof_p0"

    # Each transition row must carry the documented keys.
    for row in transitions:
        payload = row["payload"]
        assert {"from_state", "to_state", "session_id", "reason"} <= set(payload.keys())
        assert payload["session_id"] == session.id
    # Actor is stored on the row (not necessarily the payload) because the
    # ``audit_log`` table has a dedicated ``actor`` column.
    assert {row["actor"] for row in transitions} == {actor}

    archived_payload = archived[0]["payload"]
    assert {"session_id", "reason"} <= set(archived_payload.keys())
    assert archived_payload["session_id"] == session.id
    assert archived_payload["reason"] == "manual"

    # ------------------------------------------------------------------
    # (b) rubric_check — one ``active`` row + one ``refused`` row
    # ------------------------------------------------------------------
    rubric_dir = tmp_path / "rubrics"
    rubric_dir.mkdir()
    (rubric_dir / "valid.yaml").write_text(_VALID_RUBRIC, encoding="utf-8")
    (rubric_dir / "refused.yaml").write_text(_REFUSED_RUBRIC, encoding="utf-8")

    expert_rubric.reset_cache_for_tests()
    expert_rubric.load_all_with_audit(
        core=fake_core,
        tenant_id=tenant_id,
        actor=actor,
        root=rubric_dir,
        refresh=True,
    )

    rubric_rows = fake_core.by_action(audit_events.RUBRIC_CHECK)
    statuses = [r["payload"]["status"] for r in rubric_rows]
    assert "active" in statuses, f"missing active rubric_check; statuses={statuses}"
    assert "refused" in statuses, f"missing refused rubric_check; statuses={statuses}"

    active_row = next(r for r in rubric_rows if r["payload"]["status"] == "active")
    active_payload = active_row["payload"]
    # design.md catalog: rubric_check payload = domain, version, status,
    # cited_evidence_ids.
    assert {"domain", "version", "status", "cited_evidence_ids"} <= set(active_payload.keys())
    assert active_payload["domain"] == "pbt_event_audit_valid"
    assert active_payload["version"] == "0.1.0"
    assert active_payload["status"] == "active"
    assert active_payload["cited_evidence_ids"] == ["ev-pbt-001", "ev-pbt-002"]

    refused_row = next(r for r in rubric_rows if r["payload"]["status"] == "refused")
    refused_payload = refused_row["payload"]
    assert {"domain", "version", "status", "cited_evidence_ids"} <= set(refused_payload.keys())
    assert refused_payload["status"] == "refused"
    # ``refused_reason`` is an additive payload key for refused rubrics
    # (R2.5 troubleshooting).
    assert "refused_reason" in refused_payload

    # ------------------------------------------------------------------
    # (c) skill_chain.advance + skill_chain.switch
    # ------------------------------------------------------------------
    advance_chain = skill_chain.SkillChain(
        id="advance_test_chain",
        problem_type="general",
        description="",
        steps=(
            skill_chain.ChainStep(
                skill_id="problem-statement",
                description="",
                entry_conditions=("always",),
                exit_conditions=("always",),
            ),
            skill_chain.ChainStep(
                skill_id="five-whys",
                description="",
                entry_conditions=("always",),
                exit_conditions=("always",),
            ),
        ),
        entry_conditions=("always",),
    )
    initial = skill_chain.initial_state(advance_chain, {"always": True})

    advance_result = skill_chain.transition_with_audit(
        core=fake_core,
        tenant_id=tenant_id,
        actor=actor,
        session_id=session.id,
        chain=advance_chain,
        state=initial,
        context={"always": True},
    )
    assert advance_result.advance is True

    # Build a second chain so the switch path lands on a different chain
    # whose entry conditions hold.
    switch_target = skill_chain.SkillChain(
        id="switch_target_chain",
        problem_type="other",
        description="",
        steps=(
            skill_chain.ChainStep(
                skill_id="jtbd",
                description="",
                entry_conditions=("always",),
                exit_conditions=(),  # no exit so it cannot advance immediately
            ),
        ),
        entry_conditions=("always",),
    )
    # Reset the source chain's current step exit so transition_with_audit
    # falls into the failure-driven switch path (failures >= threshold).
    nonexit_chain = skill_chain.SkillChain(
        id="advance_test_chain",  # same id so audit row's from_chain matches
        problem_type="general",
        description="",
        steps=(
            skill_chain.ChainStep(
                skill_id="problem-statement",
                description="",
                entry_conditions=("always",),
                exit_conditions=("never_satisfied",),
            ),
        ),
        entry_conditions=("always",),
    )
    nonexit_state = skill_chain.initial_state(nonexit_chain, {"always": True})
    switch_result = skill_chain.transition_with_audit(
        core=fake_core,
        tenant_id=tenant_id,
        actor=actor,
        session_id=session.id,
        chain=nonexit_chain,
        state=nonexit_state,
        context={"always": True},
        failures=3,
        failure_threshold=2,
        chains=[nonexit_chain, switch_target],
    )
    assert switch_result.switched is True
    assert switch_result.next_state is not None
    assert switch_result.next_state.chain_id == "switch_target_chain"

    advance_rows = fake_core.by_action(audit_events.SKILL_CHAIN_ADVANCE)
    switch_rows = fake_core.by_action(audit_events.SKILL_CHAIN_SWITCH)
    assert len(advance_rows) == 1, f"expected 1 advance row, got {len(advance_rows)}"
    assert len(switch_rows) == 1, f"expected 1 switch row, got {len(switch_rows)}"

    advance_payload = advance_rows[0]["payload"]
    assert {"session_id", "chain_id", "prev_idx", "next_idx"} <= set(advance_payload.keys())
    assert advance_payload["session_id"] == session.id
    assert advance_payload["chain_id"] == "advance_test_chain"
    assert advance_payload["prev_idx"] == 0
    assert advance_payload["next_idx"] == 1

    switch_payload = switch_rows[0]["payload"]
    assert {"session_id", "from_chain", "to_chain", "trigger_reason"} <= set(
        switch_payload.keys()
    )
    assert switch_payload["session_id"] == session.id
    assert switch_payload["from_chain"] == "advance_test_chain"
    assert switch_payload["to_chain"] == "switch_target_chain"
    assert switch_payload["trigger_reason"] == "consecutive_failures"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_audit_log(
    repo: CoachingSessionRepo, *, tenant_id: str
) -> list[dict[str, Any]]:
    """Read all audit_log rows the repo wrote, decoding the JSON payload."""

    with repo._connect() as db:  # type: ignore[attr-defined]
        rows = db.execute(
            "select id, tenant_id, actor, action, subject, payload_json, created_at "
            "from audit_log where tenant_id = ? order by created_at asc",
            (tenant_id,),
        ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "id": row["id"],
                "tenant_id": row["tenant_id"],
                "actor": row["actor"],
                "action": row["action"],
                "subject": row["subject"],
                "payload": json.loads(row["payload_json"] or "{}"),
            }
        )
    return out
