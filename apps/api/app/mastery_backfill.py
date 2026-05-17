"""Idempotent mastery backfill for existing :class:`Concept` rows.

Sets safe SM-2 defaults (``mastery_score=0.5``, ``decay_lambda=0.05``) on
any pre-existing concept that was created before this feature shipped.
Concepts that already carry non-default mastery state are left untouched
so the script can run multiple times without losing real practice
history.

Run ad hoc::

    py -3 -m apps.api.app.mastery_backfill --db apps/api/.runtime/knowledge_core.sqlite3
"""

from __future__ import annotations

import argparse
import sqlite3
from dataclasses import dataclass
from pathlib import Path

DEFAULT_MASTERY_SCORE = 0.5
DEFAULT_DECAY_LAMBDA = 0.05


@dataclass(frozen=True)
class BackfillReport:
    scanned: int
    updated: int


def backfill_mastery(db: sqlite3.Connection) -> BackfillReport:
    """Apply safe defaults to concepts whose mastery fields are still null/0.

    Idempotent: a row is only updated when *both* ``last_practiced_at`` is
    null *and* ``mastery_score`` equals 0.0. Once a real practice has been
    recorded, the row is skipped on subsequent calls.
    """

    cur = db.execute(
        """
        select id, mastery_score, last_practiced_at, decay_lambda
        from concepts
        """
    )
    scanned = 0
    updated = 0
    for row in cur.fetchall():
        scanned += 1
        mastery_score = row["mastery_score"] if isinstance(row, sqlite3.Row) else row[1]
        last_practiced = row["last_practiced_at"] if isinstance(row, sqlite3.Row) else row[2]
        decay_lambda = row["decay_lambda"] if isinstance(row, sqlite3.Row) else row[3]
        if last_practiced is not None:
            continue
        if mastery_score is not None and mastery_score > 0.0:
            continue
        db.execute(
            "update concepts set mastery_score = ?, decay_lambda = ? where id = ?",
            (
                DEFAULT_MASTERY_SCORE,
                DEFAULT_DECAY_LAMBDA if not decay_lambda else decay_lambda,
                row["id"] if isinstance(row, sqlite3.Row) else row[0],
            ),
        )
        updated += 1
    return BackfillReport(scanned=scanned, updated=updated)


def _open(path: str | Path) -> sqlite3.Connection:
    db = sqlite3.connect(str(path))
    db.row_factory = sqlite3.Row
    return db


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mastery backfill for expert-coaching-loop")
    parser.add_argument(
        "--db",
        required=True,
        help="Path to the knowledge_core SQLite database",
    )
    args = parser.parse_args(argv)
    with _open(args.db) as db:
        report = backfill_mastery(db)
        db.commit()
    print(f"scanned={report.scanned} updated={report.updated}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
