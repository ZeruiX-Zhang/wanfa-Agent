from __future__ import annotations

import sqlite3

from analyst_core.connectors.base import StructuredDataConnector
from analyst_core.core.config import Settings


class SQLiteDemoConnector(StructuredDataConnector):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def connect(self, readonly: bool = True) -> sqlite3.Connection:
        db_path = self.settings.database_path
        if readonly:
            return sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True, check_same_thread=False)
        return sqlite3.connect(db_path, check_same_thread=False)
