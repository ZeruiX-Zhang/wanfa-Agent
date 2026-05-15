from __future__ import annotations

import json
from pathlib import Path

from app.core.config import settings
from app.core.errors import AppError
from app.llm.llm_client import LLMClient
from app.rag.vector_store import FaissVectorStore
from app.schemas.documents import DocumentChunk


class IndexService:
    def __init__(
        self,
        project_root: Path | None = None,
        chunks_path: Path | None = None,
        vector_store: FaissVectorStore | None = None,
        llm_client: LLMClient | None = None,
    ) -> None:
        self.project_root = (project_root or settings.project_root).resolve()
        self.chunks_path = chunks_path
        self.vector_store = vector_store or FaissVectorStore(self.project_root / "storage" / "faiss")
        self.llm_client = llm_client or LLMClient()

    def build_index(self) -> int:
        chunks = self._read_chunks()
        if not chunks:
            raise AppError("No chunks found to index", status_code=400, code="empty_chunks")
        vectors = self.llm_client.embed_texts([chunk.text for chunk in chunks])
        self.vector_store.save(vectors=vectors, chunks=chunks)
        return len(chunks)

    def _read_chunks(self) -> list[DocumentChunk]:
        chunk_files = self._chunk_files()
        if not chunk_files:
            raise AppError("No processed domain chunks found", status_code=404, code="chunks_not_found")
        chunks: list[DocumentChunk] = []
        for chunks_path in chunk_files:
            with chunks_path.open("r", encoding="utf-8") as file:
                for line in file:
                    if line.strip():
                        chunks.append(DocumentChunk.model_validate(json.loads(line)))
        return chunks

    def _chunk_files(self) -> list[Path]:
        if self.chunks_path is not None:
            if not self.chunks_path.exists():
                raise AppError(
                    f"Chunks file not found: {self._relative(self.chunks_path)}",
                    status_code=404,
                    code="chunks_not_found",
                )
            return [self.chunks_path]

        processed_dir = self.project_root / "data" / "processed"
        if not processed_dir.exists():
            return []
        return sorted(processed_dir.glob("*/chunks.jsonl"))

    def _relative(self, path: Path) -> str:
        return path.resolve().relative_to(self.project_root).as_posix()
