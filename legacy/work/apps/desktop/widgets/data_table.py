from __future__ import annotations

import json
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget, QTableWidgetItem


class DataTable(QTableWidget):
    def __init__(self, columns: list[tuple[str, str]], parent=None) -> None:
        super().__init__(0, len(columns), parent)
        self.columns = columns
        self.setHorizontalHeaderLabels([label for _, label in columns])
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.horizontalHeader().setStretchLastSection(True)
        self.verticalHeader().setVisible(False)
        self.setSortingEnabled(True)

    def set_rows(self, rows: list[dict[str, Any]]) -> None:
        self.setSortingEnabled(False)
        self.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for col_index, (key, _) in enumerate(self.columns):
                value = row.get(key, "")
                if isinstance(value, (dict, list)):
                    value = json.dumps(value, ensure_ascii=False)
                item = QTableWidgetItem("" if value is None else str(value))
                item.setData(Qt.UserRole, row)
                if isinstance(value, (int, float)):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.setItem(row_index, col_index, item)
        self.setSortingEnabled(True)

    def selected_rows_data(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[int] = set()
        for item in self.selectedItems():
            if item.row() in seen:
                continue
            seen.add(item.row())
            data = item.data(Qt.UserRole)
            if isinstance(data, dict):
                rows.append(data)
        return rows

    def current_row_data(self) -> dict[str, Any] | None:
        item = self.item(self.currentRow(), 0)
        if not item:
            return None
        data = item.data(Qt.UserRole)
        return data if isinstance(data, dict) else None
