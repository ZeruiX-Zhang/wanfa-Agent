"""Tests for the CoachingSession aggregate + repository (Tasks 2.1, 2.2, 2.4)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from apps.api.app.coaching_session import (
    ALLOWED_TRANSITIONS,
    ArchivedSessionWrite,
    CoachingSessionRepo,
    InvalidStateTransition,
    is_allowed,
)


@pytest.fixture()
def repo(tmp_path: Path) -> CoachingSessionRepo:
    return CoachingSessionRepo(path=tmp_path / "coach.sqlite3")


def test_repo_get_or_create_creates_session_when_id_missing(
    repo: CoachingSessionRepo,
) -> None:
    session = repo.get_or_create(
        tenant_id="tnt",
        user_id="alice",
        profile_id="prof_1",
    )

    assert session.id.startswith("cs_")
    assert session.state == "active"
    assert session.tenant_id == "tnt"
    assert session.profile_id == "prof_1"
    assert session.consecutive_failures == 0
    assert session.archived_at is None

    fetched = repo.get(tenant_id="tnt", session_id=session.id)
    assert fetched == session


def test_get_returns_none_for_other_tenant(repo: CoachingSessionRepo) -> None:
    a = repo.get_or_create(tenant_id="tnt-a", user_id="u", profile_id="p")
    other = repo.get(tenant_id="tnt-b", session_id=a.id)
    assert other is None


def test_state_machine_validity_for_every_pair(repo: CoachingSessionRepo) -> None:
    """Property 1 — every declared transition is accepted; every other
    transition raises ``InvalidStateTransition`` and the row is unchanged.
    The ``archived`` source state is covered separately because writes
    against archived sessions raise :class:`ArchivedSessionWrite` (R1.7).
    """

    states: list[str] = [s for s in ALLOWED_TRANSITIONS.keys() if s != "archived"]
    for from_state in states:
        for to_state in ALLOWED_TRANSITIONS.keys():
            session = repo.get_or_create(tenant_id="tnt", user_id="u", profile_id="p")
            # Seed the desired ``from_state`` directly so the test focuses on
            # the transition rule rather than path-finding.
            with repo._connect() as db:  # type: ignore[attr-defined]
                db.execute(
                    "update coaching_sessions set state = ? where id = ?",
                    (from_state, session.id),
                )

            current = repo.get(tenant_id="tnt", session_id=session.id)
            assert current is not None and current.state == from_state

            allowed = is_allowed(from_state, to_state)
            if allowed:
                result = repo.transition(
                    tenant_id="tnt", session_id=session.id, to_state=to_state
                )
                assert result.state == to_state
            else:
                with pytest.raises(InvalidStateTransition):
                    repo.transition(
                        tenant_id="tnt", session_id=session.id, to_state=to_state
                    )
                after = repo.get(tenant_id="tnt", session_id=session.id)
                assert after is not None
                assert after.state == from_state


def test_transition_emits_state_log_and_audit(repo: CoachingSessionRepo) -> None:
    session = repo.get_or_create(tenant_id="tnt", user_id="u", profile_id="p")
    repo.transition(
        tenant_id="tnt",
        session_id=session.id,
        to_state="awaiting_evidence",
        reason="insufficient_evidence",
        actor="alice",
    )
    log = repo.list_state_log(tenant_id="tnt", session_id=session.id)
    assert len(log) == 1
    entry = log[0]
    assert entry.from_state == "active"
    assert entry.to_state == "awaiting_evidence"
    assert entry.reason == "insufficient_evidence"
    assert entry.actor == "alice"


def test_archived_session_rejects_writes(repo: CoachingSessionRepo) -> None:
    """Property 4 — archived sessions raise ``ArchivedSessionWrite`` on write."""

    session = repo.get_or_create(tenant_id="tnt", user_id="u", profile_id="p")
    repo.transition(
        tenant_id="tnt", session_id=session.id, to_state="archived", reason="manual"
    )
    after = repo.get(tenant_id="tnt", session_id=session.id)
    assert after is not None
    assert after.state == "archived"
    assert after.archived_at is not None

    # Reads still succeed.
    assert repo.get(tenant_id="tnt", session_id=session.id) is not None

    # Writes refused.
    with pytest.raises(ArchivedSessionWrite):
        repo.transition(
            tenant_id="tnt", session_id=session.id, to_state="active", reason="resume"
        )


def test_archive_idle_archives_old_sessions(repo: CoachingSessionRepo) -> None:
    """Property 3 — ``archive_idle`` archives iff ``now - last_turn_at >= idle_days``."""

    # Create two sessions: one will be backdated, one fresh.
    old = repo.get_or_create(tenant_id="tnt", user_id="u", profile_id="p")
    fresh = repo.get_or_create(tenant_id="tnt", user_id="u", profile_id="p")

    # Backdate the old one's last_turn_at to 31 days ago.
    backdated = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
    with repo._connect() as db:  # type: ignore[attr-defined]
        db.execute(
            "update coaching_sessions set last_turn_at = ? where id = ?",
            (backdated, old.id),
        )

    archived = repo.archive_idle(tenant_id="tnt", idle_days=30)
    assert archived == 1

    after_old = repo.get(tenant_id="tnt", session_id=old.id)
    after_fresh = repo.get(tenant_id="tnt", session_id=fresh.id)
    assert after_old is not None and after_old.state == "archived"
    assert after_fresh is not None and after_fresh.state == "active"


def test_with_lock_yields_session_and_raises_on_missing(
    repo: CoachingSessionRepo,
) -> None:
    session = repo.get_or_create(tenant_id="tnt", user_id="u", profile_id="p")
    with repo.with_lock(tenant_id="tnt", session_id=session.id) as locked:
        assert locked.id == session.id

    with pytest.raises(LookupError):
        with repo.with_lock(tenant_id="tnt", session_id="cs_does_not_exist"):
            pass


def test_audit_log_metadata_redacted(repo: CoachingSessionRepo) -> None:
    """R13.5 — audit metadata carries ``redacted: True`` by default."""

    session = repo.get_or_create(tenant_id="tnt", user_id="u", profile_id="p")
    repo.transition(
        tenant_id="tnt",
        session_id=session.id,
        to_state="paused",
        reason="user_pause",
    )
    with repo._connect() as db:  # type: ignore[attr-defined]
        rows = db.execute(
            "select payload_json from audit_log where action = 'coaching_session_transition'"
        ).fetchall()
    assert rows
    payload = json.loads(rows[-1]["payload_json"])
    assert payload["redacted"] is True
    assert payload["session_id"] == session.id
