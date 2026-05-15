from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from rag_core.embedding_eval import EmbeddingScoreResult, EmbeddingReportExporter, MetricScoreRow


class MetricTableWidget(QWidget):
    HEADERS = ["指标名称", "当前值", "归一化分数", "权重", "加权得分", "阈值判断", "解释", "优化建议"]

    def __init__(self, title: str = "指标表格") -> None:
        super().__init__()
        self.rows: list[MetricScoreRow] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        toolbar = QHBoxLayout()
        self.title_label = QLabel(title)
        self.export_button = QPushButton("导出 CSV")
        self.export_button.clicked.connect(self._export_default_csv)
        toolbar.addWidget(self.title_label)
        toolbar.addStretch(1)
        toolbar.addWidget(self.export_button)
        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.cellDoubleClicked.connect(self._show_metric_detail)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addLayout(toolbar)
        layout.addWidget(self.table)

    def set_result(self, result: EmbeddingScoreResult, category_key: str | None = None) -> None:
        rows = [row for row in result.metric_rows if category_key is None or row.category_key == category_key]
        self.set_rows(rows)

    def set_rows(self, rows: list[MetricScoreRow]) -> None:
        self.rows = rows
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values: list[Any] = [
                row.metric_name,
                row.current_value,
                f"{row.normalized_score:.0f}",
                f"{row.weight:.2f}",
                f"{row.weighted_score:.2f}",
                row.judgement,
                row.explanation,
                row.suggestion,
            ]
            for col_index, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if col_index in {2, 3, 4}:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                item.setData(Qt.UserRole, row)
                self.table.setItem(row_index, col_index, item)
        self.table.resizeColumnsToContents()
        self.table.setSortingEnabled(True)

    def export_csv(self, path: str | Path) -> None:
        if not self.rows:
            Path(path).write_text("", encoding="utf-8")
            return
        partial_result = _PartialMetricResult(self.rows)
        csv_text = EmbeddingReportExporter().to_csv(partial_result)  # type: ignore[arg-type]
        Path(path).write_text(csv_text, encoding="utf-8")

    def _export_default_csv(self) -> None:
        path = Path.cwd() / "embedding_metric_table.csv"
        self.export_csv(path)
        self.export_button.setText(f"已导出 {path.name}")

    def _show_metric_detail(self, row_index: int, column: int) -> None:
        item = self.table.item(row_index, column)
        metric = item.data(Qt.UserRole) if item else None
        if not isinstance(metric, MetricScoreRow):
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(metric.metric_name)
        dialog.resize(560, 360)
        layout = QVBoxLayout(dialog)
        text = QTextEdit()
        text.setReadOnly(True)
        text.setPlainText(
            f"指标: {metric.metric_name}\n"
            f"当前值: {metric.current_value}\n"
            f"归一化分数: {metric.normalized_score:.0f}\n"
            f"权重: {metric.weight:.2f}\n"
            f"加权得分: {metric.weighted_score:.2f}\n"
            f"判断: {metric.judgement}\n\n"
            f"解释: {metric.explanation}\n\n"
            f"该指标为什么重要: {metric.why_it_matters}\n\n"
            f"优化建议: {metric.suggestion}"
        )
        layout.addWidget(text)
        close = QPushButton("关闭")
        close.clicked.connect(dialog.accept)
        layout.addWidget(close, alignment=Qt.AlignRight)
        dialog.exec()


class _PartialMetricResult:
    def __init__(self, rows: list[MetricScoreRow]) -> None:
        self.metric_rows = rows
