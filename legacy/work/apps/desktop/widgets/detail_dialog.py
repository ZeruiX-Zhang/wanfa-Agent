from __future__ import annotations

import json
from typing import Any

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QPlainTextEdit, QVBoxLayout


class DetailDialog(QDialog):
    def __init__(self, title: str, payload: Any, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(820, 620)
        layout = QVBoxLayout(self)
        editor = QPlainTextEdit()
        editor.setReadOnly(True)
        if isinstance(payload, str):
            editor.setPlainText(payload)
        else:
            editor.setPlainText(json.dumps(payload, ensure_ascii=False, indent=2))
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(editor, 1)
        layout.addWidget(buttons)
