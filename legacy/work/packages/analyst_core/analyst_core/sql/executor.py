from __future__ import annotations

import time
from typing import Any

from analyst_core.core.config import Settings, get_settings
from analyst_core.db.connection import get_readonly_connection, install_readonly_authorizer, install_timeout
from analyst_core.schemas.data_agent import SQLExecutionResult
from security import mask_pii


class ReadOnlySQLExecutor:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def execute(self, sql: str) -> SQLExecutionResult:
        started = time.perf_counter()
        try:
            with get_readonly_connection(self.settings) as conn:
                install_readonly_authorizer(conn)
                install_timeout(conn, self.settings.sql_timeout_seconds)
                cursor = conn.execute(sql)
                rows = cursor.fetchall()
                columns = [description[0] for description in cursor.description or []]
                table_rows: list[dict[str, Any]] = [
                    mask_pii({column: row[column] for column in columns})
                    for row in rows
                ]
        except Exception as exc:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            return SQLExecutionResult(
                executed_sql=sql,
                columns=[],
                rows=[],
                row_count=0,
                elapsed_ms=elapsed_ms,
                error=str(exc),
            )

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return SQLExecutionResult(
            executed_sql=sql,
            columns=columns,
            rows=table_rows,
            row_count=len(table_rows),
            elapsed_ms=elapsed_ms,
            error=None,
        )


