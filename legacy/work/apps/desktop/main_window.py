from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QListWidget, QListWidgetItem, QMainWindow, QStackedWidget, QWidget

from desktop.pages.annotation_page import AnnotationPage
from desktop.pages.chunk_preview_page import ChunkPreviewPage
from desktop.pages.chunking_rules_page import ChunkingRulesPage
from desktop.pages.cleaning_rules_page import CleaningRulesPage
from desktop.pages.dashboard_page import DashboardPage
from desktop.pages.debug_page import DebugPage
from desktop.pages.documents_page import DocumentsPage
from desktop.pages.embedding_model_center_page import EmbeddingModelCenterPage
from desktop.pages.evaluation_page import EvaluationPage
from desktop.pages.indexing_page import IndexingPage
from desktop.pages.qa_page import QAPage
from desktop.pages.settings_page import SettingsPage


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Enterprise RAG Workbench")
        self.resize(1480, 920)
        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setCentralWidget(root)

        self.nav = QListWidget()
        self.nav.setObjectName("Sidebar")
        self.nav.setFixedWidth(245)
        self.stack = QStackedWidget()
        layout.addWidget(self.nav)
        layout.addWidget(self.stack, 1)

        pages = [
            ("首页 Dashboard", DashboardPage()),
            ("知识库资料", DocumentsPage()),
            ("清洗规则", CleaningRulesPage()),
            ("切片规则", ChunkingRulesPage()),
            ("Chunk 预览", ChunkPreviewPage()),
            ("LLM 标注", AnnotationPage()),
            ("向量化索引", IndexingPage()),
            ("Embedding 模型中心", EmbeddingModelCenterPage()),
            ("知识库问答", QAPage()),
            ("检索 Debug", DebugPage()),
            ("评测报告", EvaluationPage()),
            ("设置", SettingsPage()),
        ]
        for label, page in pages:
            self.nav.addItem(QListWidgetItem(label))
            self.stack.addWidget(page)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)

        self.setStyleSheet(
            """
            QMainWindow { background: #f6f8fb; color: #16202a; }
            QListWidget#Sidebar {
                background: #17202a;
                color: #d8dee9;
                border: none;
                padding: 12px;
                font-size: 14px;
            }
            QListWidget#Sidebar::item {
                padding: 11px 10px;
                border-radius: 6px;
            }
            QListWidget#Sidebar::item:selected {
                background: #2563eb;
                color: white;
            }
            QLabel#PageTitle {
                font-size: 23px;
                font-weight: 700;
                color: #111827;
            }
            QLabel#Muted { color: #607086; }
            QWidget#Card {
                background: white;
                border: 1px solid #d8dee9;
                border-radius: 8px;
            }
            QLabel#CardTitle { color: #64748b; font-size: 12px; }
            QLabel#CardValue { color: #0f172a; font-size: 18px; font-weight: 700; }
            QPushButton {
                padding: 7px 11px;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                background: white;
            }
            QPushButton:hover { background: #eef4ff; }
            QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox {
                border: 1px solid #cbd5e1;
                border-radius: 5px;
                padding: 5px;
                background: white;
            }
            QTableWidget {
                background: white;
                border: 1px solid #d8dee9;
                gridline-color: #edf1f7;
            }
            QHeaderView::section {
                background: #f1f5f9;
                border: none;
                border-right: 1px solid #d8dee9;
                border-bottom: 1px solid #d8dee9;
                padding: 6px;
                font-weight: 600;
            }
            """
        )
