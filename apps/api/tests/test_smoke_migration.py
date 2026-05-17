"""Smoke test — schema migration on an existing dev DB (Task 6.5).

R12.1 / R16.1: the additive coaching-schema migration must apply
cleanly to a database that predates the feature, leaving old rows
untouched.
"""

from __future__ import annotations

import sqlite3

from apps.api.app.coaching_schema import COACHING_TABLES
from apps.api.app.knowledge_core import KnowledgeCore


def test_existing_dev_db_migrates_cleanly_and_old_rows_untouched(tmp_path) -> None:
    db_path = tmp_path / "dev.sqlite3"

    # First boot: behaves like a pre-feature dev DB with one absorbed item.
    core_v1 = KnowledgeCore(path=db_path)
    item = core_v1.absorb(
        tenant_id="tnt_migrate",
        title="Original note",
        body="A pre-existing knowledge item from before the migration.",
        source_kind="direct_import",
    )
    original_id = item.id

    # Second boot on the same file: re-runs ``_init_schema`` + the
    # additive coaching migration.
    core_v2 = KnowledgeCore(path=db_path)

    # The old row survived untouched.
    restored = core_v2.library_get(tenant_id="tnt_migrate", item_id=original_id)
    assert restored is not None
    assert restored.title == "Original note"

    # Every new coaching table now exists.
    with sqlite3.connect(db_path) as db:
        names = {
            row[0]
            for row in db.execute(
                "select name from sqlite_master where type = 'table'"
            ).fetchall()
        }
    for table in COACHING_TABLES:
        assert table in names, f"missing migrated table: {table}"

    # The migration is idempotent — a third boot does not raise.
    KnowledgeCore(path=db_path)
