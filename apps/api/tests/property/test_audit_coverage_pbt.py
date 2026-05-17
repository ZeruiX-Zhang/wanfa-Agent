"""Property-based test for audit event coverage.

Feature: expert-coaching-loop, Property 21: each accepted state-changing
call emits exactly one audit_log row; a rejected call emits none
(R13.1-4).
"""

from __future__ import annotations

import sqlite3

from hypothesis import given, settings, strategies as st

from apps.api.app import audit_events
from apps.api.app.coaching_session import (
    ALLOWED_TRANSITIONS,
    ArchivedSessionWrite,
    CoachingSessionRepo,
    InvalidStateTransition,
    SESSION_STATES,
    is_allowed,
)

_TENANT = "tnt-audit-coverage-pbt"


def _count_transition_audits(repo: CoachingSessionRepo, session_id: str) -> int:
    with repo._connect() as db:  # type: ignore[attr-defined]
        row = db.execute(
            "select count(*) from audit_log "
            "where tenant_id = ? and action = ? and subject = ?",
            (_TENANT, audit_events.COACHING_SESSION_TRANSITION, session_id),
        ).fetchone()
    return int(row[0])


def test_property_21_one_audit_per_accepted_state_change_and_none_on_reject(
    tmp_path,
) -> None:
    """Accepted transitions emit exactly one audit row; rejected ones emit none."""

    repo = CoachingSessionRepo(path=tmp_path / "coach.sqlite3")

    @settings(max_examples=120, deadline=None)
    @given(to_state=st.sampled_from(SESSION_STATES))
    def _check(to_state: str) -> None:
        # Each example gets a fresh ``active`` session (R1.4).
        session = repo.get_or_create(
            tenant_id=_TENANT, user_id="u", profile_id="p", actor="u"
        )
        assert session.state == "active"

        before = _count_transition_audits(repo, session.id)
        accepted = is_allowed("active", to_state)  # type: ignore[arg-type]

        rejected = False
        try:
            repo.transition(
                tenant_id=_TENANT,
                session_id=session.id,
                to_state=to_state,  # type: ignore[arg-type]
                reason="pbt",
                actor="u",
            )
        except (InvalidStateTransition, ArchivedSessionWrite):
            rejected = True

        after = _count_transition_audits(repo, session.id)

        if accepted:
            assert not rejected
            assert after - before == 1, "accepted change must emit one audit row"
        else:
            assert rejected
            assert after - before == 0, "rejected change must emit no audit row"

    _check()
