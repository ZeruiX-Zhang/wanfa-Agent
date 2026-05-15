from __future__ import annotations

import yaml
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QPlainTextEdit, QVBoxLayout, QWidget


class ConfigEditor(QWidget):
    def __init__(self, load_func, save_func, parent=None) -> None:
        super().__init__(parent)
        self.load_func = load_func
        self.save_func = save_func
        self.editor = QPlainTextEdit()
        save = QPushButton("保存 YAML")
        reload_button = QPushButton("重新加载")
        validate = QPushButton("校验")
        save.clicked.connect(self.save)
        reload_button.clicked.connect(self.reload)
        validate.clicked.connect(self.validate)
        buttons = QHBoxLayout()
        buttons.addWidget(save)
        buttons.addWidget(reload_button)
        buttons.addWidget(validate)
        buttons.addStretch(1)
        layout = QVBoxLayout(self)
        layout.addLayout(buttons)
        layout.addWidget(self.editor, 1)
        self.reload()

    def reload(self) -> None:
        self.editor.setPlainText(yaml.safe_dump(self.load_func(), allow_unicode=True, sort_keys=False))

    def save(self) -> None:
        self.save_func(yaml.safe_load(self.editor.toPlainText()) or {})

    def validate(self) -> None:
        yaml.safe_load(self.editor.toPlainText())
