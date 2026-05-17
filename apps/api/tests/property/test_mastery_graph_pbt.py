"""Property-based test for the mastery graph topological ordering.

Feature: expert-coaching-loop, Property 23: Topological learn_plan and due-only practice
Validates: Requirements 5.3, 5.4

Property 23 (design.md): for any tenant's Concept graph, the system surfaces
concepts in an order such that for every prerequisite edge ``parent → child``
the parent never appears strictly after the child, and "due-only" practice
returns only concepts whose ``next_due_at <= now`` (or is NULL).

This test exercises :meth:`KnowledgeCore.list_due_concepts`, which is the
shared primitive behind both the SM-2 ``retrieval_practice_plan`` due-only
selection (R5.3) and the topological ordering used by ``learn_plan``
(R5.4) per task 3.4. Generators build small random DAGs (3-8 concepts)
with mixed mastery / due-state distributions, and the property asserts:

  1. every returned concept satisfies ``next_due_at <= now`` or NULL, and
  2. for every prerequisite edge ``(parent, child)`` whose endpoints both
     appear in the returned list, ``index(parent) < index(child)``.
"""

from __future__ import annotations

import sqlite3
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from hypothesis import HealthCheck, given, settings, strategies as st

from apps.api.app.knowledge_core import KnowledgeCore


# ---------------------------------------------------------------------------
# Fixed reference clock
# ---------------------------------------------------------------------------

# A deterministic ``now`` keeps generated due/non-due timestamps inside a
# representable, reasoning-friendly band and keeps the property reproducible
# across machines.
_NOW = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------


@st.composite
def _dag(draw) -> tuple[int, list[tuple[int, int]]]:
    """Generate a small DAG: number of nodes (3-8) plus a list of edges.

    Edges are always ``(parent_idx, child_idx)`` with ``parent_idx <
    child_idx`` so the resulting graph is acyclic by construction. We
    sample a subset of the possible upper-triangular edges so the graph
    density varies across examples.
    """

    n = draw(st.integers(min_value=3, max_value=8))
    possible_edges = [(i, j) for i in range(n) for j in range(i + 1, n)]
    if not possible_edges:
        return n, []
    # Subsample edges. ``unique=True`` plus a list-of-tuples keeps each
    # edge at most once.
    chosen = draw(
        st.lists(
            st.sampled_from(possible_edges),
            min_size=0,
            max_size=len(possible_edges),
            unique=True,
        )
    )
    return n, chosen


# ``next_due_at`` per concept: NULL, in the past (due), or strictly in the
# future (not due). The three branches are weighted so that every example
# usually contains both due and non-due concepts.
_due_choice = st.sampled_from(["null", "past", "future"])

_mastery_score = st.floats(
    min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _next_due_iso(choice: str, *, offset_days: float) -> str | None:
    """Translate a ``due_choice`` into a concrete ISO timestamp."""

    if choice == "null":
        return None
    if choice == "past":
        return (_NOW - timedelta(days=max(0.0, offset_days))).isoformat()
    return (_NOW + timedelta(days=max(0.5, offset_days))).isoformat()


def _seed(
    db_path: str,
    *,
    tenant_id: str,
    n: int,
    edges: list[tuple[int, int]],
    due_choices: list[str],
    offsets: list[float],
    mastery: list[float],
) -> list[str]:
    """Insert ``n`` concepts and the requested prerequisite edges directly.

    Bypassing the ``absorb`` pipeline keeps each row's ``next_due_at`` and
    ``mastery_score`` exactly as the strategy generated them, which is
    required to drive the property end-to-end.
    """

    concept_ids = [f"cpt_{tenant_id}_{i:02d}" for i in range(n)]
    with sqlite3.connect(db_path) as db:
        for idx, concept_id in enumerate(concept_ids):
            # ``created_at`` advances monotonically with the index so the
            # topological tiebreaker matches the natural ``i < j`` edge
            # direction the strategy uses; this keeps the test crisp
            # without relying on tiebreaker choices we did not declare.
            created_at = (_NOW - timedelta(days=n - idx)).isoformat()
            db.execute(
                """
                insert into concepts(
                  id, tenant_id, label, summary, created_at,
                  mastery_score, last_practiced_at, next_due_at,
                  decay_lambda, ef, repetition, interval_days, domain
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    concept_id,
                    tenant_id,
                    f"label-{idx}",
                    f"summary for concept {idx}",
                    created_at,
                    mastery[idx],
                    None,
                    _next_due_iso(due_choices[idx], offset_days=offsets[idx]),
                    0.05,
                    2.5,
                    0,
                    0.0,
                    None,
                ),
            )
        for parent_idx, child_idx in edges:
            db.execute(
                """
                insert into concept_prerequisites(
                  parent_concept_id, child_concept_id, tenant_id, weight
                ) values (?, ?, ?, 1.0)
                """,
                (concept_ids[parent_idx], concept_ids[child_idx], tenant_id),
            )
        db.commit()
    return concept_ids


# ---------------------------------------------------------------------------
# Property 23 — topological learn_plan ordering + due-only practice
# Validates: Requirements 5.3, 5.4
# ---------------------------------------------------------------------------


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(graph=_dag(), data=st.data())
def test_property_23_learn_plan_topological_and_practice_due_only(
    graph: tuple[int, list[tuple[int, int]]], data
) -> None:
    """``list_due_concepts`` returns due-only concepts in topological order.

    Validates Property 23 across a generated DAG: every emitted concept is
    due (``next_due_at <= now`` or NULL) and prerequisites never appear
    strictly after their dependents in the returned list.
    """

    n, edges = graph
    due_choices = data.draw(
        st.lists(_due_choice, min_size=n, max_size=n), label="due_choices"
    )
    offsets = data.draw(
        st.lists(
            st.floats(
                min_value=0.0,
                max_value=120.0,
                allow_nan=False,
                allow_infinity=False,
            ),
            min_size=n,
            max_size=n,
        ),
        label="due_offsets",
    )
    mastery = data.draw(
        st.lists(_mastery_score, min_size=n, max_size=n), label="mastery_scores"
    )

    # Fresh tmp DB per Hypothesis example so seeded rows from prior
    # examples cannot leak into the assertion set. We use ``tempfile``
    # directly (rather than the pytest ``tmp_path_factory`` fixture)
    # because Hypothesis re-invokes the test body inside a single
    # function-scoped fixture, and the per-example uniqueness must not
    # depend on pytest's numbered-temp-dir bookkeeping.
    with tempfile.TemporaryDirectory(
        prefix="reality-os-mastery-graph-pbt-", ignore_cleanup_errors=True
    ) as tmp_dir:
        db_path = str(Path(tmp_dir) / "kc.sqlite3")
        core = KnowledgeCore(path=db_path)

        tenant_id = f"tenant_{uuid.uuid4().hex[:10]}"
        concept_ids = _seed(
            db_path,
            tenant_id=tenant_id,
            n=n,
            edges=edges,
            due_choices=due_choices,
            offsets=offsets,
            mastery=mastery,
        )

        result = core.list_due_concepts(tenant_id=tenant_id, now=_NOW)
        result_ids = [concept.id for concept in result]

        # --- Invariant 1: due-only ------------------------------------
        # Every returned concept's persisted ``next_due_at`` must be
        # NULL or ``<= _NOW``. The seeded ``due_choices`` drive this;
        # we re-check against the generated schedule rather than the
        # in-memory dataclass to defend against future field renames.
        expected_due_ids = {
            concept_ids[i]
            for i in range(n)
            if due_choices[i] != "future"
        }
        expected_not_due_ids = set(concept_ids) - expected_due_ids

        for concept in result:
            assert concept.id in expected_due_ids, (
                f"non-due concept {concept.id!r} surfaced; due_choice="
                f"{due_choices[concept_ids.index(concept.id)]}"
            )

        # All due concepts should appear; none of the not-due ones
        # should.
        assert set(result_ids) == expected_due_ids
        assert expected_not_due_ids.isdisjoint(result_ids)

        # --- Invariant 2: topological order ---------------------------
        # For every prereq edge whose endpoints both made it into the
        # due set, the parent must precede (strict) the child in the
        # result.
        position = {cid: idx for idx, cid in enumerate(result_ids)}
        for parent_idx, child_idx in edges:
            parent_id = concept_ids[parent_idx]
            child_id = concept_ids[child_idx]
            if parent_id in position and child_id in position:
                assert position[parent_id] < position[child_id], (
                    f"prereq violation: parent {parent_id!r} at "
                    f"{position[parent_id]} must precede child "
                    f"{child_id!r} at {position[child_id]}; "
                    f"due_choices={due_choices}, edges={edges}"
                )
