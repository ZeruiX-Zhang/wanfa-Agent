from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from desktop.widgets import DataTable, DetailDialog, MetricScoreBar
from workspace.services import DEFAULT_CONFIGS, DOCUMENT_STAGES, dicts_to_csv, services


class BasePage(QWidget):
    def __init__(self, title: str, subtitle: str = "") -> None:
        super().__init__()
        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(22, 18, 22, 18)
        self.root_layout.setSpacing(12)
        header = QHBoxLayout()
        text = QVBoxLayout()
        self.title_label = QLabel(title)
        self.title_label.setObjectName("PageTitle")
        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setObjectName("Muted")
        self.subtitle_label.setWordWrap(True)
        self.status_label = QLabel("")
        self.status_label.setObjectName("Muted")
        text.addWidget(self.title_label)
        if subtitle:
            text.addWidget(self.subtitle_label)
        header.addLayout(text, 1)
        header.addWidget(self.status_label)
        self.root_layout.addLayout(header)

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def message(self, title: str, text: str) -> None:
        QMessageBox.information(self, title, text)

    def error(self, title: str, exc: Exception | str) -> None:
        QMessageBox.warning(self, title, str(exc))

    def selected_ids(self, table: DataTable, key: str) -> list[str]:
        rows = table.selected_rows_data()
        return [str(row[key]) for row in rows if row.get(key)]

    def first_doc_id(self) -> str | None:
        docs = services.documents.list_documents()
        return docs[0]["doc_id"] if docs else None


def button(text: str, handler) -> QPushButton:
    item = QPushButton(text)
    item.clicked.connect(handler)
    return item


def metric_card(title: str, value: Any) -> QWidget:
    card = QWidget()
    card.setObjectName("Card")
    layout = QVBoxLayout(card)
    label = QLabel(title)
    label.setObjectName("CardTitle")
    number = QLabel(str(value))
    number.setObjectName("CardValue")
    number.setWordWrap(True)
    layout.addWidget(label)
    layout.addWidget(number)
    return card


class DashboardPage(BasePage):
    def __init__(self) -> None:
        super().__init__("首页 Dashboard", "总控台展示 workspace、pipeline、索引、问答和评测状态。")
        actions = QHBoxLayout()
        for label, handler in [
            ("导入示例知识库", self.import_sample),
            ("一键执行完整入库流程", self.run_pipeline),
            ("开始问答", lambda: self.message("问答", "请切换到“知识库问答”页面输入问题。")),
            ("查看 Debug", lambda: self.message("Debug", "请切换到“检索 Debug”页面查看 trace。")),
            ("运行评测", self.run_eval),
            ("刷新", self.refresh),
        ]:
            actions.addWidget(button(label, handler))
        actions.addStretch(1)
        self.root_layout.addLayout(actions)

        self.cards_grid = QGridLayout()
        self.root_layout.addLayout(self.cards_grid)

        self.flow_table = DataTable([("stage", "阶段"), ("status", "状态")])
        self.recent_table = DataTable(
            [
                ("filename", "文档名"),
                ("status", "状态"),
                ("current_stage", "当前阶段"),
                ("chunk_count", "chunk 数"),
                ("embedded_chunk_count", "已向量化"),
                ("embedding_status", "embedding 状态"),
                ("updated_at", "更新时间"),
                ("error_message", "错误"),
            ]
        )
        self.root_layout.addWidget(QLabel("流程进度"))
        self.root_layout.addWidget(self.flow_table)
        self.root_layout.addWidget(QLabel("最近任务"))
        self.root_layout.addWidget(self.recent_table, 1)
        self.refresh()

    def refresh(self) -> None:
        data = services.dashboard()
        for index in reversed(range(self.cards_grid.count())):
            widget = self.cards_grid.itemAt(index).widget()
            if widget:
                widget.deleteLater()
        cards = [
            ("文档总数", data["document_total"]),
            ("已索引文档数", data["indexed_documents"]),
            ("失败文档数", data["failed_documents"]),
            ("chunk 总数", data["chunk_total"]),
            ("已向量化 chunk 数", data["embedded_chunk_total"]),
            ("当前 embedding 模型", data["current_embedding_model"]),
            ("当前向量库", data["current_vector_store"]),
            ("当前 LLM", data["current_llm"]),
            ("最近一次问答耗时", data["last_qa_latency_ms"]),
            ("最近一次评测分数", data["last_eval_score"]),
        ]
        for idx, (title, value) in enumerate(cards):
            self.cards_grid.addWidget(metric_card(title, value), idx // 5, idx % 5)
        self.flow_table.set_rows(data["pipeline_status"])
        self.recent_table.set_rows(data["recent_documents"])
        self.set_status(f"{data['mode']} | {data['workspace']['workspace_root']}")

    def import_sample(self) -> None:
        rows = services.documents.import_sample_docs()
        self.set_status(f"导入示例文档 {len(rows)} 个")
        self.refresh()

    def run_pipeline(self) -> None:
        try:
            results = services.documents.run_full_pipeline()
            self.set_status(f"完整入库流程完成: {len(results)} 个文档")
        except Exception as exc:
            self.error("Pipeline 失败", exc)
        self.refresh()

    def run_eval(self) -> None:
        report = services.evaluation.run_rag_eval()
        self.set_status(f"评测完成 overall_score={report['metrics']['overall_score']}")
        self.refresh()


class DocumentsPage(BasePage):
    def __init__(self) -> None:
        super().__init__("知识库资料", "导入企业文档并驱动 parse → clean → chunk → annotate → embed → index。")
        toolbar = QHBoxLayout()
        for label, handler in [
            ("导入文件", self.import_files),
            ("导入文件夹", self.import_folder),
            ("导入示例知识库", self.import_sample),
            ("打开 raw_docs 文件夹", lambda: services.workspace.open_folder(services.workspace.paths["raw_docs"])),
            ("刷新", self.refresh),
            ("一键处理选中文档", self.run_selected_pipeline),
            ("解析", lambda: self.run_stage("parse")),
            ("清洗", lambda: self.run_stage("clean")),
            ("切片", lambda: self.run_stage("chunk")),
            ("标注", lambda: self.run_stage("annotate")),
            ("向量化", lambda: self.run_stage("embed")),
            ("删除", self.delete_selected),
        ]:
            toolbar.addWidget(button(label, handler))
        toolbar.addStretch(1)
        self.root_layout.addLayout(toolbar)

        self.paths_table = DataTable([("name", "路径"), ("path", "值"), ("operation", "操作")])
        self.docs_table = DataTable(
            [
                ("doc_id", "doc_id"),
                ("filename", "文件名"),
                ("file_type", "文件类型"),
                ("original_path", "原始路径"),
                ("raw_path", "工作区路径"),
                ("file_size", "文件大小"),
                ("status", "状态"),
                ("current_stage", "当前阶段"),
                ("page_count", "页数"),
                ("raw_char_count", "原文字数"),
                ("cleaned_char_count", "清洗后字数"),
                ("chunk_count", "chunk 数"),
                ("embedded_chunk_count", "已向量化"),
                ("annotation_status", "annotation 状态"),
                ("embedding_status", "embedding 状态"),
                ("updated_at", "更新时间"),
                ("error_message", "错误"),
            ]
        )
        self.docs_table.doubleClicked.connect(self.show_doc_detail)
        self.root_layout.addWidget(self.paths_table)
        self.root_layout.addWidget(self.docs_table, 1)
        self.refresh()

    def refresh(self) -> None:
        paths = services.workspace.get_workspace_paths()
        self.paths_table.set_rows([{"name": key, "path": value, "operation": "open"} for key, value in paths.items() if key != "database"])
        self.docs_table.set_rows(services.documents.list_documents())
        self.set_status("数据已刷新")

    def import_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "导入文件", "", "Documents (*.txt *.md *.csv *.html *.htm *.docx *.pdf);;All Files (*)")
        if paths:
            services.documents.import_files(paths)
            self.refresh()

    def import_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "导入文件夹")
        if folder:
            services.documents.import_folder(folder)
            self.refresh()

    def import_sample(self) -> None:
        rows = services.documents.import_sample_docs()
        self.set_status(f"导入 {len(rows)} 个示例文档")
        self.refresh()

    def run_selected_pipeline(self) -> None:
        ids = self.selected_ids(self.docs_table, "doc_id") or [row["doc_id"] for row in services.documents.list_documents()]
        services.documents.run_full_pipeline(ids)
        self.refresh()

    def run_stage(self, stage: str) -> None:
        funcs = {
            "parse": services.parser.parse_document,
            "clean": services.cleaning.run_cleaning,
            "chunk": services.chunking.run_chunking,
            "annotate": services.annotation.run_annotation,
            "embed": services.indexing.run_embedding,
        }
        ids = self.selected_ids(self.docs_table, "doc_id")
        for doc_id in ids:
            funcs[stage](doc_id)
        self.refresh()

    def delete_selected(self) -> None:
        for doc_id in self.selected_ids(self.docs_table, "doc_id"):
            services.documents.delete_document(doc_id)
        self.refresh()

    def show_doc_detail(self) -> None:
        row = self.docs_table.current_row_data()
        if row:
            DetailDialog("Document Detail", row, self).exec()


class RuleConfigPage(BasePage):
    def __init__(self, title: str, filename: str, preview_columns: list[tuple[str, str]], preview_func, run_func) -> None:
        super().__init__(title, f"读取并保存 configs/{filename}，支持表单、YAML、预览和应用。")
        self.filename = filename
        self.preview_func = preview_func
        self.run_func = run_func
        top = QHBoxLayout()
        self.doc_combo = QComboBox()
        for label, handler in [
            ("保存配置", self.save),
            ("恢复默认", self.reset),
            ("校验配置", self.validate),
            ("预览", self.preview),
            ("运行", self.run),
            ("标记受影响文档 stale", self.mark_stale),
        ]:
            top.addWidget(button(label, handler))
        top.addWidget(QLabel("文档"))
        top.addWidget(self.doc_combo)
        top.addStretch(1)
        self.root_layout.addLayout(top)

        splitter = QSplitter(Qt.Horizontal)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        self.form_holder = QWidget()
        self.form_layout = QFormLayout(self.form_holder)
        self.yaml_editor = QPlainTextEdit()
        left_layout.addWidget(self.form_holder)
        left_layout.addWidget(QLabel("YAML 编辑"))
        left_layout.addWidget(self.yaml_editor, 1)
        self.preview_table = DataTable(preview_columns)
        splitter.addWidget(left)
        splitter.addWidget(self.preview_table)
        splitter.setSizes([420, 860])
        self.root_layout.addWidget(splitter, 1)
        self.controls: dict[str, Any] = {}
        self.load_config()
        self.refresh_docs()
        self.preview()

    def refresh_docs(self) -> None:
        current = self.doc_combo.currentData()
        self.doc_combo.clear()
        for doc in services.documents.list_documents():
            self.doc_combo.addItem(doc["filename"], doc["doc_id"])
        if current:
            idx = self.doc_combo.findData(current)
            if idx >= 0:
                self.doc_combo.setCurrentIndex(idx)

    def load_config(self) -> None:
        config = services.workspace.load_config(self.filename)
        while self.form_layout.count():
            item = self.form_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.controls = {}
        for key, value in config.items():
            if isinstance(value, bool):
                widget = QCheckBox()
                widget.setChecked(value)
            elif isinstance(value, int):
                widget = QSpinBox()
                widget.setRange(0, 100000)
                widget.setValue(value)
            else:
                widget = QLineEdit(str(value))
            self.controls[key] = widget
            self.form_layout.addRow(key, widget)
        self.yaml_editor.setPlainText(yaml.safe_dump(config, allow_unicode=True, sort_keys=False))

    def config_from_form(self) -> dict[str, Any]:
        config: dict[str, Any] = {}
        for key, widget in self.controls.items():
            if isinstance(widget, QCheckBox):
                config[key] = widget.isChecked()
            elif isinstance(widget, QSpinBox):
                config[key] = widget.value()
            else:
                config[key] = widget.text()
        return config

    def save(self) -> None:
        config = self.config_from_form()
        services.workspace.save_config(self.filename, config)
        self.yaml_editor.setPlainText(yaml.safe_dump(config, allow_unicode=True, sort_keys=False))
        self.set_status("配置已保存")

    def reset(self) -> None:
        services.settings.reset_config(self.filename)
        self.load_config()
        self.set_status("已恢复默认")

    def validate(self) -> None:
        result = services.settings.validate_config(self.filename, self.yaml_editor.toPlainText())
        self.set_status("YAML 有效" if result["valid"] else "; ".join(result["errors"]))

    def preview(self) -> None:
        self.refresh_docs()
        rows = self.preview_func(self.doc_combo.currentData())
        self.preview_table.set_rows(rows)
        self.set_status(f"预览 {len(rows)} 行")

    def run(self) -> None:
        doc_id = self.doc_combo.currentData()
        if doc_id:
            self.run_func(doc_id)
            self.preview()

    def mark_stale(self) -> None:
        for doc in services.documents.list_documents():
            services.documents.mark_stale(doc["doc_id"], f"{self.filename} changed")
        self.set_status("受影响文档已标记 stale")


class CleaningRulesPage(RuleConfigPage):
    def __init__(self) -> None:
        super().__init__(
            "清洗规则",
            "cleaning.yaml",
            [
                ("block_id", "block_id"),
                ("page", "页码"),
                ("raw_preview", "原始文本预览"),
                ("cleaned_preview", "清洗后文本预览"),
                ("matched_rules", "命中规则"),
                ("delete_reason", "删除原因"),
                ("kept", "是否保留"),
                ("operation", "操作"),
            ],
            services.cleaning.preview_cleaning,
            services.cleaning.run_cleaning,
        )


class ChunkingRulesPage(RuleConfigPage):
    def __init__(self) -> None:
        super().__init__(
            "切片规则",
            "chunking.yaml",
            [
                ("chunk_id", "preview_chunk_id"),
                ("page_start", "页码范围"),
                ("section_path", "章节路径"),
                ("chunk_index", "chunk_index"),
                ("token_count", "token_count"),
                ("char_count", "char_count"),
                ("text_preview", "text_preview"),
                ("split_strategy", "split_strategy"),
                ("split_reason", "split_reason"),
                ("triggered_rules", "triggered_rules"),
                ("previous_overlap_text", "overlap_preview"),
            ],
            services.chunking.preview_chunks,
            services.chunking.run_chunking,
        )


class ChunkPreviewPage(BasePage):
    def __init__(self) -> None:
        super().__init__("Chunk 预览", "查看系统切分了什么、为什么这样切分，以及是否进入向量库。")
        filters = QHBoxLayout()
        self.doc_combo = QComboBox()
        self.status_combo = QComboBox()
        self.status_combo.addItems(["all", "embedded", "stale", "not_started", "failed"])
        self.enabled_combo = QComboBox()
        self.enabled_combo.addItems(["all", "enabled", "disabled"])
        self.section_filter = QLineEdit()
        self.section_filter.setPlaceholderText("章节过滤")
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索 chunk 文本")
        for widget in [QLabel("文档"), self.doc_combo, QLabel("embedding"), self.status_combo, QLabel("enabled"), self.enabled_combo, self.section_filter, self.search]:
            filters.addWidget(widget)
        for label, handler in [
            ("刷新", self.refresh),
            ("导出 CSV", self.export_csv),
            ("导出 JSONL", self.export_jsonl),
            ("查看完整 chunk", self.detail),
            ("编辑 chunk", self.edit),
            ("禁用 chunk", self.disable),
            ("启用 chunk", self.enable),
            ("合并相邻 chunks", self.merge),
            ("拆分 chunk", self.split),
            ("重新生成该文档 chunks", self.regenerate),
        ]:
            filters.addWidget(button(label, handler))
        filters.addStretch(1)
        self.root_layout.addLayout(filters)
        self.table = DataTable(
            [
                ("chunk_id", "chunk_id"),
                ("doc_id", "doc_id"),
                ("filename", "文件名"),
                ("page_start", "页码起"),
                ("page_end", "页码止"),
                ("section_path", "章节路径"),
                ("chunk_index", "chunk_index"),
                ("token_count", "token_count"),
                ("char_count", "char_count"),
                ("text_preview", "chunk_text_preview"),
                ("split_strategy", "split_strategy"),
                ("split_reason", "split_reason"),
                ("triggered_rules", "triggered_rules"),
                ("previous_overlap_text", "previous_overlap_text"),
                ("next_overlap_text", "next_overlap_text"),
                ("contains_table", "contains_table"),
                ("contains_heading", "contains_heading"),
                ("enabled", "enabled"),
                ("embedding_status", "embedding_status"),
                ("embedding_model", "embedding_model"),
                ("vector_id", "vector_id"),
            ]
        )
        self.table.doubleClicked.connect(self.detail)
        self.root_layout.addWidget(self.table, 1)
        self.refresh_docs()
        self.refresh()

    def refresh_docs(self) -> None:
        current = self.doc_combo.currentData()
        self.doc_combo.clear()
        self.doc_combo.addItem("全部", "")
        for doc in services.documents.list_documents():
            self.doc_combo.addItem(doc["filename"], doc["doc_id"])
        if current:
            idx = self.doc_combo.findData(current)
            if idx >= 0:
                self.doc_combo.setCurrentIndex(idx)

    def filters(self) -> dict[str, Any]:
        return {
            "doc_id": self.doc_combo.currentData(),
            "embedding_status": self.status_combo.currentText(),
            "enabled": self.enabled_combo.currentText(),
            "section": self.section_filter.text().strip(),
            "search": self.search.text().strip(),
        }

    def refresh(self) -> None:
        self.refresh_docs()
        rows = services.chunking.list_chunks(self.filters())
        self.table.set_rows(rows)
        self.set_status(f"{len(rows)} chunks")

    def detail(self) -> None:
        row = self.table.current_row_data()
        if row:
            payload = {
                "chunk": row,
                "source": {
                    "raw_path": services.documents.get_document(row["doc_id"]).get("raw_path"),
                    "cleaned_path": services.documents.get_document(row["doc_id"]).get("cleaned_path"),
                },
                "rules": services.chunking.load_config(),
            }
            DetailDialog("Chunk Detail", payload, self).exec()

    def edit(self) -> None:
        row = self.table.current_row_data()
        if not row:
            return
        text, ok = QInputDialog.getMultiLineText(self, "编辑 chunk", "chunk text", row["text"])
        if ok:
            services.chunking.update_chunk(row["chunk_id"], text)
            self.refresh()

    def disable(self) -> None:
        for row in self.table.selected_rows_data():
            services.chunking.disable_chunk(row["chunk_id"])
        self.refresh()

    def enable(self) -> None:
        for row in self.table.selected_rows_data():
            services.chunking.enable_chunk(row["chunk_id"])
        self.refresh()

    def merge(self) -> None:
        ids = self.selected_ids(self.table, "chunk_id")
        if ids:
            services.chunking.merge_chunks(ids)
            self.refresh()

    def split(self) -> None:
        row = self.table.current_row_data()
        if not row:
            return
        pos, ok = QInputDialog.getInt(self, "拆分 chunk", "split_position", max(1, len(row["text"]) // 2), 1, max(1, len(row["text"]) - 1))
        if ok:
            services.chunking.split_chunk(row["chunk_id"], pos)
            self.refresh()

    def regenerate(self) -> None:
        doc_id = self.doc_combo.currentData() or (self.table.current_row_data() or {}).get("doc_id")
        if doc_id:
            services.chunking.run_chunking(doc_id)
            self.refresh()

    def export_csv(self) -> None:
        rows = services.chunking.list_chunks(self.filters())
        path = services.workspace.paths["exports"] / "chunks_export.csv"
        path.write_text(dicts_to_csv(rows), encoding="utf-8")
        self.set_status(f"已导出 {path}")

    def export_jsonl(self) -> None:
        rows = services.chunking.list_chunks(self.filters())
        path = services.workspace.paths["exports"] / "chunks_export.jsonl"
        path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows), encoding="utf-8")
        self.set_status(f"已导出 {path}")


class AnnotationPage(BasePage):
    def __init__(self) -> None:
        super().__init__("LLM 标注", "标注只写入 annotation/metadata，不改写原文；人工审核后才进入正式 metadata。")
        toolbar = QHBoxLayout()
        self.doc_combo = QComboBox()
        toolbar.addWidget(QLabel("文档"))
        toolbar.addWidget(self.doc_combo)
        for label, handler in [
            ("运行 LLM 标注", self.run_annotation),
            ("重新标注", self.run_annotation),
            ("查看标注结果", self.detail),
            ("人工编辑", self.edit),
            ("接受", self.approve),
            ("拒绝", self.reject),
            ("导出 JSON", self.export_json),
            ("打开 annotation 文件夹", lambda: services.workspace.open_folder(services.workspace.paths["annotations"])),
            ("刷新", self.refresh),
        ]:
            toolbar.addWidget(button(label, handler))
        toolbar.addStretch(1)
        self.root_layout.addLayout(toolbar)
        self.table = DataTable(
            [
                ("doc_id", "doc_id"),
                ("filename", "filename"),
                ("doc_type", "doc_type"),
                ("business_domain", "business_domain"),
                ("doc_summary", "summary"),
                ("tags", "tags"),
                ("key_terms", "key_terms"),
                ("confidence", "confidence"),
                ("human_review_status", "human_review_status"),
                ("updated_at", "updated_at"),
            ]
        )
        self.table.doubleClicked.connect(self.detail)
        self.root_layout.addWidget(self.table, 1)
        self.refresh()

    def refresh(self) -> None:
        current = self.doc_combo.currentData()
        self.doc_combo.clear()
        for doc in services.documents.list_documents():
            self.doc_combo.addItem(doc["filename"], doc["doc_id"])
        if current:
            idx = self.doc_combo.findData(current)
            if idx >= 0:
                self.doc_combo.setCurrentIndex(idx)
        rows = services.annotation.list_annotations()
        self.table.set_rows(rows)
        self.set_status(f"{len(rows)} annotations")

    def run_annotation(self) -> None:
        doc_id = self.doc_combo.currentData()
        if doc_id:
            services.annotation.run_annotation(doc_id)
            self.refresh()

    def detail(self) -> None:
        row = self.table.current_row_data()
        if row:
            DetailDialog("Annotation Detail", row, self).exec()

    def edit(self) -> None:
        row = self.table.current_row_data()
        if not row:
            return
        text, ok = QInputDialog.getMultiLineText(self, "编辑 annotation JSON", "annotation", json.dumps(row, ensure_ascii=False, indent=2))
        if ok:
            services.annotation.update_annotation(row["annotation_id"], json.loads(text))
            self.refresh()

    def approve(self) -> None:
        for row in self.table.selected_rows_data():
            services.annotation.approve_annotation(row["annotation_id"])
        self.refresh()

    def reject(self) -> None:
        for row in self.table.selected_rows_data():
            services.annotation.reject_annotation(row["annotation_id"])
        self.refresh()

    def export_json(self) -> None:
        rows = services.annotation.list_annotations()
        path = services.workspace.paths["exports"] / "annotations_export.json"
        path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        self.set_status(f"已导出 {path}")


class IndexingPage(BasePage):
    def __init__(self) -> None:
        super().__init__("向量化索引", "管理 embedding、collection 兼容性和重建索引。")
        toolbar = QHBoxLayout()
        for label, handler in [
            ("开始向量化", self.embed_selected),
            ("暂停", lambda: self.set_status("当前本地任务为同步执行，没有后台队列可暂停。")),
            ("重试失败 chunk", self.retry),
            ("重建当前文档索引", self.rebuild_selected),
            ("重建全部索引", self.rebuild_all),
            ("删除当前文档索引", self.delete_selected),
            ("打开 vector_store 文件夹", lambda: services.workspace.open_folder(services.workspace.paths["vector_store"])),
            ("刷新", self.refresh),
        ]:
            toolbar.addWidget(button(label, handler))
        toolbar.addStretch(1)
        self.root_layout.addLayout(toolbar)
        self.config_table = DataTable([("key", "配置项"), ("value", "值")])
        self.table = DataTable(
            [
                ("doc_id", "doc_id"),
                ("filename", "filename"),
                ("total_chunks", "total_chunks"),
                ("embedded_chunks", "embedded_chunks"),
                ("failed_chunks", "failed_chunks"),
                ("embedding_model", "embedding_model"),
                ("dimension", "dimension"),
                ("collection_name", "collection_name"),
                ("status", "status"),
                ("latency_ms", "latency_ms"),
                ("estimated_cost", "estimated_cost"),
                ("operation", "操作"),
            ]
        )
        self.root_layout.addWidget(self.config_table)
        self.root_layout.addWidget(self.table, 1)
        self.refresh()

    def refresh(self) -> None:
        model = services.embedding_models.active_model()
        vector = services.workspace.load_config("vector_store.yaml")
        compatibility = services.indexing.check_collection_compatibility(model)
        metadata = services.indexing.get_collection_metadata()
        self.config_table.set_rows(
            [
                {"key": "当前 embedding 模型", "value": model.get("display_name")},
                {"key": "provider", "value": model.get("provider")},
                {"key": "dimension", "value": model.get("dimension")},
                {"key": "vector_store 类型", "value": vector.get("type")},
                {"key": "collection_name", "value": vector.get("collection_name")},
                {"key": "distance_metric", "value": vector.get("distance_metric")},
                {"key": "normalize_embeddings", "value": vector.get("normalize_embeddings")},
                {"key": "collection 是否兼容", "value": compatibility.get("compatible")},
                {"key": "是否需要重建索引", "value": compatibility.get("need_reindex")},
                {"key": "collection metadata", "value": metadata},
            ]
        )
        self.table.set_rows(services.indexing.index_task_rows())

    def selected_doc_ids(self) -> list[str]:
        return self.selected_ids(self.table, "doc_id")

    def embed_selected(self) -> None:
        for doc_id in self.selected_doc_ids() or [doc["doc_id"] for doc in services.documents.list_documents()]:
            services.indexing.run_embedding(doc_id)
        self.refresh()

    def retry(self) -> None:
        services.indexing.retry_failed_chunks()
        self.refresh()

    def rebuild_selected(self) -> None:
        for doc_id in self.selected_doc_ids():
            services.indexing.rebuild_document_index(doc_id)
        self.refresh()

    def rebuild_all(self) -> None:
        services.indexing.rebuild_all_indexes()
        self.refresh()

    def delete_selected(self) -> None:
        for doc_id in self.selected_doc_ids():
            services.indexing.delete_document_index(doc_id)
        self.refresh()


class EmbeddingModelCenterPage(BasePage):
    def __init__(self) -> None:
        super().__init__("Embedding 模型中心", "注册、测试、评估和对比 embedding provider，并提示重建索引风险。")
        self.tabs = QTabWidget()
        self.root_layout.addWidget(self.tabs, 1)
        self._build_registry_tab()
        self._build_editor_tab()
        self._build_connection_tab()
        self._build_similarity_tab()
        self._build_retrieval_tab()
        self._build_comparison_tab()
        self._build_weights_tab()
        self.refresh()

    def _build_registry_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        top = QHBoxLayout()
        self.model_combo = QComboBox()
        top.addWidget(QLabel("模型"))
        top.addWidget(self.model_combo)
        top.addWidget(button("设为当前模型", self.set_active))
        top.addWidget(button("测试模型", self.connection_test))
        top.addWidget(button("刷新", self.refresh))
        top.addStretch(1)
        self.registry_table = DataTable(
            [
                ("model_id", "model_id"),
                ("display_name", "模型名称"),
                ("provider", "Provider"),
                ("dimension", "维度"),
                ("max_input_tokens", "最大输入长度"),
                ("overall_score", "综合评分"),
                ("active", "active"),
                ("need_reindex", "需要重建索引"),
                ("recommended_for", "推荐用途"),
            ]
        )
        layout.addLayout(top)
        layout.addWidget(self.registry_table, 1)
        self.tabs.addTab(page, "模型注册表")

    def _build_editor_tab(self) -> None:
        page = QWidget()
        layout = QHBoxLayout(page)
        self.editor_form = QWidget()
        form = QFormLayout(self.editor_form)
        self.editor_fields: dict[str, Any] = {}
        for key in ["model_id", "display_name", "provider", "model", "dimension", "max_input_tokens", "base_url", "api_key_env", "recommended_for"]:
            field = QLineEdit()
            self.editor_fields[key] = field
            form.addRow(key, field)
        form.addRow(button("保存模型", self.save_model))
        self.model_yaml = QPlainTextEdit()
        layout.addWidget(self.editor_form)
        layout.addWidget(self.model_yaml, 1)
        self.tabs.addTab(page, "新增 / 编辑模型")

    def _build_connection_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(button("连接与维度测试", self.connection_test))
        self.connection_text = QPlainTextEdit()
        self.connection_text.setReadOnly(True)
        layout.addWidget(self.connection_text, 1)
        self.tabs.addTab(page, "连接与维度测试")

    def _build_similarity_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(button("运行语义相似度测试", self.similarity_test))
        self.similarity_table = DataTable([("group", "组别"), ("text_a", "文本 A"), ("text_b", "文本 B"), ("similarity", "相似度")])
        layout.addWidget(self.similarity_table, 1)
        self.tabs.addTab(page, "语义相似度测试")

    def _build_retrieval_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(button("运行知识库检索测试", self.retrieval_test))
        self.retrieval_table = DataTable(
            [
                ("query", "query"),
                ("hit", "hit"),
                ("recall_at_5", "Recall@5"),
                ("ndcg_at_10", "nDCG@10"),
                ("mrr_at_10", "MRR@10"),
                ("precision_at_5", "Precision@5"),
                ("failure_reason", "失败原因"),
            ]
        )
        layout.addWidget(self.retrieval_table, 1)
        self.tabs.addTab(page, "知识库检索测试")

    def _build_comparison_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(button("生成模型对比报告", self.compare_models))
        score_row = QHBoxLayout()
        self.score_bars = {
            "overall_score": MetricScoreBar("overall_score"),
            "retrieval_quality_score": MetricScoreBar("检索质量分"),
            "semantic_separation_score": MetricScoreBar("语义区分度分"),
            "rag_context_quality_score": MetricScoreBar("RAG 上下文质量分"),
            "engineering_quality_score": MetricScoreBar("工程可用性分"),
        }
        for bar in self.score_bars.values():
            score_row.addWidget(bar)
        layout.addLayout(score_row)
        self.metric_table = DataTable(
            [
                ("metric_name", "指标名称"),
                ("current_value", "当前值"),
                ("normalized_score", "归一化分数"),
                ("weight", "权重"),
                ("weighted_score", "加权得分"),
                ("judgement", "判断"),
                ("explanation", "解释"),
                ("suggestion", "建议"),
            ]
        )
        self.comparison_table = DataTable(
            [
                ("model_name", "模型名称"),
                ("provider", "Provider"),
                ("dimension", "维度"),
                ("max_input_length", "最大输入长度"),
                ("overall_score", "综合评分"),
                ("grade", "等级"),
                ("recall_at_5", "Recall@5"),
                ("ndcg_at_10", "nDCG@10"),
                ("mrr_at_10", "MRR@10"),
                ("precision_at_5", "Precision@5"),
                ("hard_negative_margin", "Hard Negative Margin"),
                ("avg_latency", "Avg Latency"),
                ("p95_latency", "P95 Latency"),
                ("cost_per_1k_chunks", "Cost / 1k chunks"),
                ("storage_per_1k_chunks", "Storage / 1k chunks"),
                ("need_reindex", "是否需要重建索引"),
                ("recommended_use", "推荐用途"),
            ]
        )
        layout.addWidget(QLabel("综合评分指标"))
        layout.addWidget(self.metric_table)
        layout.addWidget(QLabel("模型对比表"))
        layout.addWidget(self.comparison_table, 1)
        self.tabs.addTab(page, "模型对比报告")

    def _build_weights_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(button("保存评分权重", self.save_weights))
        self.weights_editor = QPlainTextEdit()
        self.weights_editor.setPlainText(yaml.safe_dump(services.workspace.load_config("embedding_eval_weights.yaml"), allow_unicode=True, sort_keys=False))
        layout.addWidget(self.weights_editor, 1)
        self.tabs.addTab(page, "评分权重设置")

    def refresh(self) -> None:
        rows = services.embedding_models.list_models()
        comparison = services.embedding_models.compare_models()
        scores = {row["model_name"]: row["overall_score"] for row in comparison["rows"]}
        for row in rows:
            row["overall_score"] = scores.get(row.get("display_name"), "")
        self.model_combo.clear()
        for row in rows:
            self.model_combo.addItem(row["display_name"], row["model_id"])
        self.registry_table.set_rows(rows)
        self.comparison_table.set_rows(comparison["rows"])
        self.metric_table.set_rows(comparison["metric_rows"])
        best = comparison.get("recommendation") or {}
        for key, bar in self.score_bars.items():
            bar.set_score(key, float(best.get(key) or 0))

    def current_model_id(self) -> str:
        return str(self.model_combo.currentData() or "")

    def set_active(self) -> None:
        result = services.embedding_models.set_active_model(self.current_model_id())
        self.set_status("需要重建索引: " + "; ".join(result.get("issues", [])) if result.get("need_reindex") else "当前模型已切换")
        self.refresh()

    def connection_test(self) -> None:
        result = services.embedding_models.test_connection(self.current_model_id())
        self.connection_text.setPlainText(json.dumps(result, ensure_ascii=False, indent=2))
        self.tabs.setCurrentIndex(2)

    def similarity_test(self) -> None:
        result = services.embedding_models.run_similarity_test(self.current_model_id())
        self.similarity_table.set_rows(result["pair_rows"])
        self.tabs.setCurrentIndex(3)

    def retrieval_test(self) -> None:
        result = services.embedding_models.run_retrieval_benchmark(self.current_model_id())
        self.retrieval_table.set_rows(result["per_query_results"])
        self.tabs.setCurrentIndex(4)

    def compare_models(self) -> None:
        self.refresh()
        self.tabs.setCurrentIndex(5)

    def save_model(self) -> None:
        model = {key: field.text().strip() for key, field in self.editor_fields.items()}
        for key in ["dimension", "max_input_tokens"]:
            if model.get(key):
                model[key] = int(model[key])
        model.update({"normalize_embeddings": True, "distance_metric": "cosine", "status": "enabled", "built_in": False})
        services.embedding_models.update_model(model)
        self.refresh()

    def save_weights(self) -> None:
        data = yaml.safe_load(self.weights_editor.toPlainText()) or {}
        services.workspace.save_config("embedding_eval_weights.yaml", data)
        self.set_status("评分权重已保存")


class QAPage(BasePage):
    def __init__(self) -> None:
        super().__init__("知识库问答", "基于 indexed 文档检索上下文、生成答案、引用来源和 trace。")
        splitter = QSplitter(Qt.Horizontal)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        self.doc_list = QListWidget()
        self.retrieval_mode = QComboBox()
        self.retrieval_mode.addItems(["vector", "bm25", "hybrid"])
        self.retrieval_mode.setCurrentText("hybrid")
        self.top_k = QSpinBox()
        self.top_k.setRange(1, 20)
        self.top_k.setValue(5)
        self.rerank = QCheckBox("rerank")
        self.rerank.setChecked(True)
        left_layout.addWidget(QLabel("可问答文档"))
        left_layout.addWidget(self.doc_list, 1)
        left_layout.addWidget(QLabel("retrieval mode"))
        left_layout.addWidget(self.retrieval_mode)
        left_layout.addWidget(QLabel("top_k"))
        left_layout.addWidget(self.top_k)
        left_layout.addWidget(self.rerank)

        middle = QWidget()
        middle_layout = QVBoxLayout(middle)
        self.examples = QHBoxLayout()
        middle_layout.addLayout(self.examples)
        self.question = QTextEdit()
        self.question.setPlaceholderText("输入知识库问题")
        self.answer = QPlainTextEdit()
        self.answer.setReadOnly(True)
        middle_layout.addWidget(self.question)
        middle_layout.addWidget(button("发送", self.ask))
        middle_layout.addWidget(QLabel("回答"))
        middle_layout.addWidget(self.answer, 1)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        self.citation_table = DataTable(
            [
                ("citation_index", "引用"),
                ("filename", "文档名"),
                ("page_range", "页码"),
                ("vector_score", "vector_score"),
                ("bm25_score", "bm25_score"),
                ("rerank_score", "rerank_score"),
                ("chunk_id", "chunk_id"),
            ]
        )
        self.hit_table = DataTable([("chunk_id", "chunk_id"), ("filename", "文档名"), ("text_preview", "命中 chunks"), ("rerank_score", "rerank_score")])
        self.qa_plan_table = DataTable(
            [
                ("step_id", "步骤"),
                ("question", "子问题"),
                ("query_variants", "查询改写"),
                ("required_evidence", "证据要求"),
            ]
        )
        self.evidence_report_table = DataTable(
            [
                ("step_id", "步骤"),
                ("question", "子问题"),
                ("usable_evidence_count", "可用证据"),
                ("blocked_source_count", "拦截证据"),
            ]
        )
        self.verification_text = QPlainTextEdit()
        self.verification_text.setReadOnly(True)
        self.verification_text.setMaximumHeight(130)
        right_layout.addWidget(QLabel("引用来源"))
        right_layout.addWidget(self.citation_table)
        right_layout.addWidget(QLabel("命中 chunks"))
        right_layout.addWidget(self.hit_table, 1)
        right_layout.addWidget(QLabel("QA Orchestrator 计划"))
        right_layout.addWidget(self.qa_plan_table)
        right_layout.addWidget(QLabel("证据报告"))
        right_layout.addWidget(self.evidence_report_table)
        right_layout.addWidget(QLabel("验证结果"))
        right_layout.addWidget(self.verification_text)
        right_layout.addWidget(button("查看 Debug", self.open_debug_hint))
        splitter.addWidget(left)
        splitter.addWidget(middle)
        splitter.addWidget(right)
        splitter.setSizes([250, 620, 490])
        self.root_layout.addWidget(splitter, 1)
        self.last_trace_id = ""
        self.refresh()

    def refresh(self) -> None:
        self.doc_list.clear()
        for doc in services.documents.list_documents():
            if doc["status"] == "indexed":
                self.doc_list.addItem(f"{doc['filename']} | {doc['chunk_count']} chunks")
        while self.examples.count():
            item = self.examples.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for question in services.query.get_example_questions()[:4]:
            self.examples.addWidget(button(question[:32], lambda checked=False, q=question: self.question.setPlainText(q)))

    def ask(self) -> None:
        question = self.question.toPlainText().strip()
        if not question:
            return
        result = services.query.ask(question, {"mode": self.retrieval_mode.currentText(), "top_k": self.top_k.value(), "rerank": self.rerank.isChecked()})
        self.answer.setPlainText(result["answer"])
        self.citation_table.set_rows(result["citations"])
        self.hit_table.set_rows(result["reranked_chunks"])
        self.qa_plan_table.set_rows(result.get("qa_plan", {}).get("steps", []))
        self.evidence_report_table.set_rows(result.get("evidence_report", {}).get("subquestions", []))
        self.verification_text.setPlainText(
            json.dumps(
                {
                    "answer_type": result.get("answer_type"),
                    "confidence": result.get("confidence"),
                    "verification": result.get("verification", {}),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        self.last_trace_id = result["trace_id"]
        self.set_status(f"trace_id={self.last_trace_id} answer_type={result.get('answer_type')} confidence={result.get('confidence')} latency_ms={result['latency_ms']}")

    def open_debug_hint(self) -> None:
        self.message("Trace", f"trace_id: {self.last_trace_id or '尚未提问'}")


class DebugPage(BasePage):
    def __init__(self) -> None:
        super().__init__("检索 Debug", "查看 trace、query rewrite、fusion、rerank、context、answer 和 citations。")
        toolbar = QHBoxLayout()
        toolbar.addWidget(button("刷新", self.refresh))
        toolbar.addWidget(button("复制 trace", self.copy_trace))
        toolbar.addWidget(button("导出 trace JSON", self.export_trace))
        toolbar.addStretch(1)
        self.root_layout.addLayout(toolbar)
        splitter = QSplitter(Qt.Horizontal)
        self.trace_table = DataTable([("trace_id", "trace_id"), ("question", "question"), ("retrieval_mode", "mode"), ("status", "status"), ("latency_ms", "latency_ms"), ("created_at", "created_at")])
        self.trace_table.currentCellChanged.connect(lambda *_: self.load_current())
        detail = QWidget()
        detail_layout = QVBoxLayout(detail)
        self.detail_text = QPlainTextEdit()
        self.result_table = DataTable(
            [
                ("rank_before", "rank_before"),
                ("rank_after", "rank_after"),
                ("chunk_id", "chunk_id"),
                ("filename", "filename"),
                ("page_range", "page_range"),
                ("section_path", "section_path"),
                ("vector_score", "vector_score"),
                ("bm25_score", "bm25_score"),
                ("hybrid_score", "hybrid_score"),
                ("rerank_score", "rerank_score"),
                ("text_preview", "text_preview"),
            ]
        )
        detail_layout.addWidget(self.detail_text, 1)
        detail_layout.addWidget(self.result_table, 1)
        splitter.addWidget(self.trace_table)
        splitter.addWidget(detail)
        splitter.setSizes([430, 880])
        self.root_layout.addWidget(splitter, 1)
        self.refresh()

    def refresh(self) -> None:
        self.trace_table.set_rows(services.trace.list_traces())
        self.load_current()

    def load_current(self) -> None:
        row = self.trace_table.current_row_data()
        if not row:
            return
        trace = services.trace.get_trace(row["trace_id"])
        self.detail_text.setPlainText(json.dumps(trace, ensure_ascii=False, indent=2))
        self.result_table.set_rows(trace.get("reranked_chunks") or [])

    def copy_trace(self) -> None:
        self.detail_text.selectAll()
        self.detail_text.copy()

    def export_trace(self) -> None:
        row = self.trace_table.current_row_data()
        if row:
            path = services.trace.export_trace(row["trace_id"])
            self.set_status(f"已导出 {path}")


class EvaluationPage(BasePage):
    def __init__(self) -> None:
        super().__init__("评测报告", "运行 RAG 评测、embedding 检索评测并导出报告。")
        toolbar = QHBoxLayout()
        self.eval_set = QComboBox()
        self.eval_set.addItem("data/eval_sets/rag_eval.jsonl", str(Path("data/eval_sets/rag_eval.jsonl")))
        toolbar.addWidget(QLabel("eval set"))
        toolbar.addWidget(self.eval_set)
        toolbar.addWidget(button("运行 RAG 评测", self.run_rag_eval))
        toolbar.addWidget(button("运行 embedding 检索评测", self.run_embedding_eval))
        toolbar.addWidget(button("导出报告", self.export_report))
        toolbar.addStretch(1)
        self.root_layout.addLayout(toolbar)
        self.metrics_grid = QGridLayout()
        self.root_layout.addLayout(self.metrics_grid)
        self.result_table = DataTable(
            [
                ("question", "question"),
                ("expected_answer", "expected_answer"),
                ("expected_sources", "expected_sources"),
                ("actual_answer", "actual_answer"),
                ("retrieved_chunks", "retrieved_chunks"),
                ("score", "score"),
                ("status", "status"),
                ("failure_reason", "failure_reason"),
                ("trace_id", "trace_id"),
            ]
        )
        self.failure_text = QPlainTextEdit()
        self.failure_text.setReadOnly(True)
        self.root_layout.addWidget(self.result_table, 1)
        self.root_layout.addWidget(QLabel("失败样例与优化建议"))
        self.root_layout.addWidget(self.failure_text)
        self.latest_report_id = ""
        self.refresh_latest()

    def run_rag_eval(self) -> None:
        report = services.evaluation.run_rag_eval()
        self.show_report(report)

    def run_embedding_eval(self) -> None:
        report = services.evaluation.run_embedding_eval()
        self.result_table.set_rows(report["rows"])
        self.failure_text.setPlainText(json.dumps(report.get("recommendation", {}), ensure_ascii=False, indent=2))

    def show_report(self, report: dict[str, Any]) -> None:
        for index in reversed(range(self.metrics_grid.count())):
            widget = self.metrics_grid.itemAt(index).widget()
            if widget:
                widget.deleteLater()
        metrics = report["metrics"]
        for idx, (key, value) in enumerate(metrics.items()):
            self.metrics_grid.addWidget(metric_card(key, value), idx // 4, idx % 4)
        self.result_table.set_rows(report["results"])
        failures = [row for row in report["results"] if row["status"] == "fail"]
        self.failure_text.setPlainText("\n\n".join(f"{row['question']}\n原因: {row['failure_reason']}\n建议: 补充 eval set、优化 chunking 或打开 rerank。" for row in failures))
        self.set_status(f"报告: {report['report_path']}")

    def refresh_latest(self) -> None:
        reports = services.evaluation.get_latest_reports()["rag"]
        if reports:
            self.latest_report_id = reports[0]["eval_run_id"]

    def export_report(self) -> None:
        self.refresh_latest()
        if self.latest_report_id:
            path = services.evaluation.export_report(self.latest_report_id, "html")
            self.set_status(f"已导出 {path}")


class SettingsPage(BasePage):
    def __init__(self) -> None:
        super().__init__("设置", "工作区、模式、LLM、向量库和配置导入导出。")
        tabs = QTabWidget()
        tabs.addTab(self._workspace_tab(), "工作区设置")
        tabs.addTab(self._llm_tab(), "LLM 设置")
        tabs.addTab(self._vector_tab(), "向量库设置")
        tabs.addTab(self._configs_tab(), "配置文件入口")
        tabs.addTab(self._import_export_tab(), "导入导出")
        self.root_layout.addWidget(tabs, 1)

    def _workspace_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self.workspace_path = QLineEdit(services.workspace.get_workspace_paths()["workspace_root"])
        self.mode = QComboBox()
        self.mode.addItems(["Demo Mode", "Real Mode"])
        self.mode.setCurrentText(services.workspace.load_config("rag.yaml").get("mode", "Demo Mode"))
        form.addRow("当前 workspace_root", self.workspace_path)
        form.addRow("模式", self.mode)
        form.addRow(button("修改工作区", self.change_workspace))
        form.addRow(button("打开工作区", lambda: services.workspace.open_folder(services.workspace.paths["workspace_root"])))
        form.addRow(button("初始化目录", lambda: (services.workspace.ensure_workspace(), self.set_status("目录已初始化"))))
        form.addRow(button("保存模式", self.save_mode))
        return page

    def _llm_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self.llm_fields: dict[str, QLineEdit] = {}
        config = services.workspace.load_config("llm.yaml")
        for key in ["provider", "model", "base_url", "api_key_env", "temperature", "max_tokens"]:
            field = QLineEdit(str(config.get(key, "")))
            self.llm_fields[key] = field
            form.addRow(key, field)
        form.addRow(button("保存 LLM 设置", self.save_llm))
        form.addRow(button("测试连接", self.test_llm))
        return page

    def _vector_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self.vector_fields: dict[str, QLineEdit] = {}
        config = services.workspace.load_config("vector_store.yaml")
        for key in ["type", "storage_path", "collection_name", "distance_metric", "normalize_embeddings"]:
            field = QLineEdit(str(config.get(key, "")))
            self.vector_fields[key] = field
            form.addRow(key, field)
        form.addRow(button("保存向量库设置", self.save_vector))
        return page

    def _configs_tab(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        self.config_combo = QComboBox()
        for filename in ["cleaning.yaml", "chunking.yaml", "retrieval.yaml", "annotation.yaml", "embedding.yaml", "llm.yaml"]:
            self.config_combo.addItem(filename)
        self.config_combo.currentTextChanged.connect(self.load_config_text)
        side = QVBoxLayout()
        side.addWidget(self.config_combo)
        side.addWidget(button("保存配置", self.save_config_text))
        side.addWidget(button("恢复默认", self.reset_config))
        side.addStretch(1)
        self.config_text = QPlainTextEdit()
        layout.addLayout(side)
        layout.addWidget(self.config_text, 1)
        self.load_config_text()
        return page

    def _import_export_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(button("导出全部配置", lambda: self.set_status(f"已导出 {services.settings.export_configs()}")))
        layout.addWidget(button("导入配置", self.import_configs))
        layout.addWidget(button("恢复默认", self.reset_all))
        layout.addStretch(1)
        return page

    def change_workspace(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择 workspace")
        if folder:
            services.workspace.change_workspace(folder)
            self.workspace_path.setText(folder)

    def save_mode(self) -> None:
        config = services.workspace.load_config("rag.yaml")
        config["mode"] = self.mode.currentText()
        services.workspace.save_config("rag.yaml", config)
        self.set_status("模式已保存")

    def save_llm(self) -> None:
        config = {key: field.text() for key, field in self.llm_fields.items()}
        config["temperature"] = float(config["temperature"])
        config["max_tokens"] = int(config["max_tokens"])
        services.workspace.save_config("llm.yaml", config)
        self.set_status("LLM 设置已保存")

    def test_llm(self) -> None:
        self.message("LLM 测试", json.dumps(services.settings.test_llm_connection(), ensure_ascii=False, indent=2))

    def save_vector(self) -> None:
        config = {key: field.text() for key, field in self.vector_fields.items()}
        config["normalize_embeddings"] = str(config["normalize_embeddings"]).lower() in {"true", "1", "yes"}
        services.workspace.save_config("vector_store.yaml", config)
        self.set_status("向量库设置已保存")

    def load_config_text(self) -> None:
        filename = self.config_combo.currentText()
        self.config_text.setPlainText(yaml.safe_dump(services.workspace.load_config(filename), allow_unicode=True, sort_keys=False))

    def save_config_text(self) -> None:
        data = yaml.safe_load(self.config_text.toPlainText()) or {}
        services.workspace.save_config(self.config_combo.currentText(), data)
        self.set_status("配置已保存")

    def reset_config(self) -> None:
        services.settings.reset_config(self.config_combo.currentText())
        self.load_config_text()

    def import_configs(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "导入配置", "", "JSON (*.json)")
        if path:
            services.settings.import_configs(path)
            self.set_status("配置已导入")

    def reset_all(self) -> None:
        for filename in DEFAULT_CONFIGS:
            services.settings.reset_config(filename)
        self.set_status("已恢复所有默认配置")
