"""Pure calibration primitives + IO helpers for the expert-coaching-loop.

The pure layer (top of the file) exposes two frozen dataclasses
(:class:`CalibrationBin`, :class:`CalibrationRecord`) and four pure
functions (:func:`brier_score`, :func:`log_loss`,
:func:`calibration_curve`, :func:`calibration_score`).

The IO layer (bottom of the file) adds three thin helpers that persist
into the ``calibration_records`` table and emit ``calibration_record``
audit rows (R4.2, R13.3):

* :func:`record_prediction` — persist the predicted-outcome row before any
  decision log is committed.
* :func:`record_outcome` — fill in the binary outcome at review time and
  compute Brier / Log loss when ``binary_resolved=True``.
* :func:`list_calibration_records` — tenant-scoped fetch helper used by
  the dashboard endpoints (Task 5.2) and the unit tests below.

The helpers intentionally take a ``core`` argument typed via a
:class:`_CalibrationStore` ``Protocol`` so unit tests can inject a fake
sink — same pattern as :func:`apps.api.app.expert_rubric.record_rubric_check`.

Design references:
- ``design.md`` § Algorithms / 3. Brier / Log loss / Calibration curve
- ``design.md`` § Data Models / 5. ``calibration_records``
- ``design.md`` § Audit log catalogue / ``calibration_record``
- ``design.md`` § Properties 12, 13, 14

Validates: Requirements 4.2, 4.3, 4.4, 13.3, 17.2, 17.5
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Protocol, Sequence
from uuid import uuid4

from . import audit_events

__all__ = [
    "CalibrationBin",
    "CalibrationRecord",
    "brier_score",
    "log_loss",
    "calibration_curve",
    "calibration_score",
    "record_prediction",
    "record_outcome",
    "list_calibration_records",
]


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CalibrationBin:
    """One decile bin of the calibration curve.

    Field order matches the constructor calls in ``design.md`` § Algorithms
    / 3 so positional construction stays faithful to the specification:
    ``CalibrationBin(lo, hi, count, mean_pred, empirical_freq)``.

    Invariants (see Property 13):

    * ``0.0 <= lo < hi <= 1.0`` for non-last bins; ``hi == 1.0`` for the
      last bin which is closed on the right so that ``p == 1.0`` lands.
    * ``count >= 0``.
    * ``0.0 <= empirical_freq <= 1.0``.
    * ``lo <= mean_pred <= hi`` whenever ``count > 0``; for empty bins
      the helper sets ``mean_pred = lo`` and ``empirical_freq = 0.0``.
    """

    lo: float
    hi: float
    count: int
    mean_pred: float
    empirical_freq: float


@dataclass(frozen=True)
class CalibrationRecord:
    """A single calibration row (mirrors ``calibration_records`` columns).

    Storage is owned by Task 3.8; this dataclass is the pure-Python view
    that :func:`calibration_score` consumes. ``brier_score`` and
    ``log_loss`` are ``None`` for unresolved reviews (R4.6) so that they
    are excluded from the calibration curve and aggregate score.

    The five trailing fields (``id``, ``tenant_id``, ``decision_log_id``,
    ``created_at``, ``reviewed_at``) default to ``None`` so the original
    six positional fields stay backwards-compatible with the pure PBT
    tests that pre-date Task 3.8.
    """

    predicted_outcome: str
    confidence: float
    binary_resolved: bool
    binary_value: int | None
    brier_score: float | None
    log_loss: float | None
    id: str | None = None
    tenant_id: str | None = None
    decision_log_id: str | None = None
    created_at: str | None = None
    reviewed_at: str | None = None


# ---------------------------------------------------------------------------
# Brier score (R4.2, R17.2 / Property 12)
# ---------------------------------------------------------------------------


def brier_score(preds: Sequence[float], outcomes: Sequence[int]) -> float:
    """Mean squared error between predictions and binary outcomes.

    Bounded in ``[0.0, 1.0]`` whenever ``preds[i] in [0, 1]`` and
    ``outcomes[i] in {0, 1}``. Returns ``0.0`` exactly when every
    ``preds[i] in {0, 1}`` matches its corresponding ``outcomes[i]``.

    Raises
    ------
    ValueError
        If ``preds`` and ``outcomes`` differ in length, or if either is
        empty. ``brier_score`` over an empty sample is undefined.
    """

    if len(preds) != len(outcomes):
        raise ValueError(
            "preds and outcomes must have equal length; "
            f"got {len(preds)} and {len(outcomes)}"
        )
    if not preds:
        raise ValueError("preds must be non-empty")

    total = 0.0
    for p, o in zip(preds, outcomes):
        diff = float(p) - float(o)
        total += diff * diff
    return total / len(preds)


# ---------------------------------------------------------------------------
# Log loss (R4.2)
# ---------------------------------------------------------------------------


def log_loss(
    preds: Sequence[float],
    outcomes: Sequence[int],
    eps: float = 1e-9,
) -> float:
    """Mean binary cross-entropy over ``preds`` against ``outcomes``.

    Each prediction is clipped to ``[eps, 1 - eps]`` so that ``log(0)``
    cannot blow up. Always non-negative.

    Raises
    ------
    ValueError
        If lengths differ, ``preds`` is empty, or ``eps`` is not in
        ``(0, 0.5)``.
    """

    if len(preds) != len(outcomes):
        raise ValueError(
            "preds and outcomes must have equal length; "
            f"got {len(preds)} and {len(outcomes)}"
        )
    if not preds:
        raise ValueError("preds must be non-empty")
    if not (0.0 < eps < 0.5):
        raise ValueError(f"eps must be in (0, 0.5); got {eps!r}")

    total = 0.0
    upper = 1.0 - eps
    for p, o in zip(preds, outcomes):
        p_c = min(upper, max(eps, float(p)))
        total += -(o * math.log(p_c) + (1 - o) * math.log(1 - p_c))
    return total / len(preds)


# ---------------------------------------------------------------------------
# Calibration curve (R4.3, R17.5 / Property 13)
# ---------------------------------------------------------------------------


def calibration_curve(
    preds: Sequence[float],
    outcomes: Sequence[int],
    bins: int = 10,
) -> list[CalibrationBin]:
    """Bin predictions into ``bins`` equal-width deciles on ``[0, 1]``.

    The last bin is closed on the right so that ``p == 1.0`` is counted
    in bin ``bins - 1`` rather than dropped (per ``design.md``):

    .. code-block:: text

        bin i  = [lo, hi)             for i in [0, bins-1)
        bin -1 = [lo, hi]             includes p == 1.0

    Empty bins are still emitted with ``count = 0`` so callers can index
    by bin number without checking presence.

    Invariants (Property 13):

    * ``sum(b.count for b in result) == len(preds)``
    * ``0.0 <= b.empirical_freq <= 1.0`` for every bin
    * ``b.lo <= b.mean_pred <= b.hi`` whenever ``b.count > 0``

    Raises
    ------
    ValueError
        If lengths differ or ``bins`` is not a positive integer.
    """

    if len(preds) != len(outcomes):
        raise ValueError(
            "preds and outcomes must have equal length; "
            f"got {len(preds)} and {len(outcomes)}"
        )
    if bins < 1:
        raise ValueError(f"bins must be >= 1; got {bins!r}")

    edges = [i / bins for i in range(bins + 1)]
    out: list[CalibrationBin] = []

    for i in range(bins):
        lo, hi = edges[i], edges[i + 1]
        is_last = i == bins - 1
        in_bin = [
            (float(p), int(o))
            for p, o in zip(preds, outcomes)
            if (lo <= p < hi) or (is_last and p == 1.0)
        ]
        if not in_bin:
            out.append(
                CalibrationBin(lo=lo, hi=hi, count=0, mean_pred=lo, empirical_freq=0.0)
            )
            continue

        ps = [p for p, _ in in_bin]
        os_ = [o for _, o in in_bin]
        out.append(
            CalibrationBin(
                lo=lo,
                hi=hi,
                count=len(in_bin),
                mean_pred=sum(ps) / len(ps),
                empirical_freq=sum(os_) / len(in_bin),
            )
        )

    return out


# ---------------------------------------------------------------------------
# Calibration score (R4.4 / Property 14)
# ---------------------------------------------------------------------------


def calibration_score(
    records: Iterable[CalibrationRecord],
    window: int = 50,
) -> float:
    """Aggregate calibration performance over the last ``window`` reviewed records.

    Defined as ``max(0, min(1, 1 - mean(brier_score)))`` over the most
    recent ``window`` records whose ``brier_score`` is not ``None``
    (i.e. resolved reviews; R4.6 keeps unresolved ones nullable).

    Returns ``0.0`` when no resolved record exists — this is the cold
    start that biases ``next_action`` toward ``practice`` until enough
    decisions have been reviewed (see ``design.md`` Open Questions).

    Raises
    ------
    ValueError
        If ``window`` is not a positive integer.
    """

    if window < 1:
        raise ValueError(f"window must be >= 1; got {window!r}")

    resolved = [r for r in records if r.brier_score is not None]
    if not resolved:
        return 0.0

    tail = resolved[-window:]
    mean_brier = sum(r.brier_score for r in tail) / len(tail)
    return max(0.0, min(1.0, 1.0 - mean_brier))


# ---------------------------------------------------------------------------
# IO helpers (Task 3.8) — persist into ``calibration_records`` and emit
# ``calibration_record`` audit rows (R4.2, R13.3).
# ---------------------------------------------------------------------------


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str = "calr") -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


class _CalibrationStore(Protocol):
    """Minimum surface :func:`record_prediction` / :func:`record_outcome` need.

    The production sink is :class:`apps.api.app.knowledge_core.KnowledgeCore`,
    which already exposes ``_lock``, ``_connect``, and ``_record_audit`` with
    the exact shapes described below. Tests inject a small in-memory fake
    that satisfies the same protocol so the helpers stay decoupled from the
    full ``KnowledgeCore`` schema (mirrors :func:`expert_rubric.record_rubric_check`).
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


def _emit_calibration_audit(
    *,
    core: _CalibrationStore,
    tenant_id: str,
    actor: str,
    decision_log_id: str,
    payload: dict[str, Any],
) -> str | None:
    """Best-effort ``calibration_record`` audit emission (R13.3)."""

    try:
        return core._record_audit(
            tenant_id=tenant_id,
            actor=actor,
            action=audit_events.CALIBRATION_RECORD,
            subject=decision_log_id,
            payload=payload,
        )
    except Exception:
        # Audit is best-effort — never block the calibration write on logging.
        return None


def record_prediction(
    *,
    core: _CalibrationStore,
    tenant_id: str,
    decision_log_id: str,
    predicted_outcome: str,
    confidence: float,
    actor: str = "user",
    now: datetime | None = None,
) -> CalibrationRecord:
    """Persist the predicted outcome of a decision into ``calibration_records``.

    The row is written with ``binary_resolved=0``, ``binary_value=NULL``,
    ``brier_score=NULL``, ``log_loss=NULL``, and ``reviewed_at=NULL``;
    those columns are filled in later by :func:`record_outcome`.

    A single ``calibration_record`` audit row is emitted with the
    documented payload keys (R13.3, design audit catalogue):

    .. code-block:: python

        {
          "decision_log_id": <str>,
          "confidence": <float>,
          "predicted_outcome": <str>,
          "source": "prediction",
        }

    Raises
    ------
    ValueError
        If ``predicted_outcome`` is empty (R4.1) or ``confidence`` is
        outside ``[0, 1]``.
    """

    if not predicted_outcome or not predicted_outcome.strip():
        raise ValueError("predicted_outcome must be non-empty")
    if not (0.0 <= confidence <= 1.0):
        raise ValueError(f"confidence must be in [0.0, 1.0]; got {confidence!r}")

    record_id = _new_id()
    created_at = (now or datetime.now(timezone.utc)).isoformat()

    with core._lock, core._connect() as db:
        db.execute(
            """
            insert into calibration_records(
              id, tenant_id, decision_log_id, predicted_outcome, confidence,
              binary_resolved, binary_value, brier_score, log_loss,
              created_at, reviewed_at
            ) values (?, ?, ?, ?, ?, 0, NULL, NULL, NULL, ?, NULL)
            """,
            (
                record_id,
                tenant_id,
                decision_log_id,
                predicted_outcome,
                float(confidence),
                created_at,
            ),
        )

    _emit_calibration_audit(
        core=core,
        tenant_id=tenant_id,
        actor=actor,
        decision_log_id=decision_log_id,
        payload={
            "decision_log_id": decision_log_id,
            "confidence": float(confidence),
            "predicted_outcome": predicted_outcome,
            "source": "prediction",
        },
    )

    return CalibrationRecord(
        predicted_outcome=predicted_outcome,
        confidence=float(confidence),
        binary_resolved=False,
        binary_value=None,
        brier_score=None,
        log_loss=None,
        id=record_id,
        tenant_id=tenant_id,
        decision_log_id=decision_log_id,
        created_at=created_at,
        reviewed_at=None,
    )


def record_outcome(
    *,
    core: _CalibrationStore,
    tenant_id: str,
    decision_log_id: str,
    binary_resolved: bool,
    binary_value: int | None = None,
    actor: str = "user",
    now: datetime | None = None,
) -> CalibrationRecord:
    """Fill in the resolved outcome of a previously-recorded prediction.

    Looks up the existing prediction row by ``(tenant_id, decision_log_id)``.
    When ``binary_resolved=True`` the helper computes ``brier_score`` and
    ``log_loss`` from the stored ``confidence`` and the supplied
    ``binary_value`` ∈ {0, 1}. When ``binary_resolved=False`` (R4.6 — outcome
    not resolvable to a binary) ``brier_score`` and ``log_loss`` remain
    ``NULL`` so the row is excluded from the calibration curve.

    A ``calibration_record`` audit row is emitted with payload:

    .. code-block:: python

        {
          "decision_log_id": <str>,
          "brier_score": <float | None>,
          "log_loss":    <float | None>,
          "source": "outcome",
        }

    Raises
    ------
    LookupError
        If no prediction row exists for ``(tenant_id, decision_log_id)``.
    ValueError
        If ``binary_resolved=True`` but ``binary_value`` is not in {0, 1}.
    """

    if binary_resolved:
        if binary_value not in (0, 1):
            raise ValueError(
                f"binary_value must be 0 or 1 when binary_resolved=True; got {binary_value!r}"
            )

    reviewed_at = (now or datetime.now(timezone.utc)).isoformat()

    with core._lock, core._connect() as db:
        row = db.execute(
            """
            select id, predicted_outcome, confidence, created_at
              from calibration_records
             where tenant_id = ? and decision_log_id = ?
             order by created_at desc
             limit 1
            """,
            (tenant_id, decision_log_id),
        ).fetchone()
        if row is None:
            raise LookupError(
                f"no calibration prediction for tenant={tenant_id!r} decision={decision_log_id!r}"
            )
        # ``row`` is sqlite3.Row; access by index for protocol independence.
        record_id = row[0]
        predicted_outcome = row[1]
        confidence = float(row[2])
        created_at = row[3]

        if binary_resolved and binary_value is not None:
            brier = brier_score([confidence], [binary_value])
            ll = log_loss([confidence], [binary_value])
        else:
            brier = None
            ll = None

        db.execute(
            """
            update calibration_records
               set binary_resolved = ?,
                   binary_value    = ?,
                   brier_score     = ?,
                   log_loss        = ?,
                   reviewed_at     = ?
             where tenant_id = ? and id = ?
            """,
            (
                1 if binary_resolved else 0,
                binary_value if binary_resolved else None,
                brier,
                ll,
                reviewed_at,
                tenant_id,
                record_id,
            ),
        )

    _emit_calibration_audit(
        core=core,
        tenant_id=tenant_id,
        actor=actor,
        decision_log_id=decision_log_id,
        payload={
            "decision_log_id": decision_log_id,
            "brier_score": brier,
            "log_loss": ll,
            "source": "outcome",
        },
    )

    return CalibrationRecord(
        predicted_outcome=predicted_outcome,
        confidence=confidence,
        binary_resolved=binary_resolved,
        binary_value=binary_value if binary_resolved else None,
        brier_score=brier,
        log_loss=ll,
        id=record_id,
        tenant_id=tenant_id,
        decision_log_id=decision_log_id,
        created_at=created_at,
        reviewed_at=reviewed_at,
    )


def list_calibration_records(
    *,
    core: _CalibrationStore,
    tenant_id: str,
) -> list[CalibrationRecord]:
    """Return all calibration records for ``tenant_id`` in chronological order.

    Resolved rows are sorted by ``reviewed_at`` and unresolved rows by
    ``created_at``; both fall back to ``created_at`` so the ordering is
    stable even when ``reviewed_at`` is ``NULL``. Used by the dashboard
    endpoints (Task 5.2) and by the unit tests below.
    """

    with core._lock, core._connect() as db:
        rows = db.execute(
            """
            select id, tenant_id, decision_log_id, predicted_outcome, confidence,
                   binary_resolved, binary_value, brier_score, log_loss,
                   created_at, reviewed_at
              from calibration_records
             where tenant_id = ?
             order by coalesce(reviewed_at, created_at) asc, created_at asc
            """,
            (tenant_id,),
        ).fetchall()

    out: list[CalibrationRecord] = []
    for row in rows:
        out.append(
            CalibrationRecord(
                predicted_outcome=row[3],
                confidence=float(row[4]),
                binary_resolved=bool(row[5]),
                binary_value=row[6],
                brier_score=row[7],
                log_loss=row[8],
                id=row[0],
                tenant_id=row[1],
                decision_log_id=row[2],
                created_at=row[9],
                reviewed_at=row[10],
            )
        )
    return out
