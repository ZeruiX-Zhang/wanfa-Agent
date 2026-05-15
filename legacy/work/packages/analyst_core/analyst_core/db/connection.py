from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from analyst_core.connectors import get_connector
from analyst_core.core.config import Settings, get_settings


def _readonly_uri(path: Path) -> str:
    return f"file:{path.as_posix()}?mode=ro"


def get_readonly_connection(settings: Settings | None = None) -> sqlite3.Connection:
    settings = settings or get_settings()
    connector = get_connector(settings)
    conn = connector.connect(readonly=True)
    conn.row_factory = sqlite3.Row
    return conn


def install_readonly_authorizer(conn: sqlite3.Connection) -> None:
    allowed_functions = {
        "abs",
        "avg",
        "cast",
        "coalesce",
        "count",
        "date",
        "ifnull",
        "julianday",
        "lower",
        "max",
        "min",
        "nullif",
        "printf",
        "round",
        "strftime",
        "sum",
        "total",
        "upper",
    }

    def authorizer(action_code: int, arg1: str | None, arg2: str | None, db_name: str | None, trigger: str | None) -> int:
        if action_code == sqlite3.SQLITE_SELECT:
            return sqlite3.SQLITE_OK
        if action_code == sqlite3.SQLITE_READ:
            table_name = (arg1 or "").lower()
            if table_name.startswith("sqlite_"):
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK
        if action_code == sqlite3.SQLITE_FUNCTION:
            function_name = (arg2 or arg1 or "").lower()
            if function_name in allowed_functions:
                return sqlite3.SQLITE_OK
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_DENY

    conn.set_authorizer(authorizer)


def install_timeout(conn: sqlite3.Connection, timeout_seconds: int) -> None:
    deadline = time.monotonic() + max(timeout_seconds, 1)

    def progress_handler() -> int:
        if time.monotonic() > deadline:
            return 1
        return 0

    conn.set_progress_handler(progress_handler, 1000)


