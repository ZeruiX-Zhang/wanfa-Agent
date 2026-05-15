from __future__ import annotations

import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from rag_core.core.config import AGENT_CORE_ROOT
from rag_core.rag.embedding import tokenize
from rag_core.rag.models import Chunk
from rag_core.rag.settings import env_int, env_str
from rag_core.security.path_guard import ensure_within_allowed_path


def read_document_text(path: Path) -> str:
    if path.suffix.lower() == ".docx":
        return _read_docx_text(path)
    if path.suffix.lower() == ".pdf":
        return path.read_bytes().decode("utf-8", errors="ignore")
    last_error: UnicodeDecodeError | None = None
    for encoding in ("utf-8-sig", "utf-8"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    return ""


def _read_docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        xml_bytes = archive.read("word/document.xml")
    root = ET.fromstring(xml_bytes)
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", namespace):
        texts = [node.text or "" for node in paragraph.findall(".//w:t", namespace)]
        text = "".join(texts).strip()
        if text:
            paragraphs.append(text)
    return "\n\n".join(paragraphs)


def infer_domain(path: Path, fallback: str = "enterprise_kb") -> str:
    name = " ".join(part.lower() for part in path.parts)
    if "support" in name or "customer" in name:
        return "customer_support"
    if "ops" in name or "runbook" in name:
        return "ops_runbook"
    if "legal" in name or "contract" in name or "msa" in name:
        return "legal_contract"
    if "data_analysis" in name or "sales" in name or path.suffix.lower() == ".csv":
        return "data_analysis"
    if "enterprise" in name or "kb" in name:
        return "enterprise_kb"
    return fallback


def parse_document(path: Path) -> str:
    text = read_document_text(path)
    if path.suffix.lower() in {".html", ".htm"}:
        text = re.sub(r"<script.*?</script>", " ", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<style.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def document_overrides(text: str) -> tuple[str, dict[str, object]]:
    if not text.startswith("---\n"):
        return text, {}
    end = text.find("\n---", 4)
    if end == -1:
        return text, {}
    header = text[4:end].strip()
    body = text[end + 4 :].lstrip()
    overrides: dict[str, object] = {}
    for line in header.splitlines():
        if ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        key = key.strip()
        value = raw_value.strip()
        if key == "access_roles":
            overrides[key] = [item.strip() for item in value.split(",") if item.strip()]
        elif key in {"domain", "doc_type"} and value:
            overrides[key] = value
    return body, overrides


def chunk_text(text: str, strategy: str | None = None, chunk_size: int | None = None, overlap: int | None = None) -> list[tuple[str, str, int]]:
    strategy = strategy or env_str("CHUNK_STRATEGY", "heading-aware")
    chunk_size = chunk_size or env_int("CHUNK_SIZE", 800)
    overlap = overlap if overlap is not None else env_int("CHUNK_OVERLAP", 120)
    if strategy in {"heading-aware", "recursive"}:
        chunks = _heading_chunks(text, chunk_size)
        if chunks:
            return chunks
    return _fixed_chunks(text, chunk_size, overlap)


def _heading_chunks(text: str, chunk_size: int) -> list[tuple[str, str, int]]:
    sections: list[tuple[str, list[str]]] = []
    current_heading = "document"
    current_lines: list[str] = []
    for line in text.splitlines():
        if re.match(r"^\s{0,3}#{1,6}\s+", line):
            if current_lines:
                sections.append((current_heading, current_lines))
            current_heading = line.strip("# ").strip() or "section"
            current_lines = [line]
        else:
            current_lines.append(line)
    if current_lines:
        sections.append((current_heading, current_lines))
    chunks: list[tuple[str, str, int]] = []
    for heading, lines in sections:
        section_text = "\n".join(lines).strip()
        if not section_text:
            continue
        if len(section_text) <= chunk_size:
            chunks.append((heading, section_text, len(tokenize(section_text))))
        else:
            chunks.extend((heading, chunk, token_count) for _, chunk, token_count in _fixed_chunks(section_text, chunk_size, 80))
    return chunks


def _fixed_chunks(text: str, chunk_size: int, overlap: int) -> list[tuple[str, str, int]]:
    clean = text.strip()
    if not clean:
        return []
    chunks: list[tuple[str, str, int]] = []
    start = 0
    safe_overlap = max(0, min(overlap, chunk_size // 2))
    while start < len(clean):
        end = min(len(clean), start + chunk_size)
        chunk = clean[start:end].strip()
        if chunk:
            chunks.append(("fixed", chunk, len(tokenize(chunk))))
        if end == len(clean):
            break
        start = max(end - safe_overlap, start + 1)
    return chunks


def load_local_documents(
    raw_path: str | None,
    tenant_id: str,
    access_roles: list[str],
    domain: str | None = None,
    doc_type: str = "kb",
    glob_pattern: str = "**/*",
) -> list[Chunk]:
    base = AGENT_CORE_ROOT
    requested = Path(raw_path) if raw_path else AGENT_CORE_ROOT / "data" / "raw"
    path = requested if requested.is_absolute() else AGENT_CORE_ROOT / requested
    path = ensure_within_allowed_path(path, [base])
    if path.is_dir():
        files = sorted(file for file in path.glob(glob_pattern or "**/*") if file.is_file())
    else:
        files = [path]
    chunks: list[Chunk] = []
    for file in files:
        ensure_within_allowed_path(file, [base])
        if file.suffix.lower() not in {".md", ".txt", ".csv", ".html", ".htm", ".pdf", ".docx"}:
            continue
        text, overrides = document_overrides(parse_document(file))
        if file.suffix.lower() == ".csv":
            chunk_payloads = [("csv", text.strip(), len(tokenize(text)))] if text.strip() else []
        else:
            chunk_payloads = chunk_text(text)
        document_id = file.stem
        file_domain = str(overrides.get("domain") or domain or infer_domain(file))
        file_access_roles = list(overrides.get("access_roles") or access_roles)
        file_doc_type = str(overrides.get("doc_type") or doc_type)
        for index, (section, paragraph, token_count) in enumerate(chunk_payloads, start=1):
            chunk_id = f"{document_id}:{index}"
            chunks.append(
                Chunk(
                    id=chunk_id,
                    document_id=document_id,
                    chunk_id=chunk_id,
                    domain=file_domain,
                    tenant_id=tenant_id,
                    doc_type=file_doc_type,
                    access_roles=file_access_roles,
                    section_path=section or f"chunk-{index}",
                    filename=file.name,
                    page=index,
                    text=paragraph,
                    metadata={
                        "tenant_id": tenant_id,
                        "domain": file_domain,
                        "access_roles": file_access_roles,
                        "doc_id": document_id,
                        "filename": file.name,
                        "page": index,
                        "section": section,
                        "chunk_index": index,
                        "token_count": token_count,
                        "source_path": str(file),
                        "status": "indexed",
                    },
                )
            )
    return chunks

