"""Property-based test for the CoachingSession round-trip persistence.

Feature: expert-coaching-loop, Property 2: Coaching session round-trip persistence
Validates: Requirements 1.8
"""

from __future__ import annotations

from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from apps.api.app.coaching_session import (
    ALLOWED_TRANSITIONS,
    CoachingSession,
    CoachingSessionRepo,
    InvalidStateTransition,
)


@pytest.fixture(scope="module")
def repo(tmp_path_factory: pytest.TempPathFactory) -> CoachingSessionRepo:
    path: Path = tmp_path_factory.mktemp("coach-pbt") / "coach.sqlite3"
    return CoachingSessionRepo(path=path)


# A small alphabet keeps Hypothesis fast and the SQLite tables small.
_state_strat = st.sampled_from(list(ALLOWED_TRANSITIONS.keys()))


def _walk(repo: CoachingSessionRepo, session_id: str, tenant: str, steps: list[str]) -> CoachingSession:
    """Best-effort transition walk; illegal transitions are silently skipped."""

    last = repo.get(tenant_id=tenant, session_id=session_id)
    assert last is not None
    for to_state in steps:
        try:
            last = repo.transition(
                tenant_id=tenant,
                session_id=session_id,
                to_state=to_state,
                reason="pbt-walk",
            )
        except InvalidStateTransition:
            continue
        if last.state == "archived":
            break
    assert last is not None
    return last


@settings(
    max_examples=80,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(steps=st.lists(_state_strat, min_size=0, max_size=8))
def test_property_2_session_round_trip(
    repo: CoachingSessionRepo,
    steps: list[str],
) -> None:
    """Persisting and reloading the aggregate yields an equal CoachingSession.

    The walk applies a random sequence of transitions, then we reload the
    session and assert structural equality across every persisted field.
    """

    session = repo.get_or_create(
        tenant_id="pbt-tnt", user_id="pbt-user", profile_id="pbt-profile"
    )
    final = _walk(repo, session.id, "pbt-tnt", steps)
    reloaded = repo.get(tenant_id="pbt-tnt", session_id=session.id)
    assert reloaded is not None
    assert reloaded == final


@settings(max_examples=50, deadline=None,
          suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(steps=st.lists(_state_strat, min_size=0, max_size=8))
def test_property_2_state_log_records_every_accepted_transition(
    repo: CoachingSessionRepo,
    steps: list[str],
) -> None:
    """Every accepted transition appends exactly one state-log entry."""

    session = repo.get_or_create(
        tenant_id="pbt-tnt2", user_id="u", profile_id="p"
    )

    # Count how many transitions are actually accepted by replaying.
    accepted = 0
    sim_state = "active"
    for to_state in steps:
        if to_state in ALLOWED_TRANSITIONS[sim_state]:
            accepted += 1
            sim_state = to_state
            if sim_state == "archived":
                break

    _walk(repo, session.id, "pbt-tnt2", steps)
    log = repo.list_state_log(tenant_id="pbt-tnt2", session_id=session.id)
    assert len(log) == accepted
