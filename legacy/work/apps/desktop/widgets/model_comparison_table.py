from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QGridLayout, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from rag_core.embedding_eval import EmbeddingScoreResult, build_model_comparison_rows, summarize_model_recommendations


class ModelComparisonTableWidget(QWidget):
    HEADERS = [
        "模型名称",
        "Provider",
        "维度",
        "最大输入长度",
        "综合评分",
        "等级",
        "检索质量分",
        "语义区分度分",
        "上下文质量分",
        "工程可用性分",
        "Recall@5",
        "nDCG@10",
        "MRR@10",
        "Precision@5",
        "Hard Negative Margin",
        "Avg Latency",
        "P95 Latency",
        "Cost / 1k chunks",
        "Storage / 1k chunks",
        "是否需要重建索引",
        "推荐用途",
        "操作",
    ]

    KEYS = [
        "model_name",
        "provider",
        "dimension",
        "max_input_length",
        "overall_score",
        "grade",
        "retrieval_quality_score",
        "semantic_separation_score",
        "rag_context_quality_score",
        "engineering_quality_score",
        "recall_at_5",
        "ndcg_at_10",
        "mrr_at_10",
        "precision_at_5",
        "hard_negative_margin",
        "avg_latency",
        "p95_latency",
        "cost_per_1k_chunks",
        "storage_per_1k_chunks",
        "need_reindex",
        "recommended_use",
        "operation",
    ]

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.summary = QWidget()
        self.summary_layout = QGridLayout(self.summary)
        self.summary_layout.setContentsMargins(0, 0, 0, 8)
        layout.addWidget(self.summary)
        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

    def set_results(self, results: list[EmbeddingScoreResult]) -> None:
        self._set_summary(results)
        rows = build_model_comparison_rows(results)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for col_index, key in enumerate(self.KEYS):
                value = row.get(key, "")
                if isinstance(value, bool):
                    value = "需要" if value else "否"
                if isinstance(value, float):
                    value = f"{value:.0f}"
                item = QTableWidgetItem(str(value))
                if col_index in {2, 3, 4, 6, 7, 8, 9, 10, 11, 12, 13}:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(row_index, col_index, item)
        self.table.resizeColumnsToContents()
        self.table.setSortingEnabled(True)

    def _set_summary(self, results: list[EmbeddingScoreResult]) -> None:
        while self.summary_layout.count():
            item = self.summary_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        recommendations = summarize_model_recommendations(results)
        labels = [
            ("当前最佳综合模型", recommendations["best_overall"]),
            ("质量优先推荐", recommendations["quality_first"]),
            ("成本优先推荐", recommendations["cost_first"]),
            ("本地部署推荐", recommendations["local_deployment"]),
            ("API 部署推荐", recommendations["api_deployment"]),
        ]
        for index, (name, value) in enumerate(labels):
            name_label = QLabel(name)
            value_label = QLabel(value)
            value_label.setObjectName("SummaryValue")
            self.summary_layout.addWidget(name_label, index // 3, (index % 3) * 2)
            self.summary_layout.addWidget(value_label, index // 3, (index % 3) * 2 + 1)
        self.summary.setStyleSheet("QLabel#SummaryValue { font-weight: 700; color: #1f2933; }")
