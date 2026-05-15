from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.rag.chunker import TextChunker
from app.rag.document_loader import DocumentLoader
from app.rag.index_service import IndexService
from app.rag.text_cleaner import clean_text
from app.schemas.documents import DocumentChunk, DocumentMetadata, IngestLocalResponse
from app.schemas.domain import DomainName


DOMAIN_SCENARIOS: dict[str, str] = {
    "enterprise_kb": "enterprise_knowledge_base",
    "customer_support": "customer_support_sla",
    "finance_research": "finance_research_briefing",
    "ops_runbook": "operations_runbook",
    "legal_contract": "legal_contract_review",
    "data_analysis": "data_analysis_workspace",
}

DOMAIN_ACCESS_ROLES: dict[str, list[str]] = {
    "enterprise_kb": ["employee"],
    "customer_support": ["support", "support_manager"],
    "finance_research": ["finance", "analyst"],
    "ops_runbook": ["ops", "sre"],
    "legal_contract": ["legal", "manager"],
    "data_analysis": ["analyst", "manager"],
}


class DocumentIngestionService:
    def __init__(
        self,
        project_root: Path | None = None,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
        output_path: Path | None = None,
    ) -> None:
        self.project_root = (project_root or settings.project_root).resolve()
        self.loader = DocumentLoader(self.project_root)
        self.chunker = TextChunker(chunk_size or settings.chunk_size, chunk_overlap or settings.chunk_overlap)
        self.output_path = output_path

    def ingest_local(
        self,
        domain: DomainName,
        directory: str,
        glob_pattern: str,
        trace_id: str,
        build_index: bool = False,
    ) -> IngestLocalResponse:
        documents = self.loader.load_directory(directory, glob_pattern)
        output_path = self.output_path or self.project_root / "data" / "processed" / domain / "chunks.jsonl"
        chunks = self._chunk_documents(documents, domain)
        self._write_chunks(chunks, output_path)
        index_built = False
        if build_index:
            IndexService(project_root=self.project_root).build_index()
            index_built = True
        return IngestLocalResponse(
            success=True,
            documents_loaded=len(documents),
            chunks_created=len(chunks),
            output_path=self._relative(output_path),
            index_built=index_built,
            trace_id=trace_id,
        )

    def _chunk_documents(self, documents: list[Any], domain: DomainName) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        chunk_counts_by_file: dict[str, int] = {}
        for document in documents:
            cleaned = clean_text(document.text)
            filename = document.metadata["filename"]
            next_index = chunk_counts_by_file.get(filename, 0)
            for text in self.chunker.split_text(cleaned):
                metadata = dict(document.metadata)
                metadata["chunk_index"] = next_index
                metadata["domain"] = domain
                metadata["scenario"] = DOMAIN_SCENARIOS[domain]
                metadata["tenant_id"] = "demo_tenant"
                metadata["access_roles"] = DOMAIN_ACCESS_ROLES[domain]
                chunks.append(
                    DocumentChunk(
                        chunk_id=f"{domain}/{filename}::{next_index}",
                        text=text,
                        metadata=DocumentMetadata(**metadata),
                    )
                )
                next_index += 1
            chunk_counts_by_file[filename] = next_index
        return chunks

    def _write_chunks(self, chunks: list[DocumentChunk], output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as file:
            for chunk in chunks:
                file.write(json.dumps(chunk.model_dump(), ensure_ascii=False) + "\n")

    def _relative(self, path: Path) -> str:
        return path.resolve().relative_to(self.project_root).as_posix()
