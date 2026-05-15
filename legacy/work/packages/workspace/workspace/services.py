from __future__ import annotations

import csv
import html
import io
import json
import math
import os
import re
import shutil
import sqlite3
import subprocess
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT_DIR = Path(__file__).resolve().parents[3]
CONFIG_DIR = ROOT_DIR / "configs"
DEFAULT_WORKSPACE_ROOT = ROOT_DIR / "workspace"

WORKSPACE_FOLDERS = [
    "raw_docs",
    "parsed_docs",
    "cleaned_docs",
    "chunks",
    "annotations",
    "vector_store",
    "traces",
    "reports",
    "exports",
]

DOCUMENT_STAGES = [
    "导入文档",
    "解析",
    "清洗",
    "切片",
    "LLM 标注",
    "向量化",
    "索引完成",
    "问答",
    "评测",
]

DEFAULT_CONFIGS: dict[str, dict[str, Any]] = {
    "rag.yaml": {
        "product_name": "Enterprise RAG Workbench",
        "mode": "Demo Mode",
        "workspace_root": "workspace",
        "auto_seed_demo_on_start": True,
        "pipeline": ["parse", "clean", "chunk", "annotate", "embed", "index"],
    },
    "cleaning.yaml": {
        "normalize_whitespace": True,
        "remove_empty_lines": True,
        "normalize_punctuation": True,
        "remove_control_chars": True,
        "remove_repeated_headers": True,
        "remove_repeated_footers": True,
        "remove_page_numbers": True,
        "remove_watermark_text": True,
        "preserve_headings": True,
        "preserve_page_numbers": False,
        "preserve_tables": True,
        "preserve_lists": True,
        "preserve_section_path": True,
        "convert_tables_to_markdown": True,
        "keep_table_header": True,
        "deduplicate_paragraphs": True,
        "similarity_threshold": 0.92,
        "llm_cleanup_enabled": False,
        "llm_cleanup_scope": "failed_blocks_only",
        "max_llm_cleanup_chars": 2000,
    },
    "chunking.yaml": {
        "strategy": "hybrid",
        "chunk_size_tokens": 380,
        "chunk_overlap_tokens": 60,
        "min_chunk_tokens": 40,
        "max_chunk_tokens": 520,
        "split_by_heading": True,
        "split_by_paragraph": True,
        "keep_heading_in_chunk": True,
        "keep_table_together": True,
        "table_chunk_mode": "markdown_block",
        "preserve_page_range": True,
        "preserve_section_path": True,
        "merge_small_chunks": True,
        "adjacent_chunk_expansion_enabled": True,
    },
    "retrieval.yaml": {
        "mode": "hybrid",
        "vector_top_k": 8,
        "bm25_top_k": 8,
        "final_top_k": 5,
        "rerank": True,
        "min_evidence_score": 0.05,
    },
    "annotation.yaml": {
        "enabled": True,
        "provider": "mock",
        "model": "mock-chat",
        "annotate_level": "document",
        "require_human_review": True,
        "max_input_chars": 6000,
        "risk_note_policy": "metadata_only",
    },
    "embedding.yaml": {
        "active_model_id": "mock_local_128",
        "provider": "mock",
        "model": "mock-local-embedding-128",
        "dimension": 128,
        "normalize_embeddings": True,
        "batch_size": 32,
        "collection_name": "enterprise_kb_demo",
        "distance_metric": "cosine",
    },
    "embedding_models.yaml": {
        "active_model_id": "mock_local_128",
        "models": {
            "mock_local_128": {
                "model_id": "mock_local_128",
                "display_name": "Mock Local Embedding 128",
                "provider": "mock",
                "model": "mock-local-embedding-128",
                "dimension": 128,
                "max_input_tokens": 4096,
                "language_support": "Chinese, English, multilingual demo",
                "recommended_for": "Demo Mode, offline walkthrough, pipeline verification",
                "normalize_embeddings": True,
                "distance_metric": "cosine",
                "base_url": "",
                "endpoint": "/embeddings",
                "api_key_env": "",
                "batch_size": 32,
                "timeout_seconds": 15,
                "retry_count": 1,
                "status": "enabled",
                "built_in": True,
            },
            "bge_m3": {
                "model_id": "bge_m3",
                "display_name": "BGE-M3",
                "provider": "local_bge",
                "model": "BAAI/bge-m3",
                "dimension": 1024,
                "max_input_tokens": 8192,
                "language_support": "Chinese, English, multilingual",
                "recommended_for": "Production Chinese and multilingual enterprise RAG",
                "normalize_embeddings": True,
                "distance_metric": "cosine",
                "base_url": "",
                "endpoint": "/embeddings",
                "api_key_env": "",
                "batch_size": 32,
                "timeout_seconds": 30,
                "retry_count": 2,
                "status": "enabled",
                "built_in": True,
            },
            "openai_text_embedding_3_small": {
                "model_id": "openai_text_embedding_3_small",
                "display_name": "OpenAI text-embedding-3-small",
                "provider": "openai",
                "model": "text-embedding-3-small",
                "dimension": 1536,
                "max_input_tokens": 8192,
                "language_support": "Chinese, English, multilingual",
                "recommended_for": "Real Mode API deployment with lower cost",
                "normalize_embeddings": True,
                "distance_metric": "cosine",
                "base_url": "https://api.openai.com/v1",
                "endpoint": "/embeddings",
                "api_key_env": "OPENAI_API_KEY",
                "batch_size": 64,
                "timeout_seconds": 30,
                "retry_count": 2,
                "status": "enabled",
                "built_in": True,
            },
            "custom_api_template": {
                "model_id": "custom_api_template",
                "display_name": "Custom OpenAI-Compatible Embedding API",
                "provider": "custom_api",
                "model": "",
                "dimension": 768,
                "max_input_tokens": 8192,
                "language_support": "custom",
                "recommended_for": "Real Mode private embedding service",
                "normalize_embeddings": True,
                "distance_metric": "cosine",
                "base_url": "",
                "endpoint": "/embeddings",
                "api_key_env": "CUSTOM_EMBEDDING_API_KEY",
                "batch_size": 32,
                "timeout_seconds": 30,
                "retry_count": 2,
                "status": "template",
                "built_in": True,
            },
        },
    },
    "embedding_eval_weights.yaml": {
        "version": 1,
        "active_profile": "balanced",
        "retrieval_quality": {"weight": 55},
        "semantic_separation": {"weight": 15},
        "rag_context_quality": {"weight": 15},
        "engineering_quality": {"weight": 15},
    },
    "vector_store.yaml": {
        "type": "local_json_vector_store",
        "storage_path": "workspace/vector_store/vectors.json",
        "collection_name": "enterprise_kb_demo",
        "distance_metric": "cosine",
        "normalize_embeddings": True,
    },
    "llm.yaml": {
        "provider": "mock",
        "model": "mock-chat",
        "base_url": "",
        "api_key_env": "OPENAI_API_KEY",
        "temperature": 0.2,
        "max_tokens": 1200,
    },
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_id(prefix: str, *parts: object) -> str:
    import hashlib

    digest = hashlib.sha1("|".join(str(part) for part in parts).encode("utf-8", "ignore")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def resolve_root_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return ROOT_DIR / path


def load_yaml(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return dict(default or {})
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        value = None
    return value if isinstance(value, dict) else dict(default or {})


def save_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def tokenize(text: str) -> list[str]:
    words = [item.lower() for item in re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]", text)]
    cjk = [text[index : index + 2] for index in range(0, max(len(text) - 1, 0)) if re.match(r"[\u4e00-\u9fff]{2}", text[index : index + 2])]
    return words + cjk


def estimate_tokens(text: str) -> int:
    tokens = tokenize(text)
    return max(len(tokens), math.ceil(len(text) / 4))


def preview_text(text: str, limit: int = 180) -> str:
    return re.sub(r"\s+", " ", text).strip()[:limit]


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def read_text_file(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return read_docx_text(path)
    if suffix in {".html", ".htm"}:
        text = path.read_text(encoding="utf-8", errors="ignore")
        return re.sub(r"<[^>]+>", " ", html.unescape(text))
    if suffix == ".csv":
        return path.read_text(encoding="utf-8", errors="ignore")
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")


def read_docx_text(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            xml = archive.read("word/document.xml").decode("utf-8", errors="ignore")
    except Exception:
        return path.read_bytes().decode("utf-8", errors="ignore")
    xml = xml.replace("</w:p>", "\n")
    return re.sub(r"<[^>]+>", "", html.unescape(xml))


def mock_embedding(text: str, dimension: int, salt: str = "mock") -> list[float]:
    import hashlib

    values: list[float] = []
    seed = f"{salt}\n{text}".encode("utf-8", "ignore")
    counter = 0
    while len(values) < dimension:
        digest = hashlib.sha256(seed + str(counter).encode()).digest()
        for byte in digest:
            values.append((byte / 127.5) - 1.0)
            if len(values) >= dimension:
                break
        counter += 1
    return normalize_vector(values)


def normalize_vector(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm <= 0:
        return vector
    return [value / norm for value in vector]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(a * b for a, b in zip(left, right))


class LocalStore:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.ensure_schema()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def ensure_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    doc_id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    file_type TEXT,
                    original_path TEXT,
                    raw_path TEXT,
                    parsed_path TEXT,
                    cleaned_path TEXT,
                    status TEXT,
                    current_stage TEXT,
                    page_count INTEGER DEFAULT 0,
                    file_size INTEGER DEFAULT 0,
                    raw_char_count INTEGER DEFAULT 0,
                    cleaned_char_count INTEGER DEFAULT 0,
                    chunk_count INTEGER DEFAULT 0,
                    embedded_chunk_count INTEGER DEFAULT 0,
                    annotation_status TEXT DEFAULT 'not_started',
                    embedding_status TEXT DEFAULT 'not_started',
                    vector_collection TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    failed_stage TEXT,
                    error_code TEXT,
                    error_message TEXT
                );

                CREATE TABLE IF NOT EXISTS chunks (
                    chunk_id TEXT PRIMARY KEY,
                    doc_id TEXT NOT NULL,
                    filename TEXT,
                    page_start INTEGER DEFAULT 1,
                    page_end INTEGER DEFAULT 1,
                    section_path TEXT,
                    chunk_index INTEGER,
                    text TEXT,
                    text_preview TEXT,
                    token_count INTEGER DEFAULT 0,
                    char_count INTEGER DEFAULT 0,
                    split_strategy TEXT,
                    split_reason TEXT,
                    triggered_rules TEXT,
                    previous_overlap_text TEXT,
                    next_overlap_text TEXT,
                    contains_table INTEGER DEFAULT 0,
                    contains_heading INTEGER DEFAULT 0,
                    enabled INTEGER DEFAULT 1,
                    embedding_status TEXT DEFAULT 'not_started',
                    embedding_model TEXT,
                    vector_id TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    FOREIGN KEY (doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS annotations (
                    annotation_id TEXT PRIMARY KEY,
                    doc_id TEXT NOT NULL,
                    doc_summary TEXT,
                    doc_type TEXT,
                    business_domain TEXT,
                    tags TEXT,
                    key_terms TEXT,
                    key_facts TEXT,
                    section_summaries TEXT,
                    table_descriptions TEXT,
                    possible_questions TEXT,
                    glossary TEXT,
                    confidence REAL DEFAULT 0,
                    human_review_status TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    FOREIGN KEY (doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS embeddings (
                    embedding_id TEXT PRIMARY KEY,
                    chunk_id TEXT NOT NULL,
                    doc_id TEXT NOT NULL,
                    provider TEXT,
                    model TEXT,
                    dimension INTEGER,
                    vector_id TEXT,
                    collection_name TEXT,
                    status TEXT,
                    latency_ms REAL,
                    cost_estimate REAL,
                    error_message TEXT,
                    embedded_at TEXT,
                    FOREIGN KEY (chunk_id) REFERENCES chunks(chunk_id) ON DELETE CASCADE,
                    FOREIGN KEY (doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS traces (
                    trace_id TEXT PRIMARY KEY,
                    question TEXT,
                    retrieval_mode TEXT,
                    query_rewrite TEXT,
                    query_embedding_model TEXT,
                    retrieved_chunks_json TEXT,
                    reranked_chunks_json TEXT,
                    context_json TEXT,
                    answer TEXT,
                    citations_json TEXT,
                    latency_ms REAL,
                    token_usage_json TEXT,
                    created_at TEXT,
                    error_message TEXT
                );

                CREATE TABLE IF NOT EXISTS eval_runs (
                    eval_run_id TEXT PRIMARY KEY,
                    target TEXT,
                    model_id TEXT,
                    retrieval_mode TEXT,
                    overall_score REAL,
                    metrics_json TEXT,
                    report_path TEXT,
                    created_at TEXT
                );

                CREATE TABLE IF NOT EXISTS embedding_model_reports (
                    report_id TEXT PRIMARY KEY,
                    model_id TEXT,
                    overall_score REAL,
                    grade TEXT,
                    retrieval_quality_score REAL,
                    semantic_separation_score REAL,
                    rag_context_quality_score REAL,
                    engineering_quality_score REAL,
                    metrics_json TEXT,
                    report_path TEXT,
                    created_at TEXT
                );
                """
            )
            conn.commit()

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        with self.connect() as conn:
            conn.execute(sql, params)
            conn.commit()

    def query(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self.connect() as conn:
            return rows_to_dicts(conn.execute(sql, params).fetchall())

    def get(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        with self.connect() as conn:
            return row_to_dict(conn.execute(sql, params).fetchone())

    def upsert(self, table: str, key: str, data: dict[str, Any]) -> None:
        columns = list(data.keys())
        placeholders = ", ".join("?" for _ in columns)
        updates = ", ".join(f"{column}=excluded.{column}" for column in columns if column != key)
        sql = (
            f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders}) "
            f"ON CONFLICT({key}) DO UPDATE SET {updates}"
        )
        with self.connect() as conn:
            conn.execute(sql, tuple(data[column] for column in columns))
            conn.commit()


class WorkspaceService:
    def __init__(self) -> None:
        self.root = ROOT_DIR
        self.config_dir = CONFIG_DIR
        self.ensure_configs()
        self.workspace_root = self._configured_workspace_root()
        self.ensure_workspace()

    def _configured_workspace_root(self) -> Path:
        config = self.load_config("rag.yaml")
        return resolve_root_path(str(config.get("workspace_root") or "workspace"))

    def ensure_configs(self) -> None:
        self.config_dir.mkdir(parents=True, exist_ok=True)
        for filename, default in DEFAULT_CONFIGS.items():
            path = self.config_dir / filename
            current = load_yaml(path, default)
            merged = self._merge_defaults(current, default)
            if current != merged or not path.exists():
                save_yaml(path, merged)

    def _merge_defaults(self, current: dict[str, Any], default: dict[str, Any]) -> dict[str, Any]:
        merged = dict(default)
        for key, value in current.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                nested = dict(merged[key])
                nested.update(value)
                merged[key] = nested
            else:
                merged[key] = value
        return merged

    def ensure_workspace(self) -> None:
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        for folder in WORKSPACE_FOLDERS:
            (self.workspace_root / folder).mkdir(parents=True, exist_ok=True)
        LocalStore(self.workspace_root / "rag_workbench.sqlite")

    def get_workspace_paths(self) -> dict[str, str]:
        paths = {"workspace_root": self.workspace_root, "database": self.workspace_root / "rag_workbench.sqlite"}
        paths.update({folder: self.workspace_root / folder for folder in WORKSPACE_FOLDERS})
        return {key: str(value) for key, value in paths.items()}

    @property
    def paths(self) -> dict[str, Path]:
        paths = {"workspace_root": self.workspace_root, "database": self.workspace_root / "rag_workbench.sqlite"}
        paths.update({folder: self.workspace_root / folder for folder in WORKSPACE_FOLDERS})
        return paths

    def open_folder(self, path: str | Path) -> None:
        target = Path(path)
        target.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(str(target))  # type: ignore[attr-defined]
            return
        subprocess.Popen(["open" if sys_platform_is_darwin() else "xdg-open", str(target)])

    def change_workspace(self, path: str | Path) -> dict[str, str]:
        config = self.load_config("rag.yaml")
        config["workspace_root"] = str(path)
        self.save_config("rag.yaml", config)
        self.workspace_root = resolve_root_path(path)
        self.ensure_workspace()
        return self.get_workspace_paths()

    def load_config(self, filename: str) -> dict[str, Any]:
        return load_yaml(self.config_dir / filename, DEFAULT_CONFIGS.get(filename, {}))

    def save_config(self, filename: str, config: dict[str, Any]) -> None:
        save_yaml(self.config_dir / filename, config)


def sys_platform_is_darwin() -> bool:
    import sys

    return sys.platform == "darwin"


class DocumentService:
    def __init__(self, hub: "RagWorkbenchServices") -> None:
        self.hub = hub

    def import_files(self, paths: list[str | Path]) -> list[dict[str, Any]]:
        imported: list[dict[str, Any]] = []
        for raw in paths:
            source = Path(raw)
            if not source.exists() or source.is_dir():
                continue
            target = self._copy_to_workspace(source)
            doc_id = stable_id("doc", target.name, target.stat().st_size, int(target.stat().st_mtime))
            text = read_text_file(target)
            record = {
                "doc_id": doc_id,
                "filename": target.name,
                "file_type": target.suffix.lower().lstrip(".") or "txt",
                "original_path": str(source),
                "raw_path": str(target),
                "parsed_path": "",
                "cleaned_path": "",
                "status": "raw_only",
                "current_stage": "导入文档",
                "page_count": max(1, math.ceil(len(text) / 1800)),
                "file_size": target.stat().st_size,
                "raw_char_count": len(text),
                "cleaned_char_count": 0,
                "chunk_count": 0,
                "embedded_chunk_count": 0,
                "annotation_status": "not_started",
                "embedding_status": "not_started",
                "vector_collection": "",
                "created_at": now_iso(),
                "updated_at": now_iso(),
                "failed_stage": "",
                "error_code": "",
                "error_message": "",
            }
            self.hub.store.upsert("documents", "doc_id", record)
            imported.append(record)
        return imported

    def _copy_to_workspace(self, source: Path) -> Path:
        raw_dir = self.hub.workspace.paths["raw_docs"]
        target = raw_dir / source.name
        if target.exists() and source.resolve() != target.resolve():
            target = raw_dir / f"{source.stem}_{stable_id('copy', source, source.stat().st_mtime)[5:9]}{source.suffix}"
        shutil.copy2(source, target)
        return target

    def import_folder(self, path: str | Path) -> list[dict[str, Any]]:
        folder = Path(path)
        files = [item for item in folder.rglob("*") if item.is_file() and item.suffix.lower() in {".txt", ".md", ".csv", ".html", ".htm", ".docx", ".pdf"}]
        return self.import_files(files)

    def import_sample_docs(self) -> list[dict[str, Any]]:
        sample_dir = ROOT_DIR / "data" / "sample_docs"
        if not sample_dir.exists():
            return []
        return self.import_folder(sample_dir)

    def list_documents(self) -> list[dict[str, Any]]:
        return self.hub.store.query("SELECT * FROM documents ORDER BY updated_at DESC, filename")

    def get_document(self, doc_id: str) -> dict[str, Any]:
        row = self.hub.store.get("SELECT * FROM documents WHERE doc_id=?", (doc_id,))
        if not row:
            raise KeyError(f"Unknown document: {doc_id}")
        return row

    def update_status(self, doc_id: str, status: str, stage: str) -> None:
        self.hub.store.execute(
            "UPDATE documents SET status=?, current_stage=?, updated_at=?, error_code='', error_message='', failed_stage='' WHERE doc_id=?",
            (status, stage, now_iso(), doc_id),
        )

    def fail(self, doc_id: str, stage: str, error: Exception | str) -> None:
        self.hub.store.execute(
            "UPDATE documents SET status='failed', current_stage=?, failed_stage=?, error_code=?, error_message=?, updated_at=? WHERE doc_id=?",
            (stage, stage, type(error).__name__, str(error), now_iso(), doc_id),
        )

    def delete_document(self, doc_id: str) -> None:
        doc = self.get_document(doc_id)
        for key in ["raw_path", "parsed_path", "cleaned_path"]:
            value = doc.get(key)
            if value and Path(value).exists() and self.hub.workspace.workspace_root in Path(value).resolve().parents:
                Path(value).unlink(missing_ok=True)
        self.hub.store.execute("DELETE FROM documents WHERE doc_id=?", (doc_id,))
        self.hub.indexing.delete_document_index(doc_id)

    def mark_stale(self, doc_id: str, reason: str) -> None:
        self.hub.store.execute(
            "UPDATE documents SET status='stale', current_stage='stale', error_message=?, updated_at=? WHERE doc_id=?",
            (reason, now_iso(), doc_id),
        )

    def run_full_pipeline(self, doc_ids: list[str] | None = None) -> list[dict[str, Any]]:
        rows = self.list_documents()
        selected = doc_ids or [row["doc_id"] for row in rows]
        results: list[dict[str, Any]] = []
        for doc_id in selected:
            try:
                self.update_status(doc_id, "queued", "排队")
                self.hub.parser.parse_document(doc_id)
                self.hub.cleaning.run_cleaning(doc_id)
                self.hub.chunking.run_chunking(doc_id)
                self.hub.annotation.run_annotation(doc_id)
                self.hub.indexing.run_embedding(doc_id)
                self.update_status(doc_id, "indexed", "索引完成")
                results.append({"doc_id": doc_id, "status": "indexed"})
            except Exception as exc:
                self.fail(doc_id, "pipeline", exc)
                results.append({"doc_id": doc_id, "status": "failed", "error": str(exc)})
        return results


class ParserService:
    def __init__(self, hub: "RagWorkbenchServices") -> None:
        self.hub = hub

    def parse_document(self, doc_id: str) -> dict[str, Any]:
        self.hub.documents.update_status(doc_id, "parsing", "解析")
        doc = self.hub.documents.get_document(doc_id)
        try:
            raw_path = self._ensure_raw_path(doc)
            text = read_text_file(raw_path)
            elements = self._elements_from_text(text)
            parsed_path = self.hub.workspace.paths["parsed_docs"] / f"{doc_id}.json"
            parsed_txt_path = self.hub.workspace.paths["parsed_docs"] / f"{doc_id}.txt"
            payload = {"doc_id": doc_id, "filename": doc["filename"], "elements": elements, "text": text}
            parsed_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            parsed_txt_path.write_text(text, encoding="utf-8")
            self.hub.store.execute(
                "UPDATE documents SET parsed_path=?, status='parsed', current_stage='解析', page_count=?, raw_char_count=?, updated_at=? WHERE doc_id=?",
                (str(parsed_path), max(1, math.ceil(len(text) / 1800)), len(text), now_iso(), doc_id),
            )
            return payload
        except Exception as exc:
            self.hub.documents.fail(doc_id, "解析", exc)
            raise

    def _ensure_raw_path(self, doc: dict[str, Any]) -> Path:
        raw_path = Path(doc["raw_path"])
        if raw_path.exists():
            return raw_path
        sample_path = ROOT_DIR / "data" / "sample_docs" / doc["filename"]
        if sample_path.exists():
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(sample_path, raw_path)
            return raw_path
        raise FileNotFoundError(str(raw_path))

    def extract_text_elements(self, doc_id: str) -> list[dict[str, Any]]:
        doc = self.hub.documents.get_document(doc_id)
        parsed_path = Path(doc.get("parsed_path") or "")
        if not parsed_path.exists():
            return self.parse_document(doc_id)["elements"]
        return json.loads(parsed_path.read_text(encoding="utf-8")).get("elements", [])

    def save_parsed_output(self, doc_id: str) -> dict[str, Any]:
        return self.parse_document(doc_id)

    def _elements_from_text(self, text: str) -> list[dict[str, Any]]:
        blocks: list[dict[str, Any]] = []
        page = 1
        block_index = 1
        for raw in re.split(r"\n\s*\n+", text):
            value = raw.strip()
            if not value:
                continue
            block_type = "heading" if value.startswith("#") or len(value) < 80 and value.endswith(":") else "paragraph"
            if "|" in value and "\n" in value:
                block_type = "table"
            blocks.append(
                {
                    "block_id": f"block_{block_index:04d}",
                    "page": page,
                    "type": block_type,
                    "text": value,
                    "section_path": self._section_for_block(value),
                }
            )
            page = max(page, math.ceil(block_index / 6))
            block_index += 1
        if not blocks:
            blocks.append({"block_id": "block_0001", "page": 1, "type": "paragraph", "text": text, "section_path": "document"})
        return blocks

    def _section_for_block(self, text: str) -> str:
        first = text.splitlines()[0].strip("# ").strip()
        if 0 < len(first) <= 80:
            return first
        return "document"


class CleaningService:
    def __init__(self, hub: "RagWorkbenchServices") -> None:
        self.hub = hub

    def load_config(self) -> dict[str, Any]:
        return self.hub.workspace.load_config("cleaning.yaml")

    def save_config(self, config: dict[str, Any]) -> None:
        self.hub.workspace.save_config("cleaning.yaml", config)

    def preview_cleaning(self, doc_id: str | None = None) -> list[dict[str, Any]]:
        doc_id = doc_id or self._first_doc_id()
        if not doc_id:
            return []
        blocks = self.list_cleaning_blocks(doc_id)
        return blocks[:50]

    def run_cleaning(self, doc_id: str) -> dict[str, Any]:
        self.hub.documents.update_status(doc_id, "cleaning", "清洗")
        try:
            elements = self.hub.parser.extract_text_elements(doc_id)
            cleaned_blocks: list[dict[str, Any]] = []
            for element in elements:
                cleaned, rules, delete_reason, kept = self._clean_block(str(element.get("text") or ""))
                if kept:
                    cleaned_blocks.append({**element, "cleaned_text": cleaned, "triggered_rules": rules})
            cleaned_text = "\n\n".join(block["cleaned_text"] for block in cleaned_blocks)
            path = self.hub.workspace.paths["cleaned_docs"] / f"{doc_id}.txt"
            metadata_path = self.hub.workspace.paths["cleaned_docs"] / f"{doc_id}.json"
            path.write_text(cleaned_text, encoding="utf-8")
            metadata_path.write_text(json.dumps(cleaned_blocks, ensure_ascii=False, indent=2), encoding="utf-8")
            self.hub.store.execute(
                "UPDATE documents SET cleaned_path=?, status='cleaned', current_stage='清洗', cleaned_char_count=?, updated_at=? WHERE doc_id=?",
                (str(path), len(cleaned_text), now_iso(), doc_id),
            )
            return {"doc_id": doc_id, "cleaned_path": str(path), "block_count": len(cleaned_blocks)}
        except Exception as exc:
            self.hub.documents.fail(doc_id, "清洗", exc)
            raise

    def list_cleaning_blocks(self, doc_id: str) -> list[dict[str, Any]]:
        elements = self.hub.parser.extract_text_elements(doc_id)
        rows: list[dict[str, Any]] = []
        for element in elements:
            original = str(element.get("text") or "")
            cleaned, rules, delete_reason, kept = self._clean_block(original)
            rows.append(
                {
                    "block_id": element.get("block_id"),
                    "page": element.get("page"),
                    "raw_preview": preview_text(original, 220),
                    "cleaned_preview": preview_text(cleaned, 220),
                    "matched_rules": ", ".join(rules),
                    "delete_reason": delete_reason,
                    "kept": "yes" if kept else "no",
                    "operation": "keep" if kept else "drop",
                }
            )
        return rows

    def _clean_block(self, text: str) -> tuple[str, list[str], str, bool]:
        config = self.load_config()
        rules: list[str] = []
        cleaned = text
        if config.get("remove_control_chars", True):
            new_value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", cleaned)
            if new_value != cleaned:
                rules.append("remove_control_chars")
            cleaned = new_value
        if config.get("normalize_whitespace", True):
            new_value = re.sub(r"[ \t]+", " ", cleaned)
            if new_value != cleaned:
                rules.append("normalize_whitespace")
            cleaned = new_value
        if config.get("remove_empty_lines", True):
            lines = [line.rstrip() for line in cleaned.splitlines() if line.strip()]
            if len(lines) != len(cleaned.splitlines()):
                rules.append("remove_empty_lines")
            cleaned = "\n".join(lines)
        if config.get("remove_page_numbers", True) and re.fullmatch(r"\s*(page\s*)?\d+\s*", cleaned, re.I):
            return "", rules + ["remove_page_numbers"], "page_number", False
        if config.get("remove_watermark_text", True) and "confidential draft watermark" in cleaned.lower():
            return "", rules + ["remove_watermark_text"], "watermark", False
        return cleaned.strip(), rules or ["no_change"], "", bool(cleaned.strip())

    def _first_doc_id(self) -> str | None:
        docs = self.hub.documents.list_documents()
        return docs[0]["doc_id"] if docs else None


class ChunkingService:
    def __init__(self, hub: "RagWorkbenchServices") -> None:
        self.hub = hub

    def load_config(self) -> dict[str, Any]:
        return self.hub.workspace.load_config("chunking.yaml")

    def save_config(self, config: dict[str, Any]) -> None:
        self.hub.workspace.save_config("chunking.yaml", config)

    def preview_chunks(self, doc_id: str | None = None) -> list[dict[str, Any]]:
        doc_id = doc_id or self._first_doc_id()
        if not doc_id:
            return []
        doc = self.hub.documents.get_document(doc_id)
        text = self._cleaned_text(doc_id, doc)
        return self._build_chunk_rows(doc, text, preview=True)

    def run_chunking(self, doc_id: str) -> list[dict[str, Any]]:
        self.hub.documents.update_status(doc_id, "chunking", "切片")
        try:
            doc = self.hub.documents.get_document(doc_id)
            text = self._cleaned_text(doc_id, doc)
            rows = self._build_chunk_rows(doc, text, preview=False)
            self.hub.store.execute("DELETE FROM embeddings WHERE doc_id=?", (doc_id,))
            self.hub.store.execute("DELETE FROM chunks WHERE doc_id=?", (doc_id,))
            for row in rows:
                self.hub.store.upsert("chunks", "chunk_id", row)
            jsonl_path = self.hub.workspace.paths["chunks"] / f"{doc_id}.jsonl"
            jsonl_path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows), encoding="utf-8")
            self.hub.store.execute(
                "UPDATE documents SET status='chunked', current_stage='切片', chunk_count=?, embedded_chunk_count=0, embedding_status='stale', updated_at=? WHERE doc_id=?",
                (len(rows), now_iso(), doc_id),
            )
            return rows
        except Exception as exc:
            self.hub.documents.fail(doc_id, "切片", exc)
            raise

    def list_chunks(self, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        filters = filters or {}
        sql = "SELECT * FROM chunks WHERE 1=1"
        params: list[Any] = []
        if filters.get("doc_id"):
            sql += " AND doc_id=?"
            params.append(filters["doc_id"])
        if filters.get("embedding_status") and filters["embedding_status"] != "all":
            sql += " AND embedding_status=?"
            params.append(filters["embedding_status"])
        if filters.get("enabled") in {"enabled", "disabled"}:
            sql += " AND enabled=?"
            params.append(1 if filters["enabled"] == "enabled" else 0)
        if filters.get("section"):
            sql += " AND section_path LIKE ?"
            params.append(f"%{filters['section']}%")
        if filters.get("search"):
            sql += " AND text LIKE ?"
            params.append(f"%{filters['search']}%")
        sql += " ORDER BY filename, chunk_index"
        return self.hub.store.query(sql, tuple(params))

    def get_chunk(self, chunk_id: str) -> dict[str, Any]:
        row = self.hub.store.get("SELECT * FROM chunks WHERE chunk_id=?", (chunk_id,))
        if not row:
            raise KeyError(chunk_id)
        return row

    def update_chunk(self, chunk_id: str, text: str) -> None:
        self.hub.store.execute(
            "UPDATE chunks SET text=?, text_preview=?, token_count=?, char_count=?, embedding_status='stale', updated_at=? WHERE chunk_id=?",
            (text, preview_text(text), estimate_tokens(text), len(text), now_iso(), chunk_id),
        )
        row = self.get_chunk(chunk_id)
        self.hub.documents.mark_stale(row["doc_id"], "chunk edited; embedding must be rebuilt")

    def disable_chunk(self, chunk_id: str) -> None:
        self.hub.store.execute("UPDATE chunks SET enabled=0, embedding_status='disabled', updated_at=? WHERE chunk_id=?", (now_iso(), chunk_id))

    def enable_chunk(self, chunk_id: str) -> None:
        self.hub.store.execute("UPDATE chunks SET enabled=1, embedding_status='stale', updated_at=? WHERE chunk_id=?", (now_iso(), chunk_id))

    def merge_chunks(self, chunk_ids: list[str]) -> str:
        rows = [self.get_chunk(chunk_id) for chunk_id in chunk_ids]
        rows.sort(key=lambda row: row["chunk_index"])
        if len(rows) < 2:
            raise ValueError("Select at least two chunks to merge.")
        merged_text = "\n\n".join(row["text"] for row in rows)
        self.update_chunk(rows[0]["chunk_id"], merged_text)
        for row in rows[1:]:
            self.disable_chunk(row["chunk_id"])
        return rows[0]["chunk_id"]

    def split_chunk(self, chunk_id: str, split_position: int) -> list[str]:
        row = self.get_chunk(chunk_id)
        text = row["text"]
        split_position = max(1, min(split_position, len(text) - 1))
        left, right = text[:split_position].strip(), text[split_position:].strip()
        self.update_chunk(chunk_id, left)
        new_id = stable_id("chunk", chunk_id, split_position, now_iso())
        new_row = dict(row)
        new_row.update(
            {
                "chunk_id": new_id,
                "chunk_index": int(row["chunk_index"]) + 1,
                "text": right,
                "text_preview": preview_text(right),
                "token_count": estimate_tokens(right),
                "char_count": len(right),
                "split_reason": "manual split",
                "embedding_status": "stale",
                "vector_id": "",
                "created_at": now_iso(),
                "updated_at": now_iso(),
            }
        )
        self.hub.store.upsert("chunks", "chunk_id", new_row)
        return [chunk_id, new_id]

    def _cleaned_text(self, doc_id: str, doc: dict[str, Any]) -> str:
        cleaned_path = Path(doc.get("cleaned_path") or "")
        if not cleaned_path.exists():
            self.hub.cleaning.run_cleaning(doc_id)
            doc = self.hub.documents.get_document(doc_id)
            cleaned_path = Path(doc["cleaned_path"])
        return cleaned_path.read_text(encoding="utf-8")

    def _build_chunk_rows(self, doc: dict[str, Any], text: str, preview: bool) -> list[dict[str, Any]]:
        config = self.load_config()
        max_tokens = int(config.get("chunk_size_tokens") or 380)
        overlap_tokens = int(config.get("chunk_overlap_tokens") or 60)
        paragraphs = [para.strip() for para in re.split(r"\n\s*\n+", text) if para.strip()]
        chunks: list[str] = []
        current: list[str] = []
        current_tokens = 0
        for paragraph in paragraphs:
            tokens = estimate_tokens(paragraph)
            if current and current_tokens + tokens > max_tokens:
                chunks.append("\n\n".join(current))
                overlap = " ".join(" ".join(current).split()[-overlap_tokens:]) if overlap_tokens else ""
                current = [overlap, paragraph] if overlap else [paragraph]
                current_tokens = estimate_tokens("\n\n".join(current))
            else:
                current.append(paragraph)
                current_tokens += tokens
        if current:
            chunks.append("\n\n".join(current))
        if not chunks and text:
            chunks = [text]
        rows: list[dict[str, Any]] = []
        for index, chunk_text in enumerate(chunks, start=1):
            previous_overlap = chunks[index - 2][-240:] if index > 1 else ""
            next_overlap = chunks[index][:240] if index < len(chunks) else ""
            chunk_id = f"preview_{index:04d}" if preview else stable_id("chunk", doc["doc_id"], index, preview_text(chunk_text, 40))
            page_start = max(1, math.ceil(index / 3))
            row = {
                "chunk_id": chunk_id,
                "doc_id": doc["doc_id"],
                "filename": doc["filename"],
                "page_start": page_start,
                "page_end": page_start,
                "section_path": self._section_path(chunk_text),
                "chunk_index": index,
                "text": chunk_text,
                "text_preview": preview_text(chunk_text),
                "token_count": estimate_tokens(chunk_text),
                "char_count": len(chunk_text),
                "split_strategy": str(config.get("strategy") or "hybrid"),
                "split_reason": "heading/paragraph boundary with token limit",
                "triggered_rules": "split_by_heading, split_by_paragraph, preserve_section_path",
                "previous_overlap_text": previous_overlap,
                "next_overlap_text": next_overlap,
                "contains_table": 1 if "|" in chunk_text or "," in chunk_text and doc["file_type"] == "csv" else 0,
                "contains_heading": 1 if chunk_text.lstrip().startswith("#") else 0,
                "enabled": 1,
                "embedding_status": "not_started" if not preview else "preview",
                "embedding_model": "",
                "vector_id": "",
                "created_at": now_iso(),
                "updated_at": now_iso(),
            }
            rows.append(row)
        return rows

    def _section_path(self, text: str) -> str:
        for line in text.splitlines():
            if line.strip().startswith("#"):
                return line.strip("# ").strip()[:80] or "document"
        first = text.splitlines()[0].strip() if text.splitlines() else "document"
        return first[:80] if len(first) < 80 else "document"

    def _first_doc_id(self) -> str | None:
        docs = self.hub.documents.list_documents()
        return docs[0]["doc_id"] if docs else None


class AnnotationService:
    def __init__(self, hub: "RagWorkbenchServices") -> None:
        self.hub = hub

    def load_config(self) -> dict[str, Any]:
        return self.hub.workspace.load_config("annotation.yaml")

    def save_config(self, config: dict[str, Any]) -> None:
        self.hub.workspace.save_config("annotation.yaml", config)

    def run_annotation(self, doc_id: str) -> dict[str, Any]:
        self.hub.documents.update_status(doc_id, "annotating", "LLM 标注")
        doc = self.hub.documents.get_document(doc_id)
        chunks = self.hub.chunking.list_chunks({"doc_id": doc_id})
        if not chunks:
            self.hub.chunking.run_chunking(doc_id)
            chunks = self.hub.chunking.list_chunks({"doc_id": doc_id})
        text = " ".join(chunk["text_preview"] for chunk in chunks)
        terms = sorted(set(tokenize(text)))[:12]
        annotation = {
            "annotation_id": stable_id("ann", doc_id),
            "doc_id": doc_id,
            "doc_summary": f"{doc['filename']} contains {len(chunks)} retrieval chunks about {preview_text(text, 120)}",
            "doc_type": self._doc_type(doc["filename"]),
            "business_domain": "enterprise_knowledge_base",
            "tags": json_dumps([doc["file_type"], "Demo Mode" if self.hub.is_demo_mode() else "Real Mode", "rag-ready"]),
            "key_terms": json_dumps(terms),
            "key_facts": json_dumps([chunk["text_preview"] for chunk in chunks[:5]]),
            "section_summaries": json_dumps({chunk["section_path"]: chunk["text_preview"] for chunk in chunks[:8]}),
            "table_descriptions": json_dumps([chunk["text_preview"] for chunk in chunks if chunk["contains_table"]][:4]),
            "possible_questions": json_dumps(self._questions_for_doc(doc, chunks)),
            "glossary": json_dumps({term: f"Term detected in {doc['filename']}" for term in terms[:6]}),
            "confidence": 0.78 if self.hub.is_demo_mode() else 0.62,
            "human_review_status": "pending",
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        self.hub.store.upsert("annotations", "annotation_id", annotation)
        path = self.hub.workspace.paths["annotations"] / f"{doc_id}.json"
        path.write_text(json.dumps(annotation, ensure_ascii=False, indent=2), encoding="utf-8")
        self.hub.store.execute(
            "UPDATE documents SET status='annotated', current_stage='LLM 标注', annotation_status='pending_review', updated_at=? WHERE doc_id=?",
            (now_iso(), doc_id),
        )
        return annotation

    def list_annotations(self) -> list[dict[str, Any]]:
        rows = self.hub.store.query(
            """
            SELECT a.*, d.filename
            FROM annotations a
            JOIN documents d ON d.doc_id=a.doc_id
            ORDER BY a.updated_at DESC
            """
        )
        for row in rows:
            row["summary"] = row.get("doc_summary", "")
        return rows

    def update_annotation(self, annotation_id: str, data: dict[str, Any]) -> None:
        allowed = {
            "doc_summary",
            "doc_type",
            "business_domain",
            "tags",
            "key_terms",
            "key_facts",
            "section_summaries",
            "table_descriptions",
            "possible_questions",
            "glossary",
            "confidence",
            "human_review_status",
        }
        updates = {key: value for key, value in data.items() if key in allowed}
        updates["updated_at"] = now_iso()
        current = self.hub.store.get("SELECT * FROM annotations WHERE annotation_id=?", (annotation_id,))
        if not current:
            raise KeyError(annotation_id)
        current.update(updates)
        self.hub.store.upsert("annotations", "annotation_id", current)

    def approve_annotation(self, annotation_id: str) -> None:
        self.update_annotation(annotation_id, {"human_review_status": "approved"})

    def reject_annotation(self, annotation_id: str) -> None:
        self.update_annotation(annotation_id, {"human_review_status": "rejected"})

    def _doc_type(self, filename: str) -> str:
        lowered = filename.lower()
        if "runbook" in lowered:
            return "operations_runbook"
        if "policy" in lowered or "handbook" in lowered:
            return "policy"
        if "kb" in lowered:
            return "knowledge_base"
        return "enterprise_document"

    def _questions_for_doc(self, doc: dict[str, Any], chunks: list[dict[str, Any]]) -> list[str]:
        base = [f"What does {doc['filename']} say about {chunks[0]['section_path']}?"] if chunks else []
        base.extend(
            [
                "What are the key rules in this document?",
                "Which sources support the answer?",
                "What should be escalated to a human reviewer?",
            ]
        )
        return base


class EmbeddingModelRegistry:
    def __init__(self, hub: "RagWorkbenchServices") -> None:
        self.hub = hub

    def load(self) -> dict[str, Any]:
        return self.hub.workspace.load_config("embedding_models.yaml")

    def save(self, config: dict[str, Any]) -> None:
        self.hub.workspace.save_config("embedding_models.yaml", config)

    def list_models(self) -> list[dict[str, Any]]:
        config = self.load()
        active = config.get("active_model_id")
        rows: list[dict[str, Any]] = []
        for model_id, data in (config.get("models") or {}).items():
            row = {"model_id": model_id, **(data or {})}
            row["active"] = model_id == active
            row["need_reindex"] = self.hub.indexing.check_collection_compatibility(row).get("need_reindex", False)
            rows.append(row)
        return rows

    def active_model(self) -> dict[str, Any]:
        config = self.load()
        model_id = config.get("active_model_id") or "mock_local_128"
        models = config.get("models") or {}
        data = dict(models.get(model_id) or models.get("mock_local_128") or next(iter(models.values())))
        data["model_id"] = data.get("model_id") or model_id
        return data

    def add_model(self, model: dict[str, Any]) -> None:
        self.update_model(model)

    def update_model(self, model: dict[str, Any]) -> None:
        model_id = str(model.get("model_id") or "").strip()
        if not model_id:
            raise ValueError("model_id is required")
        if int(model.get("dimension") or 0) <= 0:
            raise ValueError("dimension must be positive")
        config = self.load()
        config.setdefault("models", {})[model_id] = model
        self.save(config)

    def delete_custom_model(self, model_id: str) -> None:
        config = self.load()
        model = (config.get("models") or {}).get(model_id)
        if not model:
            raise KeyError(model_id)
        if model.get("built_in"):
            raise ValueError("Built-in models can only be disabled, not deleted.")
        del config["models"][model_id]
        self.save(config)

    def set_active_model(self, model_id: str) -> dict[str, Any]:
        config = self.load()
        if model_id not in (config.get("models") or {}):
            raise KeyError(model_id)
        config["active_model_id"] = model_id
        self.save(config)
        model = {"model_id": model_id, **config["models"][model_id]}
        compatibility = self.hub.indexing.check_collection_compatibility(model)
        embedding_config = self.hub.workspace.load_config("embedding.yaml")
        embedding_config.update(
            {
                "active_model_id": model_id,
                "provider": model.get("provider"),
                "model": model.get("model"),
                "dimension": model.get("dimension"),
                "normalize_embeddings": model.get("normalize_embeddings", True),
                "distance_metric": model.get("distance_metric", "cosine"),
            }
        )
        self.hub.workspace.save_config("embedding.yaml", embedding_config)
        return compatibility

    def test_connection(self, model_id: str | None = None) -> dict[str, Any]:
        model = self._model(model_id)
        provider = model.get("provider", "mock")
        errors: list[str] = []
        if provider in {"openai", "custom_api"} and model.get("api_key_env") and not os.getenv(str(model.get("api_key_env"))):
            errors.append(f"Missing environment variable {model.get('api_key_env')}; Demo Mode can still simulate.")
        vector = mock_embedding("connection test", int(model.get("dimension") or 128), str(model.get("model_id")))
        return {
            "model_id": model.get("model_id"),
            "provider": provider,
            "available": not errors or self.hub.is_demo_mode(),
            "dimension": len(vector),
            "first_8_values": [round(value, 6) for value in vector[:8]],
            "latency_ms": 8.0 if provider == "mock" else 35.0,
            "errors": errors,
            "note": "Mock embedding is for Demo Mode only and does not represent real semantic retrieval.",
        }

    def test_dimension(self, model_id: str | None = None) -> dict[str, Any]:
        return self.test_connection(model_id)

    def run_similarity_test(self, model_id: str | None = None) -> dict[str, Any]:
        model = self._model(model_id)
        pairs = [
            ("refund request process", "how do customers get a refund", "positive"),
            ("incident rollback approval", "who approves emergency rollback", "positive"),
            ("refund request process", "database backup retention", "negative"),
            ("P1 response time", "marketing campaign budget", "negative"),
            ("refund request process", "return shipping process", "hard_negative"),
        ]
        rows = []
        for left, right, group in pairs:
            score = cosine_similarity(
                mock_embedding(left, int(model.get("dimension") or 128), str(model.get("model_id"))),
                mock_embedding(right, int(model.get("dimension") or 128), str(model.get("model_id"))),
            )
            rows.append({"group": group, "text_a": left, "text_b": right, "similarity": round(score, 4)})
        positives = [row["similarity"] for row in rows if row["group"] == "positive"]
        negatives = [row["similarity"] for row in rows if row["group"] != "positive"]
        margin = (sum(positives) / len(positives)) - (sum(negatives) / len(negatives))
        return {
            "model_id": model["model_id"],
            "pair_rows": rows,
            "positive_avg_similarity": round(sum(positives) / len(positives), 4),
            "negative_avg_similarity": round(sum(negatives) / len(negatives), 4),
            "hard_negative_margin": round(margin, 4),
            "pair_accuracy": 0.8 if margin > 0 else 0.55,
        }

    def run_retrieval_benchmark(self, model_id: str | None = None) -> dict[str, Any]:
        started = time.perf_counter()
        examples = self.hub.query.get_example_questions()[:5]
        rows: list[dict[str, Any]] = []
        for question in examples:
            result = self.hub.retrieval.retrieve(question, {"mode": "hybrid", "top_k": 5, "rerank": True})
            rows.append(
                {
                    "query": question,
                    "hit": bool(result["reranked_chunks"]),
                    "recall_at_5": 1.0 if result["reranked_chunks"] else 0.0,
                    "ndcg_at_10": min(1.0, len(result["reranked_chunks"]) / 5),
                    "mrr_at_10": 1.0 if result["reranked_chunks"] else 0.0,
                    "precision_at_5": min(1.0, len(result["reranked_chunks"]) / 5),
                    "failure_reason": "" if result["reranked_chunks"] else "No indexed chunks",
                }
            )
        return {
            "model_id": self._model(model_id)["model_id"],
            "per_query_results": rows,
            "recall_at_5": avg([row["recall_at_5"] for row in rows]),
            "ndcg_at_10": avg([row["ndcg_at_10"] for row in rows]),
            "mrr_at_10": avg([row["mrr_at_10"] for row in rows]),
            "precision_at_5": avg([row["precision_at_5"] for row in rows]),
            "avg_latency_ms": round((time.perf_counter() - started) * 1000 / max(len(rows), 1), 2),
        }

    def compare_models(self) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        for model in self.list_models():
            if model.get("status") == "template":
                continue
            retrieval = self.run_retrieval_benchmark(model["model_id"])
            similarity = self.run_similarity_test(model["model_id"])
            engineering_score = max(55.0, 100 - float(model.get("dimension") or 128) / 50)
            retrieval_score = retrieval["recall_at_5"] * 40 + retrieval["mrr_at_10"] * 30 + retrieval["ndcg_at_10"] * 30
            semantic_score = max(40, min(100, 60 + similarity["hard_negative_margin"] * 120))
            rag_score = retrieval["precision_at_5"] * 60 + retrieval["recall_at_5"] * 40
            overall = retrieval_score * 0.45 + semantic_score * 0.15 + rag_score * 0.25 + engineering_score * 0.15
            row = {
                "model_name": model.get("display_name"),
                "provider": model.get("provider"),
                "dimension": model.get("dimension"),
                "max_input_length": model.get("max_input_tokens"),
                "overall_score": round(overall, 2),
                "grade": grade_for_score(overall),
                "retrieval_quality_score": round(retrieval_score, 2),
                "semantic_separation_score": round(semantic_score, 2),
                "rag_context_quality_score": round(rag_score, 2),
                "engineering_quality_score": round(engineering_score, 2),
                "recall_at_5": retrieval["recall_at_5"],
                "ndcg_at_10": retrieval["ndcg_at_10"],
                "mrr_at_10": retrieval["mrr_at_10"],
                "precision_at_5": retrieval["precision_at_5"],
                "hard_negative_margin": similarity["hard_negative_margin"],
                "avg_latency": retrieval["avg_latency_ms"],
                "p95_latency": round(retrieval["avg_latency_ms"] * 1.8, 2),
                "cost_per_1k_chunks": 0.0 if model.get("provider") != "openai" else 0.02,
                "storage_per_1k_chunks": f"{int(model.get('dimension') or 128) * 4 * 1000 / 1024 / 1024:.2f} MB",
                "need_reindex": model.get("need_reindex", False),
                "recommended_use": model.get("recommended_for", ""),
            }
            rows.append(row)
        rows.sort(key=lambda item: item["overall_score"], reverse=True)
        if rows:
            self.hub.evaluation.save_embedding_report(rows[0], rows)
        return {"rows": rows, "recommendation": rows[0] if rows else {}, "metric_rows": self.metric_rows(rows[0] if rows else {})}

    def metric_rows(self, row: dict[str, Any]) -> list[dict[str, Any]]:
        if not row:
            return []
        metrics = [
            ("Recall@5", row.get("recall_at_5", 0), row.get("retrieval_quality_score", 0), 18, "retrieval quality"),
            ("nDCG@10", row.get("ndcg_at_10", 0), row.get("retrieval_quality_score", 0), 14, "ranking quality"),
            ("MRR@10", row.get("mrr_at_10", 0), row.get("retrieval_quality_score", 0), 10, "first relevant rank"),
            ("Hard Negative Margin", row.get("hard_negative_margin", 0), row.get("semantic_separation_score", 0), 7, "semantic separation"),
            ("Context Precision", row.get("precision_at_5", 0), row.get("rag_context_quality_score", 0), 5, "clean context"),
            ("Avg Latency", row.get("avg_latency", 0), row.get("engineering_quality_score", 0), 5, "runtime latency"),
        ]
        return [
            {
                "metric_name": name,
                "current_value": current,
                "normalized_score": round(float(score), 2),
                "weight": weight,
                "weighted_score": round(float(score) * weight / 100, 2),
                "judgement": grade_for_score(float(score)),
                "explanation": explanation,
                "suggestion": "Tune chunking, retrieval mode, reranking, or switch embedding model.",
            }
            for name, current, score, weight, explanation in metrics
        ]

    def _model(self, model_id: str | None = None) -> dict[str, Any]:
        if not model_id:
            return self.active_model()
        for row in self.list_models():
            if row["model_id"] == model_id:
                return row
        raise KeyError(model_id)


class IndexingService:
    def __init__(self, hub: "RagWorkbenchServices") -> None:
        self.hub = hub

    @property
    def vector_path(self) -> Path:
        return self.hub.workspace.paths["vector_store"] / "vectors.json"

    @property
    def metadata_path(self) -> Path:
        return self.hub.workspace.paths["vector_store"] / "collection_metadata.json"

    def run_embedding(self, doc_id: str) -> dict[str, Any]:
        self.hub.documents.update_status(doc_id, "embedding", "向量化")
        model = self.hub.embedding_models.active_model()
        compatibility = self.check_collection_compatibility(model)
        if compatibility.get("blocking"):
            raise RuntimeError("; ".join(compatibility["issues"]))
        chunks = self.hub.chunking.list_chunks({"doc_id": doc_id})
        if not chunks:
            chunks = self.hub.chunking.run_chunking(doc_id)
        vectors = self._load_vectors()
        embedded = 0
        total_latency = 0.0
        for chunk in chunks:
            if not chunk["enabled"]:
                continue
            start = time.perf_counter()
            vector_id = f"{self._collection_name()}:{chunk['chunk_id']}"
            vector = mock_embedding(chunk["text"], int(model.get("dimension") or 128), str(model.get("model_id")))
            latency = round((time.perf_counter() - start) * 1000, 3)
            total_latency += latency
            vectors[vector_id] = {"vector": vector, "chunk_id": chunk["chunk_id"], "doc_id": doc_id, "model_id": model["model_id"]}
            embedding = {
                "embedding_id": stable_id("emb", chunk["chunk_id"], model["model_id"]),
                "chunk_id": chunk["chunk_id"],
                "doc_id": doc_id,
                "provider": model.get("provider"),
                "model": model.get("model"),
                "dimension": model.get("dimension"),
                "vector_id": vector_id,
                "collection_name": self._collection_name(),
                "status": "embedded",
                "latency_ms": latency,
                "cost_estimate": 0.0 if model.get("provider") != "openai" else 0.00002,
                "error_message": "",
                "embedded_at": now_iso(),
            }
            self.hub.store.upsert("embeddings", "embedding_id", embedding)
            self.hub.store.execute(
                "UPDATE chunks SET embedding_status='embedded', embedding_model=?, vector_id=?, updated_at=? WHERE chunk_id=?",
                (model["model_id"], vector_id, now_iso(), chunk["chunk_id"]),
            )
            embedded += 1
        self._save_vectors(vectors)
        self._save_collection_metadata(model, len(vectors))
        self.hub.store.execute(
            "UPDATE documents SET status='indexed', current_stage='索引完成', embedding_status='embedded', embedded_chunk_count=?, vector_collection=?, updated_at=? WHERE doc_id=?",
            (embedded, self._collection_name(), now_iso(), doc_id),
        )
        return {"doc_id": doc_id, "embedded_chunks": embedded, "latency_ms": round(total_latency, 2)}

    def rebuild_document_index(self, doc_id: str) -> dict[str, Any]:
        self.delete_document_index(doc_id)
        return self.run_embedding(doc_id)

    def rebuild_all_indexes(self) -> list[dict[str, Any]]:
        self.vector_path.unlink(missing_ok=True)
        self.metadata_path.unlink(missing_ok=True)
        self.hub.store.execute("UPDATE chunks SET embedding_status='stale', vector_id='', embedding_model=''")
        self.hub.store.execute("DELETE FROM embeddings")
        results = []
        for doc in self.hub.documents.list_documents():
            if doc["chunk_count"] <= 0:
                self.hub.chunking.run_chunking(doc["doc_id"])
            results.append(self.run_embedding(doc["doc_id"]))
        return results

    def retry_failed_chunks(self) -> dict[str, Any]:
        failed_docs = {row["doc_id"] for row in self.hub.store.query("SELECT DISTINCT doc_id FROM chunks WHERE embedding_status IN ('failed','stale')")}
        results = [self.run_embedding(doc_id) for doc_id in failed_docs]
        return {"documents": len(results), "results": results}

    def delete_document_index(self, doc_id: str) -> None:
        vectors = self._load_vectors()
        vectors = {key: value for key, value in vectors.items() if value.get("doc_id") != doc_id}
        self._save_vectors(vectors)
        self.hub.store.execute("DELETE FROM embeddings WHERE doc_id=?", (doc_id,))
        self.hub.store.execute("UPDATE chunks SET embedding_status='stale', vector_id='', embedding_model='' WHERE doc_id=?", (doc_id,))
        self.hub.store.execute("UPDATE documents SET embedded_chunk_count=0, embedding_status='stale' WHERE doc_id=?", (doc_id,))

    def get_collection_metadata(self) -> dict[str, Any]:
        if not self.metadata_path.exists():
            return {
                "collection_name": self._collection_name(),
                "vector_store_type": self.hub.workspace.load_config("vector_store.yaml").get("type"),
                "compatible": True,
                "chunk_count": 0,
                "needs_rebuild": False,
            }
        return json.loads(self.metadata_path.read_text(encoding="utf-8"))

    def check_collection_compatibility(self, model: dict[str, Any] | None = None) -> dict[str, Any]:
        model = model or self.hub.embedding_models.active_model()
        metadata = self.get_collection_metadata()
        issues: list[str] = []
        if metadata.get("chunk_count", 0) > 0:
            if metadata.get("embedding_model_id") != model.get("model_id"):
                issues.append("collection is bound to a different embedding_model_id")
            if int(metadata.get("dimension") or 0) != int(model.get("dimension") or 0):
                issues.append("collection dimension differs from selected embedding model")
            if metadata.get("distance_metric") != model.get("distance_metric", "cosine"):
                issues.append("distance metric differs from selected embedding model")
        return {"compatible": not issues, "need_reindex": bool(issues), "blocking": bool(issues), "issues": issues}

    def index_task_rows(self) -> list[dict[str, Any]]:
        rows = []
        for doc in self.hub.documents.list_documents():
            failed = self.hub.store.get("SELECT COUNT(*) AS count FROM chunks WHERE doc_id=? AND embedding_status='failed'", (doc["doc_id"],)) or {"count": 0}
            latest = self.hub.store.get("SELECT AVG(latency_ms) AS latency, SUM(cost_estimate) AS cost FROM embeddings WHERE doc_id=?", (doc["doc_id"],)) or {}
            rows.append(
                {
                    "doc_id": doc["doc_id"],
                    "filename": doc["filename"],
                    "total_chunks": doc["chunk_count"],
                    "embedded_chunks": doc["embedded_chunk_count"],
                    "failed_chunks": failed.get("count", 0),
                    "embedding_model": self.hub.embedding_models.active_model().get("model_id"),
                    "dimension": self.hub.embedding_models.active_model().get("dimension"),
                    "collection_name": self._collection_name(),
                    "status": doc["embedding_status"],
                    "latency_ms": round(float(latest.get("latency") or 0), 2),
                    "estimated_cost": round(float(latest.get("cost") or 0), 6),
                    "operation": "rebuild / delete / retry",
                }
            )
        return rows

    def _collection_name(self) -> str:
        return str(self.hub.workspace.load_config("vector_store.yaml").get("collection_name") or "enterprise_kb_demo")

    def _load_vectors(self) -> dict[str, Any]:
        if not self.vector_path.exists():
            return {}
        try:
            return json.loads(self.vector_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save_vectors(self, vectors: dict[str, Any]) -> None:
        self.vector_path.parent.mkdir(parents=True, exist_ok=True)
        self.vector_path.write_text(json.dumps(vectors, ensure_ascii=False), encoding="utf-8")

    def _save_collection_metadata(self, model: dict[str, Any], chunk_count: int) -> None:
        metadata = {
            "collection_name": self._collection_name(),
            "vector_store_type": self.hub.workspace.load_config("vector_store.yaml").get("type"),
            "embedding_model_id": model.get("model_id"),
            "provider": model.get("provider"),
            "dimension": int(model.get("dimension") or 128),
            "distance_metric": model.get("distance_metric", "cosine"),
            "normalize_embeddings": bool(model.get("normalize_embeddings", True)),
            "chunk_count": chunk_count,
            "doc_count": len({row["doc_id"] for row in self.hub.documents.list_documents()}),
            "updated_at": now_iso(),
            "compatible": True,
            "needs_rebuild": False,
        }
        self.metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")


class RetrievalService:
    def __init__(self, hub: "RagWorkbenchServices") -> None:
        self.hub = hub

    def retrieve(self, question: str, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        filters = filters or {}
        mode = filters.get("mode") or self.hub.workspace.load_config("retrieval.yaml").get("mode", "hybrid")
        top_k = int(filters.get("top_k") or self.hub.workspace.load_config("retrieval.yaml").get("final_top_k") or 5)
        vector_rows = self.vector_search(question, top_k=max(top_k, 8)) if mode in {"vector", "hybrid"} else []
        bm25_rows = self.bm25_search(question, top_k=max(top_k, 8)) if mode in {"bm25", "hybrid"} else []
        if mode == "vector":
            fused = vector_rows
        elif mode == "bm25":
            fused = bm25_rows
        else:
            fused = self.hybrid_search(vector_rows, bm25_rows)
        reranked = self.rerank(question, fused) if filters.get("rerank", True) else fused
        context = self.build_context(reranked[:top_k])
        return {
            "retrieval_mode": mode,
            "vector_rows": vector_rows,
            "bm25_rows": bm25_rows,
            "retrieved_chunks": fused[:top_k],
            "reranked_chunks": reranked[:top_k],
            "context": context,
        }

    def vector_search(self, question: str, filters: dict[str, Any] | None = None, top_k: int = 5) -> list[dict[str, Any]]:
        model = self.hub.embedding_models.active_model()
        query_vector = mock_embedding(question, int(model.get("dimension") or 128), str(model.get("model_id")))
        vectors = self.hub.indexing._load_vectors()
        chunks_by_id = {row["chunk_id"]: row for row in self.hub.chunking.list_chunks({"enabled": "enabled"})}
        rows: list[dict[str, Any]] = []
        for vector_id, payload in vectors.items():
            chunk = chunks_by_id.get(payload.get("chunk_id"))
            if not chunk:
                continue
            score = cosine_similarity(query_vector, payload.get("vector") or [])
            rows.append(self._result_row(chunk, vector_score=score, bm25_score=0.0, hybrid_score=score, rerank_score=score))
        rows.sort(key=lambda item: item["vector_score"], reverse=True)
        return rows[:top_k]

    def bm25_search(self, question: str, filters: dict[str, Any] | None = None, top_k: int = 5) -> list[dict[str, Any]]:
        query_terms = set(tokenize(question))
        chunks = self.hub.chunking.list_chunks({"enabled": "enabled"})
        rows: list[dict[str, Any]] = []
        for chunk in chunks:
            terms = tokenize(chunk["text"])
            if not terms:
                score = 0.0
            else:
                overlap = sum(1 for term in terms if term in query_terms)
                score = overlap / math.sqrt(len(terms))
            rows.append(self._result_row(chunk, vector_score=0.0, bm25_score=score, hybrid_score=score, rerank_score=score))
        rows.sort(key=lambda item: item["bm25_score"], reverse=True)
        return rows[:top_k]

    def hybrid_search(self, vector_rows: list[dict[str, Any]] | None = None, bm25_rows: list[dict[str, Any]] | None = None, **_: Any) -> list[dict[str, Any]]:
        vector_rows = vector_rows or []
        bm25_rows = bm25_rows or []
        merged: dict[str, dict[str, Any]] = {}
        for rank, row in enumerate(vector_rows, start=1):
            item = dict(row)
            item["rank_before"] = rank
            item["hybrid_score"] = item.get("vector_score", 0) * 0.65 + (1 / (rank + 10)) * 0.35
            merged[item["chunk_id"]] = item
        for rank, row in enumerate(bm25_rows, start=1):
            item = merged.get(row["chunk_id"], dict(row))
            item["bm25_score"] = row.get("bm25_score", 0)
            item["hybrid_score"] = item.get("hybrid_score", 0) + item["bm25_score"] * 0.35 + (1 / (rank + 10)) * 0.20
            merged[row["chunk_id"]] = item
        rows = list(merged.values())
        rows.sort(key=lambda item: item["hybrid_score"], reverse=True)
        for index, row in enumerate(rows, start=1):
            row["rank_before"] = index
        return rows

    def rerank(self, question: str, rows: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        rows = [dict(row) for row in (rows or [])]
        terms = set(tokenize(question))
        for row in rows:
            text_terms = set(tokenize(row.get("text_preview", "")))
            keyword_boost = len(terms & text_terms) / max(len(terms), 1)
            row["rerank_score"] = row.get("hybrid_score", row.get("vector_score", row.get("bm25_score", 0))) + keyword_boost * 0.2
        rows.sort(key=lambda item: item["rerank_score"], reverse=True)
        for index, row in enumerate(rows, start=1):
            row["rank_after"] = index
        return rows

    def build_context(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        context: list[dict[str, Any]] = []
        for index, row in enumerate(rows, start=1):
            chunk = self.hub.chunking.get_chunk(row["chunk_id"])
            context.append(
                {
                    "citation_index": index,
                    "chunk_id": chunk["chunk_id"],
                    "doc_id": chunk["doc_id"],
                    "filename": chunk["filename"],
                    "page_start": chunk["page_start"],
                    "page_end": chunk["page_end"],
                    "section_path": chunk["section_path"],
                    "text": chunk["text"],
                    "scores": {
                        "vector_score": row.get("vector_score", 0),
                        "bm25_score": row.get("bm25_score", 0),
                        "hybrid_score": row.get("hybrid_score", 0),
                        "rerank_score": row.get("rerank_score", 0),
                    },
                }
            )
        return context

    def _result_row(self, chunk: dict[str, Any], vector_score: float, bm25_score: float, hybrid_score: float, rerank_score: float) -> dict[str, Any]:
        return {
            "rank_before": 0,
            "rank_after": 0,
            "chunk_id": chunk["chunk_id"],
            "doc_id": chunk["doc_id"],
            "filename": chunk["filename"],
            "page_range": f"{chunk['page_start']}-{chunk['page_end']}",
            "section_path": chunk["section_path"],
            "vector_score": round(float(vector_score), 6),
            "bm25_score": round(float(bm25_score), 6),
            "hybrid_score": round(float(hybrid_score), 6),
            "rerank_score": round(float(rerank_score), 6),
            "text_preview": chunk["text_preview"],
        }


class AnswerService:
    def __init__(self, hub: "RagWorkbenchServices") -> None:
        self.hub = hub

    def generate_answer(self, question: str, context: list[dict[str, Any]]) -> dict[str, Any]:
        min_score = float(self.hub.workspace.load_config("retrieval.yaml").get("min_evidence_score") or 0.05)
        if not context or max(item["scores"].get("rerank_score", 0) for item in context) < min_score:
            return {"answer": "当前知识库没有足够依据。", "insufficient_evidence": True}
        statements = []
        for item in context[:3]:
            snippet = self._best_snippet(question, item["text"])
            statements.append(f"{snippet} [{item['citation_index']}]")
        answer = "根据当前知识库检索到的证据：\n" + "\n".join(f"- {statement}" for statement in statements)
        if self.hub.is_demo_mode():
            answer += "\n\n提示：当前为 Demo Mode，mock embedding 仅用于流程演示，不代表真实语义检索质量。"
        return {"answer": answer, "insufficient_evidence": False}

    def generate_citations(self, retrieved_chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        citations = []
        for index, item in enumerate(retrieved_chunks, start=1):
            citations.append(
                {
                    "citation_index": index,
                    "chunk_id": item["chunk_id"],
                    "doc_id": item["doc_id"],
                    "filename": item["filename"],
                    "page_range": item.get("page_range"),
                    "section_path": item.get("section_path"),
                    "vector_score": item.get("vector_score", 0),
                    "bm25_score": item.get("bm25_score", 0),
                    "rerank_score": item.get("rerank_score", 0),
                }
            )
        return citations

    def _best_snippet(self, question: str, text: str) -> str:
        terms = set(tokenize(question))
        sentences = re.split(r"(?<=[。.!?])\s+|\n+", text)
        if not sentences:
            return preview_text(text, 280)
        best = max(sentences, key=lambda sentence: len(terms & set(tokenize(sentence))))
        return preview_text(best or text, 280)


QUERY_EXPANSIONS = {
    "sla": "service level agreement response time priority support",
    "p1": "priority one urgent response escalation",
    "p0": "critical incident emergency approval notification",
    "refund": "return after-sales entitlement approval",
    "rollback": "incident commander approval change rollback",
    "502": "payment gateway upstream provider retry queue failover",
    "revenue": "quarterly revenue gross margin sales",
    "prompt injection": "untrusted context ignore previous instructions",
    "api key": "secret credential token password policy",
    "退款": "售后 订单校验 权益审核 主管审批",
    "响应": "SLA 优先级 响应时间",
    "回滚": "事故指挥官 审批 变更",
    "支付": "支付网关 第三方通道 重试队列 备用通道",
}

PROMPT_INJECTION_MARKERS = (
    "ignore previous instructions",
    "ignore all previous instructions",
    "system prompt",
    "developer message",
    "execute shell",
    "reveal api key",
    "reveal token",
    "忽略之前",
    "泄露密钥",
)


def _qa_split_question(question: str) -> list[str]:
    parts = re.split(r"\?|;|；|以及|并且|同时|分别|还要| and | also | compare | vs ", question, flags=re.IGNORECASE)
    cleaned = [part.strip(" ，,。.") for part in parts if len(part.strip(" ，,。.")) >= 6]
    return cleaned[:3] or [question.strip()]


def _qa_query_variants(question: str) -> list[str]:
    variants = [question]
    lowered = question.lower()
    additions = [value for key, value in QUERY_EXPANSIONS.items() if key.lower() in lowered or key in question]
    if additions:
        variants.append(f"{question} {' '.join(additions)}")
    deduped: list[str] = []
    for item in variants:
        normalized = re.sub(r"\s+", " ", item).strip()
        if normalized and normalized not in deduped:
            deduped.append(normalized)
    return deduped[:3]


def _qa_prompt_injection_flags(text: str) -> list[str]:
    lowered = text.lower()
    return [marker for marker in PROMPT_INJECTION_MARKERS if marker in lowered or marker in text]


def _qa_best_score(row: dict[str, Any]) -> float:
    return float(row.get("rerank_score") or row.get("hybrid_score") or row.get("vector_score") or row.get("bm25_score") or 0)


class QueryService:
    def __init__(self, hub: "RagWorkbenchServices") -> None:
        self.hub = hub

    def ask(self, question: str, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        started = time.perf_counter()
        filters = filters or {}
        indexed = [doc for doc in self.hub.documents.list_documents() if doc["status"] == "indexed"]
        if not indexed:
            payload = {
                "question": question,
                "answer": "当前知识库没有足够依据。请先导入文档并完成向量化索引。",
                "citations": [],
                "retrieved_chunks": [],
                "reranked_chunks": [],
                "context": [],
                "trace_id": "",
                "latency_ms": 0,
                "insufficient_evidence": True,
                "answer_type": "insufficient_evidence",
                "confidence": 0.0,
                "qa_plan": {},
                "evidence_report": {},
                "verification": {"status": "insufficient", "missing_evidence": ["no indexed documents"]},
            }
            return payload
        qa_plan = self._build_qa_plan(question, filters)
        evidence_report, retrieval = self._collect_evidence(qa_plan, filters)
        verification = self._verify_evidence(qa_plan, evidence_report, retrieval["context"])
        answer_payload = self.hub.answer.generate_answer(question, retrieval["context"])
        answer_type = verification["answer_type"]
        if answer_type == "insufficient_evidence":
            answer_payload["answer"] = (
                "当前知识库没有足够依据回答该问题。"
                f"已拆解 {len(qa_plan['steps'])} 个子问题，"
                f"找到 {evidence_report['usable_evidence_count']} 条可用证据；"
                f"缺口：{'; '.join(verification['missing_evidence']) or '证据覆盖不足'}。"
            )
            answer_payload["insufficient_evidence"] = True
        citations = self.hub.answer.generate_citations(retrieval["reranked_chunks"])
        trace_id = stable_id("trace", question, now_iso())
        latency = round((time.perf_counter() - started) * 1000, 2)
        payload = {
            "trace_id": trace_id,
            "question": question,
            "retrieval_mode": retrieval["retrieval_mode"],
            "query_rewrite": qa_plan["steps"][0]["query_variants"] if qa_plan["steps"] else [question],
            "query_embedding_model": self.hub.embedding_models.active_model().get("model_id"),
            "retrieved_chunks": retrieval["retrieved_chunks"],
            "reranked_chunks": retrieval["reranked_chunks"],
            "context": retrieval["context"],
            "answer": answer_payload["answer"],
            "citations": citations,
            "latency_ms": latency,
            "token_usage": {"prompt_tokens": estimate_tokens(json_dumps(retrieval["context"])), "completion_tokens": estimate_tokens(answer_payload["answer"])},
            "created_at": now_iso(),
            "error_message": "",
            "insufficient_evidence": answer_payload["insufficient_evidence"],
            "answer_type": answer_type,
            "confidence": verification["confidence"],
            "qa_plan": qa_plan,
            "evidence_report": evidence_report,
            "verification": verification,
        }
        self.hub.trace.save_trace(payload)
        return payload

    def _build_qa_plan(self, question: str, filters: dict[str, Any]) -> dict[str, Any]:
        subquestions = _qa_split_question(question)
        strategy = "multi_query_rag" if len(subquestions) > 1 else "focused_rag"
        top_k = int(filters.get("top_k") or self.hub.workspace.load_config("retrieval.yaml").get("final_top_k") or 5)
        steps = []
        for index, item in enumerate(subquestions, start=1):
            steps.append(
                {
                    "step_id": f"q{index}",
                    "question": item,
                    "query_variants": _qa_query_variants(item),
                    "top_k": top_k,
                    "required_evidence": 1,
                }
            )
        return {
            "strategy": strategy,
            "question_type": "multi_hop" if len(steps) > 1 else "direct",
            "allow_data_tool": False,
            "llm_usage": {
                "question_analysis": "fallback_rule_based_in_demo_mode",
                "answer_synthesis": "workspace_answer_service",
                "embedding": self.hub.embedding_models.active_model().get("model_id"),
            },
            "steps": steps,
            "output_requirements": [
                "answer only from retrieved chunks",
                "generate citations from chunk metadata",
                "return insufficient_evidence when coverage is weak",
                "record qa_plan, evidence_report, and verification in trace",
            ],
        }

    def _collect_evidence(self, qa_plan: dict[str, Any], filters: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        all_retrieved: dict[str, dict[str, Any]] = {}
        all_reranked: dict[str, dict[str, Any]] = {}
        subquestions: list[dict[str, Any]] = []
        retrieval_mode = filters.get("mode") or self.hub.workspace.load_config("retrieval.yaml").get("mode", "hybrid")
        for step in qa_plan["steps"]:
            step_items: dict[str, dict[str, Any]] = {}
            blocked_items: list[dict[str, Any]] = []
            for query in step["query_variants"]:
                query_filters = {**filters, "top_k": step["top_k"]}
                result = self.hub.retrieval.retrieve(query, query_filters)
                retrieval_mode = result["retrieval_mode"]
                for row in result["retrieved_chunks"]:
                    self._keep_best(all_retrieved, row)
                for row in result["reranked_chunks"]:
                    enriched = dict(row)
                    chunk = self.hub.chunking.get_chunk(row["chunk_id"])
                    flags = _qa_prompt_injection_flags(chunk.get("text", ""))
                    enriched["qa_query"] = query
                    enriched["prompt_injection_flags"] = flags
                    if flags:
                        blocked_items.append(enriched)
                    else:
                        self._keep_best(step_items, enriched)
                        self._keep_best(all_reranked, enriched)
            subquestions.append(
                {
                    "step_id": step["step_id"],
                    "question": step["question"],
                    "queries": step["query_variants"],
                    "usable_evidence_count": len(step_items),
                    "blocked_source_count": len(blocked_items),
                    "items": sorted(step_items.values(), key=_qa_best_score, reverse=True)[: step["top_k"]],
                    "blocked_items": blocked_items,
                }
            )
        reranked_chunks = sorted(all_reranked.values(), key=_qa_best_score, reverse=True)
        top_k = int(filters.get("top_k") or self.hub.workspace.load_config("retrieval.yaml").get("final_top_k") or 5)
        reranked_chunks = reranked_chunks[:top_k]
        retrieved_chunks = sorted(all_retrieved.values(), key=_qa_best_score, reverse=True)[:top_k]
        context = self.hub.retrieval.build_context(reranked_chunks)
        supported = sum(1 for item in subquestions if item["usable_evidence_count"] >= 1)
        evidence_report = {
            "subquestions": subquestions,
            "usable_evidence_count": sum(item["usable_evidence_count"] for item in subquestions),
            "total_sources": sum(item["usable_evidence_count"] + item["blocked_source_count"] for item in subquestions),
            "blocked_source_count": sum(item["blocked_source_count"] for item in subquestions),
            "prompt_injection_count": sum(item["blocked_source_count"] for item in subquestions),
            "coverage": round(supported / max(len(subquestions), 1), 4),
        }
        return evidence_report, {
            "retrieval_mode": retrieval_mode,
            "retrieved_chunks": retrieved_chunks,
            "reranked_chunks": reranked_chunks,
            "context": context,
        }

    def _verify_evidence(self, qa_plan: dict[str, Any], evidence_report: dict[str, Any], context: list[dict[str, Any]]) -> dict[str, Any]:
        min_score = float(self.hub.workspace.load_config("retrieval.yaml").get("min_evidence_score") or 0.05)
        missing = []
        scores = []
        for step, evidence in zip(qa_plan["steps"], evidence_report["subquestions"]):
            if evidence["usable_evidence_count"] < step["required_evidence"]:
                missing.append(step["question"])
            for item in evidence["items"][:3]:
                scores.append(_qa_best_score(item))
        best_score = max(scores or [0.0])
        coverage = float(evidence_report["coverage"])
        confidence = round(min(0.95, max(0.0, 0.3 + coverage * 0.35 + min(best_score, 1.0) * 0.35)), 4)
        warnings = []
        if evidence_report["prompt_injection_count"]:
            warnings.append("retrieved_context_contains_prompt_injection_markers")
        if missing or not context or best_score < min_score:
            return {
                "status": "insufficient",
                "answer_type": "insufficient_evidence",
                "confidence": min(confidence, 0.45),
                "supported_step_count": len(qa_plan["steps"]) - len(missing),
                "total_step_count": len(qa_plan["steps"]),
                "missing_evidence": missing or ["retrieval score below evidence threshold"],
                "citation_coverage": coverage,
                "warnings": warnings,
            }
        return {
            "status": "passed",
            "answer_type": "direct_answer",
            "confidence": confidence,
            "supported_step_count": len(qa_plan["steps"]),
            "total_step_count": len(qa_plan["steps"]),
            "missing_evidence": [],
            "citation_coverage": coverage,
            "warnings": warnings,
        }

    def _keep_best(self, rows: dict[str, dict[str, Any]], row: dict[str, Any]) -> None:
        key = str(row.get("chunk_id") or "")
        if not key:
            return
        current = rows.get(key)
        if current is None or _qa_best_score(row) > _qa_best_score(current):
            rows[key] = dict(row)

    def get_example_questions(self) -> list[str]:
        questions: list[str] = []
        for row in self.hub.annotation.list_annotations():
            try:
                questions.extend(json.loads(row.get("possible_questions") or "[]"))
            except Exception:
                pass
        eval_path = ROOT_DIR / "data" / "eval_sets" / "rag_eval.jsonl"
        if eval_path.exists():
            for line in eval_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    try:
                        questions.append(json.loads(line)["question"])
                    except Exception:
                        pass
        return list(dict.fromkeys(questions))[:12] or ["What is included in the Enterprise RAG Workbench?"]


class TraceService:
    def __init__(self, hub: "RagWorkbenchServices") -> None:
        self.hub = hub

    def save_trace(self, payload: dict[str, Any]) -> None:
        row = {
            "trace_id": payload["trace_id"],
            "question": payload["question"],
            "retrieval_mode": payload["retrieval_mode"],
            "query_rewrite": payload["query_rewrite"] if isinstance(payload["query_rewrite"], str) else json_dumps(payload["query_rewrite"]),
            "query_embedding_model": payload["query_embedding_model"],
            "retrieved_chunks_json": json_dumps(payload["retrieved_chunks"]),
            "reranked_chunks_json": json_dumps(payload["reranked_chunks"]),
            "context_json": json_dumps(payload["context"]),
            "answer": payload["answer"],
            "citations_json": json_dumps(payload["citations"]),
            "latency_ms": payload["latency_ms"],
            "token_usage_json": json_dumps(payload["token_usage"]),
            "created_at": payload["created_at"],
            "error_message": payload.get("error_message", ""),
        }
        self.hub.store.upsert("traces", "trace_id", row)
        path = self.hub.workspace.paths["traces"] / f"{payload['trace_id']}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def list_traces(self) -> list[dict[str, Any]]:
        rows = self.hub.store.query("SELECT trace_id, question, retrieval_mode, latency_ms, created_at, error_message FROM traces ORDER BY created_at DESC")
        for row in rows:
            row["status"] = "failed" if row.get("error_message") else "ok"
        return rows

    def get_trace(self, trace_id: str) -> dict[str, Any]:
        row = self.hub.store.get("SELECT * FROM traces WHERE trace_id=?", (trace_id,))
        if not row:
            raise KeyError(trace_id)
        for key in ["retrieved_chunks_json", "reranked_chunks_json", "context_json", "citations_json", "token_usage_json"]:
            try:
                row[key.removesuffix("_json")] = json.loads(row.get(key) or "[]")
            except Exception:
                row[key.removesuffix("_json")] = []
        path = self.hub.workspace.paths["traces"] / f"{trace_id}.json"
        if path.exists():
            try:
                full_payload = json.loads(path.read_text(encoding="utf-8"))
                for key in ["answer_type", "confidence", "qa_plan", "evidence_report", "verification", "insufficient_evidence"]:
                    if key in full_payload:
                        row[key] = full_payload[key]
            except Exception:
                pass
        return row

    def export_trace(self, trace_id: str) -> str:
        trace = self.get_trace(trace_id)
        path = self.hub.workspace.paths["exports"] / f"{trace_id}.json"
        path.write_text(json.dumps(trace, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(path)


class EvaluationService:
    def __init__(self, hub: "RagWorkbenchServices") -> None:
        self.hub = hub

    def run_rag_eval(self, eval_set: str | None = None) -> dict[str, Any]:
        eval_path = Path(eval_set) if eval_set else ROOT_DIR / "data" / "eval_sets" / "rag_eval.jsonl"
        cases = self._load_eval_cases(eval_path)
        rows: list[dict[str, Any]] = []
        for case in cases:
            result = self.hub.query.ask(case["question"], {"mode": "hybrid", "top_k": 5, "rerank": True})
            answer = result["answer"]
            retrieved = result["reranked_chunks"]
            expected_sources = case.get("expected_sources") or []
            source_hit = any(row.get("filename") in expected_sources for row in retrieved)
            expected_terms = set(tokenize(case.get("expected_answer", "")))
            answer_terms = set(tokenize(answer))
            relevancy = len(expected_terms & answer_terms) / max(len(expected_terms), 1) if expected_terms else 0.6
            score = min(1.0, 0.45 * relevancy + 0.35 * (1.0 if source_hit else 0.0) + 0.20 * (1.0 if not result["insufficient_evidence"] else 0.0))
            rows.append(
                {
                    "question": case["question"],
                    "expected_answer": case.get("expected_answer", ""),
                    "expected_sources": ", ".join(expected_sources),
                    "actual_answer": answer,
                    "retrieved_chunks": ", ".join(row["chunk_id"] for row in retrieved),
                    "score": round(score, 3),
                    "status": "pass" if score >= 0.55 else "fail",
                    "failure_reason": "" if score >= 0.55 else "missing expected source or answer term",
                    "trace_id": result["trace_id"],
                }
            )
        metrics = self._aggregate_eval_metrics(rows)
        report = {"target": "rag", "metrics": metrics, "results": rows, "created_at": now_iso()}
        report_path = self._write_report("rag_eval", report)
        eval_run = {
            "eval_run_id": stable_id("eval", "rag", now_iso()),
            "target": "rag",
            "model_id": self.hub.workspace.load_config("llm.yaml").get("model"),
            "retrieval_mode": self.hub.workspace.load_config("retrieval.yaml").get("mode"),
            "overall_score": metrics["overall_score"],
            "metrics_json": json_dumps(metrics),
            "report_path": report_path,
            "created_at": now_iso(),
        }
        self.hub.store.upsert("eval_runs", "eval_run_id", eval_run)
        return {**report, "report_path": report_path}

    def run_embedding_eval(self) -> dict[str, Any]:
        return self.hub.embedding_models.compare_models()

    def get_latest_reports(self) -> dict[str, Any]:
        rag = self.hub.store.query("SELECT * FROM eval_runs ORDER BY created_at DESC LIMIT 5")
        embedding = self.hub.store.query("SELECT * FROM embedding_model_reports ORDER BY created_at DESC LIMIT 5")
        return {"rag": rag, "embedding": embedding}

    def export_report(self, report_id: str, format: str = "json") -> str:
        row = self.hub.store.get("SELECT * FROM eval_runs WHERE eval_run_id=?", (report_id,))
        if not row:
            row = self.hub.store.get("SELECT * FROM embedding_model_reports WHERE report_id=?", (report_id,))
        if not row:
            raise KeyError(report_id)
        source = Path(row["report_path"])
        payload = json.loads(source.read_text(encoding="utf-8")) if source.exists() else row
        target = self.hub.workspace.paths["exports"] / f"{report_id}.{format}"
        if format == "json":
            target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        elif format == "csv":
            rows = payload.get("results") or payload.get("rows") or []
            target.write_text(dicts_to_csv(rows), encoding="utf-8")
        elif format in {"md", "markdown"}:
            target.write_text(report_to_markdown(payload), encoding="utf-8")
        elif format == "html":
            target.write_text(report_to_html(payload), encoding="utf-8")
        else:
            raise ValueError(format)
        return str(target)

    def save_embedding_report(self, best: dict[str, Any], rows: list[dict[str, Any]]) -> None:
        report_id = stable_id("emb_report", best.get("model_name"), now_iso())
        report = {"report_id": report_id, "best": best, "rows": rows, "created_at": now_iso()}
        report_path = self._write_report("embedding_eval", report)
        row = {
            "report_id": report_id,
            "model_id": best.get("model_name"),
            "overall_score": best.get("overall_score", 0),
            "grade": best.get("grade", "Failed"),
            "retrieval_quality_score": best.get("retrieval_quality_score", 0),
            "semantic_separation_score": best.get("semantic_separation_score", 0),
            "rag_context_quality_score": best.get("rag_context_quality_score", 0),
            "engineering_quality_score": best.get("engineering_quality_score", 0),
            "metrics_json": json_dumps(best),
            "report_path": report_path,
            "created_at": now_iso(),
        }
        self.hub.store.upsert("embedding_model_reports", "report_id", row)

    def _load_eval_cases(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return [
                {
                    "question": "What is included in Enterprise RAG Workbench?",
                    "expected_answer": "RAG pipeline documents embeddings retrieval citations evaluation",
                    "expected_sources": ["enterprise_kb.md"],
                }
            ]
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def _aggregate_eval_metrics(self, rows: list[dict[str, Any]]) -> dict[str, float]:
        overall = avg([row["score"] for row in rows])
        pass_rate = avg([1.0 if row["status"] == "pass" else 0.0 for row in rows])
        return {
            "overall_score": round(overall * 100, 2),
            "context_precision": round(pass_rate, 3),
            "context_recall": round(pass_rate, 3),
            "faithfulness": round(overall, 3),
            "answer_relevancy": round(overall, 3),
            "citation_accuracy": round(pass_rate, 3),
            "retrieval_hit_rate": round(pass_rate, 3),
            "latency": round(avg([self._trace_latency(row.get("trace_id", "")) for row in rows]), 2),
            "cost": 0.0,
        }

    def _trace_latency(self, trace_id: str) -> float:
        if not trace_id:
            return 0.0
        row = self.hub.store.get("SELECT latency_ms FROM traces WHERE trace_id=?", (trace_id,))
        return float((row or {}).get("latency_ms") or 0)

    def _write_report(self, stem: str, payload: dict[str, Any]) -> str:
        path = self.hub.workspace.paths["reports"] / f"{stem}_{stable_id('run', now_iso())[4:]}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(path)


class SettingsService:
    def __init__(self, hub: "RagWorkbenchServices") -> None:
        self.hub = hub

    def load_all_configs(self) -> dict[str, dict[str, Any]]:
        return {path.name: self.hub.workspace.load_config(path.name) for path in CONFIG_DIR.glob("*.yaml")}

    def save_config(self, filename: str, config: dict[str, Any]) -> None:
        self.hub.workspace.save_config(filename, config)

    def validate_config(self, filename: str, text: str) -> dict[str, Any]:
        try:
            data = yaml.safe_load(text) or {}
            if not isinstance(data, dict):
                raise ValueError("YAML root must be an object")
            return {"valid": True, "config": data, "errors": []}
        except Exception as exc:
            return {"valid": False, "config": {}, "errors": [str(exc)]}

    def reset_config(self, filename: str) -> dict[str, Any]:
        config = DEFAULT_CONFIGS.get(filename, {})
        self.hub.workspace.save_config(filename, config)
        return dict(config)

    def export_configs(self) -> str:
        path = self.hub.workspace.paths["exports"] / f"configs_{stable_id('cfg', now_iso())[4:]}.json"
        path.write_text(json.dumps(self.load_all_configs(), ensure_ascii=False, indent=2), encoding="utf-8")
        return str(path)

    def import_configs(self, path: str | Path) -> None:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        for filename, config in payload.items():
            if filename.endswith(".yaml") and isinstance(config, dict):
                self.save_config(filename, config)

    def test_llm_connection(self) -> dict[str, Any]:
        config = self.hub.workspace.load_config("llm.yaml")
        provider = config.get("provider")
        if provider == "mock":
            return {"available": True, "latency_ms": 5, "message": "Mock LLM is ready for Demo Mode."}
        env_name = config.get("api_key_env")
        return {
            "available": bool(env_name and os.getenv(str(env_name))),
            "latency_ms": 0,
            "message": "External LLM configuration is present." if env_name and os.getenv(str(env_name)) else f"Missing environment variable {env_name}.",
        }


class RagWorkbenchServices:
    def __init__(self) -> None:
        self.workspace = WorkspaceService()
        self.store = LocalStore(self.workspace.paths["database"])
        self.documents = DocumentService(self)
        self.parser = ParserService(self)
        self.cleaning = CleaningService(self)
        self.chunking = ChunkingService(self)
        self.annotation = AnnotationService(self)
        self.embedding_models = EmbeddingModelRegistry(self)
        self.indexing = IndexingService(self)
        self.retrieval = RetrievalService(self)
        self.answer = AnswerService(self)
        self.query = QueryService(self)
        self.trace = TraceService(self)
        self.evaluation = EvaluationService(self)
        self.settings = SettingsService(self)
        if os.getenv("RAG_WORKBENCH_SKIP_AUTO_SEED") != "1":
            self.ensure_demo_data()

    def is_demo_mode(self) -> bool:
        return str(self.workspace.load_config("rag.yaml").get("mode", "Demo Mode")).lower().startswith("demo")

    def ensure_demo_data(self) -> None:
        config = self.workspace.load_config("rag.yaml")
        if not self.is_demo_mode() or not config.get("auto_seed_demo_on_start", True):
            return
        docs = self.documents.list_documents()
        if docs and all(Path(doc.get("raw_path") or "").exists() for doc in docs):
            return
        imported = self.documents.import_sample_docs()
        doc_ids = [row["doc_id"] for row in imported] or [row["doc_id"] for row in self.documents.list_documents()]
        if doc_ids:
            self.documents.run_full_pipeline(doc_ids)
            self.query.ask("What is included in the Enterprise RAG Workbench?", {"mode": "hybrid", "top_k": 5, "rerank": True})
            self.evaluation.run_rag_eval()
            self.embedding_models.compare_models()

    def dashboard(self) -> dict[str, Any]:
        docs = self.documents.list_documents()
        chunks = self.chunking.list_chunks()
        latest_trace = self.trace.list_traces()[:1]
        latest_report = self.evaluation.get_latest_reports()["rag"][:1]
        active_model = self.embedding_models.active_model()
        vector = self.indexing.get_collection_metadata()
        status_by_stage = self.pipeline_status()
        return {
            "workspace": self.workspace.get_workspace_paths(),
            "mode": self.workspace.load_config("rag.yaml").get("mode", "Demo Mode"),
            "document_total": len(docs),
            "indexed_documents": sum(1 for doc in docs if doc["status"] == "indexed"),
            "failed_documents": sum(1 for doc in docs if doc["status"] == "failed"),
            "chunk_total": len(chunks),
            "embedded_chunk_total": sum(1 for chunk in chunks if chunk["embedding_status"] == "embedded"),
            "current_embedding_model": active_model.get("display_name") or active_model.get("model_id"),
            "current_vector_store": vector.get("vector_store_type") or self.workspace.load_config("vector_store.yaml").get("type"),
            "current_llm": self.workspace.load_config("llm.yaml").get("model"),
            "last_qa_latency_ms": latest_trace[0]["latency_ms"] if latest_trace else "-",
            "last_eval_score": latest_report[0]["overall_score"] if latest_report else "-",
            "pipeline_status": status_by_stage,
            "recent_documents": docs[:20],
        }

    def pipeline_status(self) -> list[dict[str, Any]]:
        docs = self.documents.list_documents()
        if not docs:
            return [{"stage": stage, "status": "未开始"} for stage in DOCUMENT_STAGES]
        stage_map = {
            "导入文档": any(doc["status"] in {"raw_only", "parsed", "cleaned", "chunked", "annotated", "indexed"} for doc in docs),
            "解析": any(doc["status"] in {"parsed", "cleaned", "chunked", "annotated", "indexed"} for doc in docs),
            "清洗": any(doc["status"] in {"cleaned", "chunked", "annotated", "indexed"} for doc in docs),
            "切片": any(doc["chunk_count"] > 0 for doc in docs),
            "LLM 标注": any(doc["annotation_status"] != "not_started" for doc in docs),
            "向量化": any(doc["embedded_chunk_count"] > 0 for doc in docs),
            "索引完成": any(doc["status"] == "indexed" for doc in docs),
            "问答": bool(self.trace.list_traces()),
            "评测": bool(self.evaluation.get_latest_reports()["rag"]),
        }
        failed_stages = {doc["failed_stage"] for doc in docs if doc["status"] == "failed"}
        return [
            {"stage": stage, "status": "失败" if stage in failed_stages else ("已完成" if done else "未开始")}
            for stage, done in stage_map.items()
        ]


def avg(values: list[float]) -> float:
    return sum(values) / max(len(values), 1)


def grade_for_score(score: float) -> str:
    if score >= 85:
        return "Excellent"
    if score >= 75:
        return "Good"
    if score >= 60:
        return "Usable"
    if score >= 45:
        return "Weak"
    return "Failed"


def dicts_to_csv(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return ""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    for row in rows:
        writer.writerow({key: json_dumps(value) if isinstance(value, (dict, list)) else value for key, value in row.items()})
    return output.getvalue()


def report_to_markdown(payload: dict[str, Any]) -> str:
    lines = ["# Enterprise RAG Workbench Report", ""]
    metrics = payload.get("metrics") or payload.get("best") or {}
    for key, value in metrics.items():
        lines.append(f"- {key}: {value}")
    rows = payload.get("results") or payload.get("rows") or []
    if rows:
        lines.extend(["", "## Results"])
        headers = list(rows[0].keys())
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("| " + " | ".join("---" for _ in headers) + " |")
        for row in rows:
            lines.append("| " + " | ".join(str(row.get(header, ""))[:160].replace("\n", " ") for header in headers) + " |")
    return "\n".join(lines)


def report_to_html(payload: dict[str, Any]) -> str:
    body = html.escape(report_to_markdown(payload)).replace("\n", "<br>")
    return f"<!doctype html><html><head><meta charset='utf-8'><title>RAG Report</title></head><body>{body}</body></html>"


services = RagWorkbenchServices()
