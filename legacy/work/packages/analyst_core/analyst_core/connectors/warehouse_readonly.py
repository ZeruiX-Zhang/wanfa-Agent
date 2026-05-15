from __future__ import annotations

import sqlite3

from analyst_core.connectors.base import StructuredDataConnector
from analyst_core.core.config import Settings


class WarehouseReadonlyConnector(StructuredDataConnector):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def connect(self, readonly: bool = True) -> sqlite3.Connection:
        raise NotImplementedError(
            "warehouse_readonly connector is reserved for a later production integration phase."
        )
