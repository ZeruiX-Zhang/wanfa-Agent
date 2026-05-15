from __future__ import annotations

import re
from pathlib import Path

from app.core.config import AGENT_CORE_ROOT
from app.rag.models import Chunk
from app.security.path_guard import ensure_within_allowed_path


def read_document_text(path: Path) -> str:
    last_error: UnicodeDecodeError | None = None
    for encoding in ("utf-8-sig", "utf-8"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    return ""


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
        if file.suffix.lower() not in {".md", ".txt", ".csv"}:
            continue
        text = read_document_text(file)
        if file.suffix.lower() == ".csv":
            paragraphs = [text.strip()] if text.strip() else []
        else:
            paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
        document_id = file.stem
        file_domain = domain or infer_domain(file)
        for index, paragraph in enumerate(paragraphs, start=1):
            chunk_id = f"{document_id}:{index}"
            chunks.append(
                Chunk(
                    id=chunk_id,
                    document_id=document_id,
                    chunk_id=chunk_id,
                    domain=file_domain,
                    tenant_id=tenant_id,
                    doc_type=doc_type,
                    access_roles=access_roles,
                    section_path=f"paragraph-{index}",
                    filename=file.name,
                    page=index,
                    text=paragraph,
                    metadata={"tenant_id": tenant_id, "domain": file_domain, "access_roles": access_roles},
                )
            )
    return chunks
