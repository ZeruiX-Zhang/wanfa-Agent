"""CoachingSession aggregate, state machine, and repository.

Implements R1 (Coaching Session Aggregate) and the persistence layer that
the rest of M1 depends on. The state machine enforced here is the one
documented in :file:`.kiro/specs/expert-coaching-loop/design.md`
("CoachingSession state machine").

The module is intentionally self-contained: it does not import the
``orchestrator`` or ``reality_advisor`` so that unit tests, PBTs, and the
M0 schema validator can exercise the aggregate without spinning up the
full app.
"""

from __future__ import annotations

import contextlib
import json
import sqlite3
import threading
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator, Literal
from uuid import uuid4

from . import audit_events
from .coaching_schema import apply_coaching_schema


SessionState = Literal[
    "active",
    "awaiting_evidence",
    "awaiting_practice",
    "awaiting_experiment",
    "awaiting_review",
    "paused",
    "archived",
]

NextAction = Literal[
    "learn",
    "practice",
    "experiment",
    "review",
    "awaiting_evidence",
]

SESSION_STATES: tuple[SessionState, ...] = (
    "active",
    "awaiting_evidence",
    "awaiting_practice",
    "awaiting_experiment",
    "awaiting_review",
    "paused",
    "archived",
)


# Allowed transitions (R1.2). Mirrors the diagram in design.md.
ALLOWED_TRANSITIONS: dict[SessionState, frozenset[SessionState]] = {
    "active": frozenset(
        {
            "awaiting_evidence",
            "awaiting_practice",
            "awaiting_experiment",
            "awaiting_review",
            "paused",
            "archived",
        }
    ),
    "awaiting_evidence": frozenset({"active", "archived"}),
    "awaiting_practice": frozenset({"active", "archived"}),
    "awaiting_experiment": frozenset({"awaiting_review", "archived"}),
    "awaiting_review": frozenset({"active", "archived"}),
    "paused": frozenset({"active", "archived"}),
    "archived": frozenset(),
}


def is_allowed(from_state: SessionState, to_state: SessionState) -> bool:
    """Pure helper: check whether a transition is declared in :data:`ALLOWED_TRANSITIONS`."""

    if from_state not in ALLOWED_TRANSITIONS:
        return False
    return to_state in ALLOWED_TRANSITIONS[from_state]


class InvalidStateTransition(ValueError):
    """Raised when a caller asks for a transition not in :data:`ALLOWED_TRANSITIONS`."""

    def __init__(self, from_state: SessionState, to_state: SessionState) -> None:
        super().__init__(f"invalid transition {from_state} -> {to_state}")
        self.from_state: SessionState = from_state
        self.to_state: SessionState = to_state


class ArchivedSessionWrite(RuntimeError):
    """Raised when a write is attempted against an archived session (R1.7)."""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def _parse_iso(value: str) -> datetime:
    """Parse an ISO timestamp robustly (accepts ``Z`` suffix)."""

    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


@dataclass(frozen=True)
class CoachingSession:
    """Aggregate root for one coaching loop (R1.1).

    The aggregate references ``profile_id`` rather than embedding the full
    user profile so the existing ``user_profiles`` storage stays the
    source-of-truth and we keep the table additive.
    """

    id: str
    tenant_id: str
    user_id: str
    profile_id: str
    state: SessionState
    current_chain_id: str | None
    current_step_idx: int
    last_action: NextAction | None
    consecutive_failures: int
    created_at: str
    updated_at: str
    last_turn_at: str
    archived_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "profile_id": self.profile_id,
            "state": self.state,
            "current_chain_id": self.current_chain_id,
            "current_step_idx": self.current_step_idx,
            "last_action": self.last_action,
            "consecutive_failures": self.consecutive_failures,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_turn_at": self.last_turn_at,
            "archived_at": self.archived_at,
        }


@dataclass(frozen=True)
class StateLogEntry:
    id: str
    session_id: str
    tenant_id: str
    from_state: SessionState
    to_state: SessionState
    actor: str | None
    reason: str | None
    payload: dict[str, Any]
    created_at: str


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------


class CoachingSessionRepo:
    """Tenant-scoped repository for ``CoachingSession`` aggregates.

    Every read/write filters by ``tenant_id`` first (R12.2). The repository
    accepts an explicit DB path so tests can use an isolated SQLite file and
    the production app can wire it to ``knowledge_core.default_core_path``.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._lock = threading.RLock()
        self._ensure_schema()

    # -- connection helpers -------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _ensure_schema(self) -> None:
        with self._lock, self._connect() as db:
            apply_coaching_schema(db)

    # -- CRUD ---------------------------------------------------------------

    def get(self, *, tenant_id: str, session_id: str) -> CoachingSession | None:
        with self._lock, self._connect() as db:
            row = db.execute(
                "select * from coaching_sessions where tenant_id = ? and id = ?",
                (tenant_id, session_id),
            ).fetchone()
        return _row_to_session(row) if row else None

    def get_or_create(
        self,
        *,
        tenant_id: str,
        user_id: str,
        profile_id: str,
        session_id: str | None = None,
        actor: str | None = None,
    ) -> CoachingSession:
        """Return an existing session for ``(tenant_id, session_id)`` or create one.

        When ``session_id`` is ``None`` (R1.4) a fresh aggregate is created in
        ``state="active"`` and a ``coaching_session.created`` audit row is
        emitted. When the id is supplied but belongs to a different tenant
        the lookup returns ``None`` and we create a new session under the
        caller's tenant — callers that want strict 404 semantics should use
        :meth:`get` first.
        """

        if session_id:
            existing = self.get(tenant_id=tenant_id, session_id=session_id)
            if existing is not None:
                return existing

        now = _utc_now_iso()
        new_session = CoachingSession(
            id=_new_id("cs"),
            tenant_id=tenant_id,
            user_id=user_id,
            profile_id=profile_id,
            state="active",
            current_chain_id=None,
            current_step_idx=0,
            last_action=None,
            consecutive_failures=0,
            created_at=now,
            updated_at=now,
            last_turn_at=now,
            archived_at=None,
        )
        with self._lock, self._connect() as db:
            db.execute(
                """
                insert into coaching_sessions(
                  id, tenant_id, user_id, profile_id, state, current_chain_id,
                  current_step_idx, last_action, consecutive_failures,
                  created_at, updated_at, last_turn_at, archived_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_session.id,
                    new_session.tenant_id,
                    new_session.user_id,
                    new_session.profile_id,
                    new_session.state,
                    new_session.current_chain_id,
                    new_session.current_step_idx,
                    new_session.last_action,
                    new_session.consecutive_failures,
                    new_session.created_at,
                    new_session.updated_at,
                    new_session.last_turn_at,
                    new_session.archived_at,
                ),
            )
            self._append_audit(
                db,
                tenant_id=tenant_id,
                actor=actor or user_id,
                event_type=audit_events.COACHING_SESSION_CREATED,
                payload={
                    "session_id": new_session.id,
                    "profile_id": profile_id,
                },
            )
        return new_session

    @contextlib.contextmanager
    def with_lock(
        self,
        *,
        tenant_id: str,
        session_id: str,
    ) -> Iterator[CoachingSession]:
        """Re-entrant repository lock around a session read.

        Subsequent ``transition`` / ``touch`` calls inside the ``with``
        block share the same in-process lock so two concurrent
        ``coach/turn`` requests cannot interleave.
        """

        with self._lock:
            session = self.get(tenant_id=tenant_id, session_id=session_id)
            if session is None:
                raise LookupError(f"session not found: {session_id}")
            yield session

    # -- transitions --------------------------------------------------------

    def transition(
        self,
        *,
        tenant_id: str,
        session_id: str,
        to_state: SessionState,
        reason: str | None = None,
        actor: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> CoachingSession:
        """Move a session to ``to_state`` if the transition is declared.

        Atomic w.r.t. the repo lock: the session row, the
        ``coaching_session_state_log`` row, and the audit row are written in
        the same transaction so a partial state never escapes (R1.2, R13.1).
        """

        with self._lock, self._connect() as db:
            row = db.execute(
                "select * from coaching_sessions where tenant_id = ? and id = ?",
                (tenant_id, session_id),
            ).fetchone()
            if row is None:
                raise LookupError(f"session not found: {session_id}")
            current = _row_to_session(row)
            if current.state == "archived" and to_state != "archived":
                raise ArchivedSessionWrite(
                    f"session {session_id} is archived; new turns are rejected"
                )
            if not is_allowed(current.state, to_state):
                raise InvalidStateTransition(current.state, to_state)

            now = _utc_now_iso()
            archived_at = current.archived_at
            if to_state == "archived" and archived_at is None:
                archived_at = now

            db.execute(
                """
                update coaching_sessions set
                  state = ?, updated_at = ?, last_turn_at = ?, archived_at = ?
                where tenant_id = ? and id = ?
                """,
                (
                    to_state,
                    now,
                    now if to_state != "archived" else current.last_turn_at,
                    archived_at,
                    tenant_id,
                    session_id,
                ),
            )
            log_id = _new_id("csl")
            db.execute(
                """
                insert into coaching_session_state_log(
                  id, session_id, tenant_id, from_state, to_state,
                  actor, reason, payload_json, created_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    log_id,
                    session_id,
                    tenant_id,
                    current.state,
                    to_state,
                    actor,
                    reason,
                    json.dumps(payload or {}),
                    now,
                ),
            )
            self._append_audit(
                db,
                tenant_id=tenant_id,
                actor=actor or current.user_id,
                event_type=audit_events.COACHING_SESSION_TRANSITION,
                payload={
                    "session_id": session_id,
                    "from_state": current.state,
                    "to_state": to_state,
                    "reason": reason,
                },
            )
            if to_state == "archived":
                self._append_audit(
                    db,
                    tenant_id=tenant_id,
                    actor=actor or current.user_id,
                    event_type=audit_events.COACHING_SESSION_ARCHIVED,
                    payload={"session_id": session_id, "reason": reason},
                )

            return replace(
                current,
                state=to_state,
                updated_at=now,
                last_turn_at=now if to_state != "archived" else current.last_turn_at,
                archived_at=archived_at,
            )

    def touch_last_turn(
        self,
        *,
        tenant_id: str,
        session_id: str,
        last_action: NextAction | None = None,
    ) -> None:
        """Record that a turn happened without changing the session state.

        Useful when a coach turn loops back to the same state (e.g. repeating
        a Skill Chain step). Updates ``last_turn_at`` so :meth:`archive_idle`
        keeps the session alive (R1.6).
        """

        now = _utc_now_iso()
        with self._lock, self._connect() as db:
            db.execute(
                """
                update coaching_sessions set
                  last_turn_at = ?, updated_at = ?, last_action = coalesce(?, last_action)
                where tenant_id = ? and id = ?
                """,
                (now, now, last_action, tenant_id, session_id),
            )

    def archive_idle(
        self,
        *,
        tenant_id: str | None = None,
        idle_days: int = 30,
        now: datetime | None = None,
    ) -> int:
        """Archive sessions whose ``last_turn_at`` is older than ``idle_days``.

        Returns the number of sessions archived. A reason of
        ``"idle_timeout"`` is recorded on each transition (R1.6).
        """

        if idle_days <= 0:
            return 0
        cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=idle_days)
        cutoff_iso = cutoff.isoformat()

        with self._lock, self._connect() as db:
            params: list[Any] = [cutoff_iso]
            query = (
                "select * from coaching_sessions "
                "where state != 'archived' and last_turn_at <= ?"
            )
            if tenant_id is not None:
                query += " and tenant_id = ?"
                params.append(tenant_id)
            rows = db.execute(query, params).fetchall()

        archived = 0
        for row in rows:
            session = _row_to_session(row)
            try:
                self.transition(
                    tenant_id=session.tenant_id,
                    session_id=session.id,
                    to_state="archived",
                    reason="idle_timeout",
                    actor="system",
                )
                archived += 1
            except (InvalidStateTransition, ArchivedSessionWrite):
                continue
        return archived

    # -- audit log --------------------------------------------------------

    def list_state_log(
        self,
        *,
        tenant_id: str,
        session_id: str,
    ) -> list[StateLogEntry]:
        with self._lock, self._connect() as db:
            rows = db.execute(
                "select * from coaching_session_state_log "
                "where tenant_id = ? and session_id = ? order by created_at asc",
                (tenant_id, session_id),
            ).fetchall()
        return [_row_to_log(row) for row in rows]

    # -- helpers ----------------------------------------------------------

    def _append_audit(
        self,
        db: sqlite3.Connection,
        *,
        tenant_id: str,
        actor: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        # The shared audit_log table lives in the same DB (created by
        # ``KnowledgeCore._init_schema``). When this repo is used in tests
        # without the full knowledge_core schema, we create a minimal
        # ``audit_log`` table on demand to avoid coupling tests to the wider
        # schema.
        db.execute(
            """
            create table if not exists audit_log (
              id text primary key,
              tenant_id text not null,
              actor text not null,
              action text not null,
              subject text,
              payload_json text,
              created_at text not null
            )
            """
        )
        db.execute(
            """
            insert into audit_log(id, tenant_id, actor, action, subject, payload_json, created_at)
            values (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _new_id("audit"),
                tenant_id,
                actor,
                event_type,
                payload.get("session_id"),
                json.dumps({**payload, "redacted": True}),
                _utc_now_iso(),
            ),
        )


def _row_to_session(row: sqlite3.Row) -> CoachingSession:
    return CoachingSession(
        id=row["id"],
        tenant_id=row["tenant_id"],
        user_id=row["user_id"],
        profile_id=row["profile_id"],
        state=row["state"],
        current_chain_id=row["current_chain_id"],
        current_step_idx=row["current_step_idx"],
        last_action=row["last_action"],
        consecutive_failures=row["consecutive_failures"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        last_turn_at=row["last_turn_at"],
        archived_at=row["archived_at"],
    )


def _row_to_log(row: sqlite3.Row) -> StateLogEntry:
    return StateLogEntry(
        id=row["id"],
        session_id=row["session_id"],
        tenant_id=row["tenant_id"],
        from_state=row["from_state"],
        to_state=row["to_state"],
        actor=row["actor"],
        reason=row["reason"],
        payload=json.loads(row["payload_json"] or "{}"),
        created_at=row["created_at"],
    )



# ---------------------------------------------------------------------------
# next_action decision table (R1.5, R4.5)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SessionSnapshot:
    """Read-only inputs to :func:`decide_next_action`.

    Keeping this a plain dataclass (no ORM) makes the decision rule a pure
    function — easy to test with Hypothesis and easy to reason about when
    the orchestrator builds it (R1.5, R4.5).
    """

    insufficient_evidence: bool = False
    evidence_gathering_open: bool = False
    min_due_mastery: float | None = None
    mastery_pass_threshold: float = 0.6
    calibration_score: float = 0.0
    calibration_threshold: float = 0.6
    calibration_records_recent: int = 0
    skill_chain_step_exit_satisfied: bool = False
    skill_chain_has_next_step: bool = False
    last_experiment_unreviewed: bool = False


def decide_next_action(snap: SessionSnapshot) -> NextAction:
    """Return the next coaching action based on a session snapshot.

    The table mirrors design.md "next_action 决策规则":

    1. ``insufficient_evidence`` and an open gathering task → ``awaiting_evidence``
    2. any due concept below the pass threshold → ``practice``
    3. ``calibration_score`` below threshold *and* sparse recent calibration
       data (< 10 records) → ``practice`` (calibration practice)
    4. current chain step exit-conditions met *and* a next step exists →
       ``experiment``
    5. last experiment lacks a structured review → ``review``
    6. otherwise → ``learn``
    """

    if snap.insufficient_evidence and snap.evidence_gathering_open:
        return "awaiting_evidence"
    if (
        snap.min_due_mastery is not None
        and snap.min_due_mastery < snap.mastery_pass_threshold
    ):
        return "practice"
    if (
        snap.calibration_score < snap.calibration_threshold
        and snap.calibration_records_recent < 10
    ):
        return "practice"
    if snap.skill_chain_step_exit_satisfied and snap.skill_chain_has_next_step:
        return "experiment"
    if snap.last_experiment_unreviewed:
        return "review"
    return "learn"
