from __future__ import annotations

from PySide6.QtWidgets import QLabel, QProgressBar, QVBoxLayout, QWidget


class MetricScoreBar(QWidget):
    def __init__(self, label: str, score: float = 0, parent=None) -> None:
        super().__init__(parent)
        self.label = QLabel()
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        layout = QVBoxLayout(self)
        layout.addWidget(self.label)
        layout.addWidget(self.bar)
        self.set_score(label, score)

    def set_score(self, label: str, score: float) -> None:
        self.label.setText(f"{label}: {score:.0f}/100")
        self.bar.setValue(int(score))
