from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QProgressBar,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from rag_core.embedding_eval import EmbeddingScoreResult, grade_color


class ScoreProgressWidget(QFrame):
    def __init__(self, title: str = "综合质量评分") -> None:
        super().__init__()
        self.setObjectName("ScoreProgressWidget")
        self.title = title
        self.detail = QWidget()
        self.detail.setVisible(False)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("ScoreTitle")
        self.score_label = QLabel("- / 100")
        self.score_label.setObjectName("ScoreNumber")
        self.grade_label = QLabel("-")
        self.grade_label.setObjectName("GradeBadge")
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(True)
        self.progress.setFixedHeight(20)
        self.recommendation_label = QLabel("点击评分条展开评分明细。")
        self.recommendation_label.setWordWrap(True)
        self.risk_label = QLabel("")
        self.risk_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        header = QGridLayout()
        header.addWidget(self.title_label, 0, 0)
        header.addWidget(self.score_label, 0, 1, alignment=Qt.AlignRight)
        header.addWidget(self.grade_label, 0, 2, alignment=Qt.AlignRight)
        header.setColumnStretch(0, 1)
        layout.addLayout(header)
        layout.addWidget(self.progress)
        layout.addWidget(self.recommendation_label)
        layout.addWidget(self.risk_label)
        layout.addWidget(self.detail)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.setCursor(Qt.PointingHandCursor)
        self._build_empty_detail()
        self.setStyleSheet(self._style("#64748b"))

    def set_result(self, result: EmbeddingScoreResult) -> None:
        color = grade_color(result.grade)
        self.score_label.setText(f"综合评分: {result.overall_score:.0f} / 100")
        self.grade_label.setText(result.grade)
        self.progress.setValue(int(round(result.overall_score)))
        self.progress.setFormat(f"{result.overall_score:.0f}%")
        self.recommendation_label.setText(f"推荐: {result.recommendation}")
        self.risk_label.setText("风险提示: " + "；".join(result.risk_notes))
        self._build_detail(result)
        self.setStyleSheet(self._style(color))

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        self.detail.setVisible(not self.detail.isVisible())
        super().mousePressEvent(event)

    def _build_empty_detail(self) -> None:
        layout = QGridLayout(self.detail)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.addWidget(QLabel("暂无评分。"), 0, 0)

    def _build_detail(self, result: EmbeddingScoreResult) -> None:
        while self.detail.layout() and self.detail.layout().count():
            item = self.detail.layout().takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        layout = self.detail.layout() or QGridLayout(self.detail)
        layout.setContentsMargins(0, 8, 0, 0)
        scores = [
            ("检索质量", result.retrieval_quality_score),
            ("语义区分度", result.semantic_separation_score),
            ("上下文质量", result.rag_context_quality_score),
            ("工程可用性", result.engineering_quality_score),
        ]
        for index, (label, score) in enumerate(scores):
            name = QLabel(label)
            value = QLabel(f"{score:.0f}")
            value.setObjectName("SubScore")
            layout.addWidget(name, index, 0)
            layout.addWidget(value, index, 1)

    def _style(self, color: str) -> str:
        return f"""
        QFrame#ScoreProgressWidget {{
            background: white;
            border: 1px solid #d8dee9;
            border-radius: 8px;
        }}
        QLabel#ScoreTitle {{
            font-size: 15px;
            font-weight: 700;
            color: #1f2933;
        }}
        QLabel#ScoreNumber {{
            font-size: 18px;
            font-weight: 700;
            color: #1f2933;
        }}
        QLabel#GradeBadge {{
            background: {color};
            color: white;
            border-radius: 6px;
            padding: 4px 10px;
            font-weight: 700;
        }}
        QLabel#SubScore {{
            font-weight: 700;
            color: #1f2933;
        }}
        QProgressBar {{
            border: none;
            border-radius: 8px;
            background: #edf1f7;
            text-align: center;
            color: #111827;
        }}
        QProgressBar::chunk {{
            background: {color};
            border-radius: 8px;
        }}
        """
