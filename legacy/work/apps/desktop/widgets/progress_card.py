from __future__ import annotations

from PySide6.QtWidgets import QLabel, QProgressBar, QVBoxLayout, QWidget


class ProgressCard(QWidget):
    def __init__(self, title: str, value: str = "", progress: int = 0, parent=None) -> None:
        super().__init__(parent)
        self.title = QLabel(title)
        self.title.setObjectName("CardTitle")
        self.value = QLabel(value)
        self.value.setObjectName("CardValue")
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(progress)
        layout = QVBoxLayout(self)
        layout.addWidget(self.title)
        layout.addWidget(self.value)
        layout.addWidget(self.bar)

    def update_value(self, value: str, progress: int = 0) -> None:
        self.value.setText(value)
        self.bar.setValue(progress)
