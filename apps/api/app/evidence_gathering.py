"""Active Evidence Gathering state machine + IO helpers.

This module owns the closed-loop driver for Requirement 6 (Active
Evidence Gathering): a tenant-scoped task that starts at
``INSUFFICIENT`` whenever ``work/verification`` reports
``insufficient_evidence=true`` for a coach turn, dispatches an
``expert_search`` to fill the gap, parks the candidate items in
``PENDING`` review, and only releases the linked ``DecisionLog``'s
verdict once a user explicitly approves the result.

Layered design:

* **Pure layer** (top of the file) — :class:`GatheringState` enum, the
  immutable :data:`TRANSITIONS` map, the :class:`GatheringTask` frozen
  dataclass, :func:`step` (pure transition), and :func:`verdict_allowed`
  (read-only predicate). The pure layer has no I/O and is the surface
  exercised by Property 15.

* **IO layer** (bottom of the file) — thin helpers that persist into the
  ``evidence_gathering_tasks`` table created by Task 1.1, keep the row
  in lock-step with the pure :class:`GatheringTask`, and emit one
  ``evidence_gathering.*`` audit row per accepted state change (R13.1,
  Property 21). The helpers take a ``core`` argument typed via the
  :class:`_EvidenceStore` ``Protocol`` so unit tests can inject a tiny
  in-memory fake — same pattern used by
  :func:`apps.api.app.calibration.record_prediction` and
  :func:`apps.api.app.expert_rubric.record_rubric_check`.

Design references:
- ``design.md`` § Algorithms / 7. Evidence gathering
- ``design.md`` § Data Models / 10. ``evidence_gathering_tasks``
- ``design.md`` § Audit log catalogue / ``evidence_gathering.*``
- ``design.md`` § Property 15

Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.6, 11.4, 13.1, 17.6
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Protocol
from uuid import uuid4

from . import audit_events


__all__ = [
    "GatheringState",
    "TRANSITIONS",
    "GatheringTask",
    "step",
    "verdict_allowed",
    "verdict_allowed_for_decision",
    "open_task",
    "apply_step",
    "approve_task",
    "reject_task",
    "load_task",
    "list_tasks",
    "dispatch_search",
]


# ---------------------------------------------------------------------------
# Pure layer
# ---------------------------------------------------------------------------


class GatheringState(str, Enum):
    """Lifecycle states of an Active Evidence Gathering task.

    String-valued so the enum serialises cleanly into the
    ``evidence_gathering_tasks.state`` column whose ``CHECK`` clause
    enumerates exactly these six values (see
    ``apps/api/app/coaching_schema.py``).
    """

    INSUFFICIENT = "insufficient"
    SEARCHING = "searching"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CLOSED = "closed_with_reason"


# Adjacency map — mirrors ``design.md`` § Algorithms / 7 verbatim. Frozen
# at module import time via ``frozenset`` values so callers cannot mutate
# the allowed-edges relation by accident (the dict itself is intentionally
# left as a regular ``dict`` so consumers may iterate ``.items()`` without
# importing the helper, but the inner sets are immutable).
TRANSITIONS: Mapping[GatheringState, frozenset[GatheringState]] = {
    GatheringState.INSUFFICIENT: frozenset(
        {GatheringState.SEARCHING, GatheringState.CLOSED}
    ),
    GatheringState.SEARCHING: frozenset({GatheringState.PENDING}),
    GatheringState.PENDING: frozenset(
        {
            GatheringState.APPROVED,
            GatheringState.REJECTED,
            GatheringState.SEARCHING,
            GatheringState.CLOSED,
        }
    ),
    GatheringState.APPROVED: frozenset(),
    GatheringState.REJECTED: frozenset(
        {GatheringState.SEARCHING, GatheringState.CLOSED}
    ),
    GatheringState.CLOSED: frozenset(),
}


@dataclass(frozen=True)
class GatheringTask:
    """Immutable view of one row in ``evidence_gathering_tasks``.

    The dataclass mirrors the storage columns one-to-one. ``state`` and
    ``pending_knowledge_ids`` are the only fields that change across the
    lifecycle; :func:`step` returns a new instance with ``state`` and
    ``updated_at`` advanced and never mutates the input. All other
    fields are stable across the task's lifetime.

    ``pending_knowledge_ids`` is stored as a tuple so the dataclass stays
    hashable and the frozen contract holds.
    """

    id: str
    tenant_id: str
    session_id: str | None
    coach_turn_id: str | None
    decision_log_id: str | None
    state: GatheringState
    claim: str
    pending_knowledge_ids: tuple[str, ...] = field(default_factory=tuple)
    created_at: str = ""
    updated_at: str = ""


def _legal_targets(state: GatheringState) -> frozenset[GatheringState]:
    return TRANSITIONS.get(state, frozenset())


def step(
    task: GatheringTask,
    target_state: GatheringState,
    *,
    now: datetime | None = None,
) -> GatheringTask:
    """Pure state transition.

    Returns a new :class:`GatheringTask` whose ``state`` is
    ``target_state`` whenever the edge ``task.state -> target_state`` is
    declared in :data:`TRANSITIONS`. Raises :class:`ValueError` for any
    other edge — including self-loops (e.g. ``PENDING -> PENDING``) and
    transitions out of the terminal states ``APPROVED`` and ``CLOSED``.

    Parameters
    ----------
    task:
        Current task value.
    target_state:
        The :class:`GatheringState` the caller wants to move into.
    now:
        Optional override for the ``updated_at`` timestamp; defaults to
        the current UTC instant. Tests pin this to keep assertions
        deterministic.

    Raises
    ------
    ValueError
        If ``target_state`` is not in ``TRANSITIONS[task.state]``.
    """

    if target_state not in _legal_targets(task.state):
        raise ValueError(
            f"illegal transition {task.state.value} -> {target_state.value}"
        )
    updated_at = (now or datetime.now(timezone.utc)).isoformat()
    return replace(task, state=target_state, updated_at=updated_at)


def verdict_allowed(task: GatheringTask) -> bool:
    """Return ``True`` iff the task has reached :attr:`GatheringState.APPROVED`.

    R6.3 / R11.4: while any pending evidence remains, the linked
    ``DecisionLog.verdict`` must stay empty. Only ``APPROVED`` releases
    the verdict; ``REJECTED`` keeps the loop open (R6.6) and ``CLOSED``
    is an explicit user-documented abandonment that still does not
    release a verdict.
    """

    return task.state == GatheringState.APPROVED


# ---------------------------------------------------------------------------
# IO layer
# ---------------------------------------------------------------------------


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str = "evg") -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


# Map ``GatheringState`` → audit ``event_type`` constants from Task 1.6
# so :func:`apply_step` emits the right ``evidence_gathering.*`` row for
# each accepted transition. ``INSUFFICIENT`` is paired with
# ``EVIDENCE_GATHERING_OPENED`` because the only context an
# ``INSUFFICIENT`` transition could appear in is :func:`open_task`'s
# initial insert; we never expose a path that *re-enters* ``INSUFFICIENT``.
_STATE_TO_AUDIT: Mapping[GatheringState, str] = {
    GatheringState.INSUFFICIENT: audit_events.EVIDENCE_GATHERING_OPENED,
    GatheringState.SEARCHING: audit_events.EVIDENCE_GATHERING_DISPATCHED,
    GatheringState.PENDING: audit_events.EVIDENCE_GATHERING_PENDING,
    GatheringState.APPROVED: audit_events.EVIDENCE_GATHERING_APPROVED,
    GatheringState.REJECTED: audit_events.EVIDENCE_GATHERING_REJECTED,
    GatheringState.CLOSED: audit_events.EVIDENCE_GATHERING_CLOSED,
}


class _EvidenceStore(Protocol):
    """Minimum surface :func:`open_task` / :func:`apply_step` need.

    The production sink is :class:`apps.api.app.knowledge_core.KnowledgeCore`,
    which exposes ``_lock``, ``_connect``, and ``_record_audit`` with the
    exact shapes used here. Tests inject a small in-memory fake that
    satisfies the same protocol so the helpers stay decoupled from the
    full ``KnowledgeCore`` schema (mirrors
    :func:`apps.api.app.calibration.record_prediction`).
    """

    _lock: Any  # ``threading.RLock`` — context-manager-able.

    def _connect(self) -> Any: ...

    def _record_audit(
        self,
        *,
        tenant_id: str,
        actor: str,
        action: str,
        subject: str | None,
        payload: dict[str, Any] | None,
    ) -> str: ...


def _emit_evidence_audit(
    *,
    core: _EvidenceStore,
    tenant_id: str,
    actor: str,
    task: GatheringTask,
    extra: dict[str, Any] | None = None,
) -> str | None:
    """Best-effort ``evidence_gathering.*`` audit emission (R13.1)."""

    payload: dict[str, Any] = {
        "task_id": task.id,
        "state": task.state.value,
    }
    if task.session_id is not None:
        payload["session_id"] = task.session_id
    if task.coach_turn_id is not None:
        payload["coach_turn_id"] = task.coach_turn_id
    if task.decision_log_id is not None:
        payload["decision_log_id"] = task.decision_log_id
    if extra:
        payload.update(extra)
    action = _STATE_TO_AUDIT[task.state]
    try:
        return core._record_audit(
            tenant_id=tenant_id,
            actor=actor,
            action=action,
            subject=task.id,
            payload=payload,
        )
    except Exception:
        # Audit is best-effort — never block a state change on logging.
        return None


def _row_to_task(row: Any) -> GatheringTask:
    """Hydrate a ``GatheringTask`` from a ``sqlite3.Row``-shaped result."""

    pending_raw = row["pending_knowledge_ids_json"]
    try:
        pending_list = json.loads(pending_raw) if pending_raw else []
    except (TypeError, ValueError):
        pending_list = []
    if not isinstance(pending_list, list):
        pending_list = []
    return GatheringTask(
        id=row["id"],
        tenant_id=row["tenant_id"],
        session_id=row["session_id"],
        coach_turn_id=row["coach_turn_id"],
        decision_log_id=row["decision_log_id"],
        state=GatheringState(row["state"]),
        claim=row["claim"],
        pending_knowledge_ids=tuple(str(x) for x in pending_list),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def open_task(
    *,
    core: _EvidenceStore,
    tenant_id: str,
    claim: str,
    session_id: str | None = None,
    coach_turn_id: str | None = None,
    decision_log_id: str | None = None,
    pending_knowledge_ids: tuple[str, ...] | list[str] = (),
    actor: str = "system",
    now: datetime | None = None,
) -> GatheringTask:
    """Insert a new ``INSUFFICIENT`` task and emit ``evidence_gathering.opened``.

    R6.1: every coach turn whose verifier reports
    ``insufficient_evidence=true`` opens exactly one task. The row is
    inserted with ``state='insufficient'`` and the supplied ``claim`` /
    link columns. A single ``evidence_gathering.opened`` audit row is
    emitted with the documented payload keys (R13.1).

    Raises
    ------
    ValueError
        If ``claim`` is empty.
    """

    if not claim or not claim.strip():
        raise ValueError("claim must be non-empty")

    task_id = _new_id()
    created_at = (now or datetime.now(timezone.utc)).isoformat()
    pending = tuple(str(x) for x in pending_knowledge_ids)

    with core._lock, core._connect() as db:
        db.execute(
            """
            insert into evidence_gathering_tasks(
              id, tenant_id, session_id, coach_turn_id, decision_log_id,
              state, claim, pending_knowledge_ids_json, created_at, updated_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                tenant_id,
                session_id,
                coach_turn_id,
                decision_log_id,
                GatheringState.INSUFFICIENT.value,
                claim,
                json.dumps(list(pending), ensure_ascii=False),
                created_at,
                created_at,
            ),
        )

    task = GatheringTask(
        id=task_id,
        tenant_id=tenant_id,
        session_id=session_id,
        coach_turn_id=coach_turn_id,
        decision_log_id=decision_log_id,
        state=GatheringState.INSUFFICIENT,
        claim=claim,
        pending_knowledge_ids=pending,
        created_at=created_at,
        updated_at=created_at,
    )

    _emit_evidence_audit(
        core=core,
        tenant_id=tenant_id,
        actor=actor,
        task=task,
        extra={"claim": claim},
    )
    return task


def apply_step(
    *,
    core: _EvidenceStore,
    task: GatheringTask,
    target_state: GatheringState,
    pending_knowledge_ids: tuple[str, ...] | list[str] | None = None,
    actor: str = "system",
    now: datetime | None = None,
) -> GatheringTask:
    """Persist a transition computed by :func:`step` and emit one audit row.

    The pure :func:`step` is invoked first — illegal transitions raise
    ``ValueError`` *before* any DB write, mirroring the design's
    no-side-effects-on-reject contract (Property 21).

    ``pending_knowledge_ids`` lets callers refresh the linked candidate
    set on the same write (e.g. ``SEARCHING -> PENDING`` after
    ``expert_search`` returned hits per R6.2). When omitted, the prior
    value is preserved verbatim.
    """

    next_task = step(task, target_state, now=now)
    if pending_knowledge_ids is not None:
        next_task = replace(
            next_task,
            pending_knowledge_ids=tuple(str(x) for x in pending_knowledge_ids),
        )

    with core._lock, core._connect() as db:
        db.execute(
            """
            update evidence_gathering_tasks
               set state = ?,
                   pending_knowledge_ids_json = ?,
                   updated_at = ?
             where tenant_id = ? and id = ?
            """,
            (
                next_task.state.value,
                json.dumps(list(next_task.pending_knowledge_ids), ensure_ascii=False),
                next_task.updated_at,
                next_task.tenant_id,
                next_task.id,
            ),
        )

    _emit_evidence_audit(
        core=core,
        tenant_id=next_task.tenant_id,
        actor=actor,
        task=next_task,
        extra={"from_state": task.state.value},
    )
    return next_task


def load_task(
    *,
    core: _EvidenceStore,
    tenant_id: str,
    task_id: str,
) -> GatheringTask | None:
    """Tenant-scoped fetch by id; ``None`` when the row does not exist."""

    with core._lock, core._connect() as db:
        row = db.execute(
            """
            select id, tenant_id, session_id, coach_turn_id, decision_log_id,
                   state, claim, pending_knowledge_ids_json, created_at, updated_at
              from evidence_gathering_tasks
             where tenant_id = ? and id = ?
            """,
            (tenant_id, task_id),
        ).fetchone()
    return _row_to_task(row) if row is not None else None


def list_tasks(
    *,
    core: _EvidenceStore,
    tenant_id: str,
    decision_log_id: str | None = None,
) -> list[GatheringTask]:
    """List tasks for ``tenant_id`` ordered by creation time.

    When ``decision_log_id`` is supplied, only tasks linked to that
    decision are returned — used by the orchestrator to decide whether
    any pending work still blocks a verdict (R6.3 / R11.4).
    """

    sql = """
        select id, tenant_id, session_id, coach_turn_id, decision_log_id,
               state, claim, pending_knowledge_ids_json, created_at, updated_at
          from evidence_gathering_tasks
         where tenant_id = ?
    """
    params: list[Any] = [tenant_id]
    if decision_log_id is not None:
        sql += " and decision_log_id = ?"
        params.append(decision_log_id)
    sql += " order by created_at asc, id asc"

    with core._lock, core._connect() as db:
        rows = db.execute(sql, params).fetchall()
    return [_row_to_task(r) for r in rows]


# ---------------------------------------------------------------------------
# Decision-log gate helpers (Task 3.14, R6.3, R6.4, R6.6, R11.4)
# ---------------------------------------------------------------------------


def verdict_allowed_for_decision(
    *,
    core: _EvidenceStore,
    tenant_id: str,
    decision_log_id: str,
) -> bool:
    """Tenant-scoped predicate: may a verdict be issued for this decision?

    R6.3 / R11.4: a ``DecisionMemo`` verdict MUST stay empty while *any*
    Active-Evidence-Gathering task linked to ``decision_log_id`` is in a
    non-terminal-approved state.

    The predicate considers all tasks linked to the decision and returns
    ``True`` only when every task has reached
    :attr:`GatheringState.APPROVED`. If no tasks exist for the decision
    we also return ``True`` — the absence of an open gathering loop is
    the default state for plain decisions where ``insufficient_evidence``
    never fired.

    R6.6: ``REJECTED`` and ``CLOSED`` keep the loop **closed-but-not
    -approved**, so the verdict stays blocked until the user approves at
    least one round of pending evidence (or explicitly closes the loop
    *and* opens a new approved task — design.md "Endpoint × mode"
    table). This mirrors :func:`verdict_allowed` for a single task.
    """

    tasks = list_tasks(
        core=core, tenant_id=tenant_id, decision_log_id=decision_log_id
    )
    if not tasks:
        return True
    return all(verdict_allowed(task) for task in tasks)


def approve_task(
    *,
    core: _EvidenceStore,
    task: GatheringTask,
    actor: str = "user",
    now: datetime | None = None,
) -> GatheringTask:
    """User-driven approval (R6.4).

    Convenience wrapper around :func:`apply_step` that drives a
    ``PENDING`` task into :attr:`GatheringState.APPROVED`. Emits the
    ``evidence_gathering.approved`` audit row in the same write so the
    state log captures the user's accept action (R13.1, Property 21).

    Raises :class:`ValueError` (via :func:`step`) if ``task`` is not in
    :attr:`GatheringState.PENDING` — the only legal predecessor of
    APPROVED per :data:`TRANSITIONS`.
    """

    return apply_step(
        core=core,
        task=task,
        target_state=GatheringState.APPROVED,
        actor=actor,
        now=now,
    )


def reject_task(
    *,
    core: _EvidenceStore,
    task: GatheringTask,
    actor: str = "user",
    now: datetime | None = None,
) -> GatheringTask:
    """User-driven rejection (R6.6).

    R6.6 keeps the loop **open** after a rejection: the linked
    ``DecisionLog.verdict`` MUST stay empty until at least one approved
    item exists (or the user explicitly closes the loop with a
    documented reason). Concretely this transitions ``PENDING ->
    REJECTED``. Re-opening the search is a separate
    :func:`apply_step` call (REJECTED → SEARCHING) once the user
    triggers another round.
    """

    return apply_step(
        core=core,
        task=task,
        target_state=GatheringState.REJECTED,
        actor=actor,
        now=now,
    )


# ---------------------------------------------------------------------------
# Active Evidence Gathering — wired dispatch (Task 3.13, R6.1, R6.2)
# ---------------------------------------------------------------------------


class _PendingSink(Protocol):
    """The minimal :mod:`apps.api.storage` surface :func:`dispatch_search`
    needs to persist ``pending_knowledge`` rows.

    Production callers pass :class:`apps.api.storage.RealityStorage`,
    whose ``save_pending`` already (a) upserts into the
    ``pending_knowledge`` ``records`` table tenant-scoped and (b) emits
    the historical ``pending_knowledge.created`` audit row. Tests inject
    a tiny in-memory fake that satisfies the same protocol so this
    module stays decoupled from the wider storage layer.
    """

    def save_pending(self, record: Any) -> Any: ...


def _build_pending_record(
    *,
    tenant_id: str,
    task_id: str,
    actor: str,
    result: Mapping[str, Any],
    coach_turn_id: str | None,
    decision_log_id: str | None,
    session_id: str | None,
) -> Any:
    """Build a :class:`PendingKnowledgeRecord` with the documented
    Active-Evidence-Gathering defaults.

    Per R6.2 every result MUST land with:

    * ``status="pending_review"`` (cross-cutting R11.1).
    * ``formal_knowledge_write=False`` (cross-cutting R11.2).
    * ``external=True`` and ``trust_level="untrusted"`` (R6.2 + R15
      defaults; expert search results come from the public web).
    * tenant scoping derived from the originating
      :class:`GatheringTask`.

    Linking back to the originating coach turn / decision happens via
    ``evidence_gathering_tasks.pending_knowledge_ids_json`` (the inverse
    direction); we additionally tag the pending record with the task /
    turn / decision ids so a UI listing the pending queue can group by
    the originating context without a join.
    """

    # Imported lazily to avoid a circular import: ``schemas`` pulls in
    # the broader pydantic graph that some thin import paths into this
    # module want to keep slim.
    from ..schemas import PendingKnowledgeRecord, new_id, utc_now

    title = str(result.get("title") or "").strip() or "(untitled)"
    snippet = str(result.get("snippet") or "").strip()
    body = f"{title}\n\n{snippet}" if snippet else title

    tags = ["evidence_gathering", f"task:{task_id}"]
    if coach_turn_id:
        tags.append(f"coach_turn:{coach_turn_id}")
    if decision_log_id:
        tags.append(f"decision_log:{decision_log_id}")
    if session_id:
        tags.append(f"session:{session_id}")
    src_id = result.get("source_id")
    if src_id:
        tags.append(f"source:{src_id}")

    return PendingKnowledgeRecord(
        id=new_id("pending"),
        content=body,
        origin="expert_search",
        source_uri=result.get("url"),
        tags=tags,
        created_by=actor,
        status="pending_review",
        review_required=True,
        formal_knowledge_write=False,
        external=True,
        trust_level="untrusted",
        tenant_id=tenant_id,
        created_at=utc_now(),
    )


def dispatch_search(
    *,
    core: _EvidenceStore,
    storage: _PendingSink,
    task: GatheringTask,
    actor: str = "system",
    language: str = "en",
    sources: list[str] | None = None,
    max_pending: int | None = None,
    search_runner: Any = None,
    now: datetime | None = None,
) -> tuple[GatheringTask, list[Any]]:
    """Wire ``expert_search`` for Active Evidence Gathering (R6.1, R6.2).

    Closed-loop driver:

    1. Transition the supplied ``task`` from ``INSUFFICIENT`` to
       ``SEARCHING`` (one ``evidence_gathering.dispatched`` audit row).
    2. Invoke ``expert_search`` seeded with ``task.claim`` and the
       coach-turn / decision-log linkage so the run trace records the
       coaching context.
    3. Persist each returned result to ``pending_knowledge`` via
       ``storage.save_pending`` with the R6.2 defaults
       (``status="pending_review"``, ``formal_knowledge_write=False``,
       ``external=True``, ``trust_level="untrusted"``,
       ``tenant_id=task.tenant_id``).
    4. Transition the task from ``SEARCHING`` to ``PENDING`` and
       refresh ``pending_knowledge_ids`` with the ids of the saved
       records (one ``evidence_gathering.pending`` audit row).

    Parameters
    ----------
    core:
        Sink that owns the ``evidence_gathering_tasks`` table —
        typically :class:`KnowledgeCore`.
    storage:
        Sink that owns the ``pending_knowledge`` table — typically
        :class:`RealityStorage`.
    task:
        A live :class:`GatheringTask` in :attr:`GatheringState.INSUFFICIENT`
        (returned by :func:`open_task`).
    actor:
        Audit actor; defaults to ``"system"`` because the loop is
        triggered by the orchestrator without a direct user click.
    language:
        Forwarded to :func:`expert_search`.
    sources:
        Optional explicit source allow-list; ``None`` lets the strategy
        engine pick.
    max_pending:
        Optional cap on the number of results to persist. ``None``
        keeps all results from the search call.
    search_runner:
        Optional injected callable with the same shape as
        :func:`apps.api.app.expert_search.expert_search`. Tests inject a
        deterministic fake so the dispatch loop is exercised without
        hitting the real search pipeline.
    now:
        Optional pinned UTC timestamp for the state transitions.

    Returns
    -------
    ``(task, pending_records)`` — the freshly persisted task in
    :attr:`GatheringState.PENDING` and the list of
    :class:`PendingKnowledgeRecord` rows saved in this dispatch.

    Raises
    ------
    ValueError
        If ``task.state`` is not :attr:`GatheringState.INSUFFICIENT` —
        :func:`step` will reject any other starting state via the pure
        adjacency check.
    """

    if search_runner is None:
        from .expert_search import expert_search as search_runner  # type: ignore[assignment]

    # 1) INSUFFICIENT → SEARCHING (audit ``evidence_gathering.dispatched``).
    searching_task = apply_step(
        core=core,
        task=task,
        target_state=GatheringState.SEARCHING,
        actor=actor,
        now=now,
    )

    # 2) Seeded expert_search call. The runner is allowed to be either a
    # module-level function (production) or a deterministic fake (tests);
    # either way it MUST accept the documented kwargs below.
    search_response = search_runner(
        tenant_id=task.tenant_id,
        query=task.claim,
        language=language,
        sources=sources,
        auto_absorb=False,            # R11.1: pending review only.
        actor=actor,
        seed_claim=task.claim,        # R6.1: seed with the claim.
        session_id=task.session_id,
        coach_turn_id=task.coach_turn_id,
        decision_log_id=task.decision_log_id,
        evidence_gathering_task_id=task.id,
    )

    raw_results = list(search_response.get("results") or [])
    if max_pending is not None and max_pending >= 0:
        raw_results = raw_results[:max_pending]

    # 3) Persist each result as a pending_knowledge row tied to the
    # originating coach turn / decision (R6.2 + R11.1).
    pending_records: list[Any] = []
    for result in raw_results:
        record = _build_pending_record(
            tenant_id=task.tenant_id,
            task_id=task.id,
            actor=actor,
            result=result,
            coach_turn_id=task.coach_turn_id,
            decision_log_id=task.decision_log_id,
            session_id=task.session_id,
        )
        saved = storage.save_pending(record)
        pending_records.append(saved)

    # 4) SEARCHING → PENDING with the linked pending ids merged in.
    merged_ids = list(task.pending_knowledge_ids) + [
        rec.id for rec in pending_records
    ]
    pending_task = apply_step(
        core=core,
        task=searching_task,
        target_state=GatheringState.PENDING,
        pending_knowledge_ids=tuple(merged_ids),
        actor=actor,
        now=now,
    )

    return pending_task, pending_records
