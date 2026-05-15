from __future__ import annotations

from PySide6.QtWidgets import QLabel


class StatusBadge(QLabel):
    COLORS = {
        "indexed": ("#e7f7ed", "#137333"),
        "embedded": ("#e7f7ed", "#137333"),
        "ok": ("#e7f7ed", "#137333"),
        "failed": ("#fdecec", "#b42318"),
        "stale": ("#fff7e6", "#a15c00"),
        "pending": ("#eef4ff", "#1d4ed8"),
        "raw_only": ("#f3f4f6", "#374151"),
    }

    def __init__(self, text: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setText(text)

    def setText(self, text: str) -> None:  # noqa: N802
        super().setText(text)
        key = text.lower().replace(" ", "_")
        bg, fg = self.COLORS.get(key, ("#eef2f7", "#334155"))
        self.setStyleSheet(f"padding: 3px 8px; border-radius: 8px; background: {bg}; color: {fg}; font-weight: 600;")
