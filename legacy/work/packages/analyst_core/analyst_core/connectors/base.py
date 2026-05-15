from __future__ import annotations

import sqlite3
from abc import ABC, abstractmethod


class StructuredDataConnector(ABC):
    @abstractmethod
    def connect(self, readonly: bool = True) -> sqlite3.Connection:
        raise NotImplementedError
