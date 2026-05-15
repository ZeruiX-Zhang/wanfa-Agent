from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np

from app.core.errors import AppError
from app.schemas.documents import DocumentChunk, RetrievedChunk


class FaissVectorStore:
    def __init__(self, storage_dir: Path) -> None:
        self.storage_dir = storage_dir
        self.index_path = storage_dir / "index.faiss"
        self.chunks_path = storage_dir / "chunks.jsonl"

    def save(self, vectors: list[list[float]], chunks: list[DocumentChunk]) -> None:
        if len(vectors) != len(chunks):
            raise AppError("Embedding count does not match chunk count", status_code=500, code="embedding_count_mismatch")
        try:
            import faiss
        except ImportError as exc:
            raise AppError("faiss-cpu is required to build the vector index", status_code=500, code="missing_dependency") from exc

        matrix = self._normalize(np.array(vectors, dtype="float32"))
        index = faiss.IndexFlatIP(matrix.shape[1])
        index.add(matrix)

        self.storage_dir.mkdir(parents=True, exist_ok=True)
        faiss.write_index(index, str(self.index_path))
        with self.chunks_path.open("w", encoding="utf-8") as file:
            for chunk in chunks:
                file.write(json.dumps(chunk.model_dump(), ensure_ascii=False) + "\n")

    def search(self, query_vector: list[float], top_k: int, domain: str | None = None) -> list[RetrievedChunk]:
        try:
            import faiss
        except ImportError as exc:
            raise AppError("faiss-cpu is required to search the vector index", status_code=500, code="missing_dependency") from exc
        if not self.index_path.exists() or not self.chunks_path.exists():
            raise AppError("Vector index has not been built", status_code=404, code="index_not_found")

        index = faiss.read_index(str(self.index_path))
        chunks = self._read_chunks()
        query = self._normalize(np.array([query_vector], dtype="float32"))
        search_k = len(chunks) if domain else min(top_k, len(chunks))
        scores, indexes = index.search(query, search_k)

        results: list[RetrievedChunk] = []
        for score, item_index in zip(scores[0].tolist(), indexes[0].tolist()):
            if item_index < 0:
                continue
            chunk = chunks[item_index]
            if domain and chunk.metadata.domain != domain:
                continue
            results.append(
                RetrievedChunk(
                    chunk_id=chunk.chunk_id,
                    text=chunk.text,
                    metadata=chunk.metadata,
                    score=float(score),
                )
            )
            if len(results) >= top_k:
                break
        return results

    def copy_chunks_from(self, source_path: Path) -> None:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, self.chunks_path)

    def _read_chunks(self) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        with self.chunks_path.open("r", encoding="utf-8") as file:
            for line in file:
                if line.strip():
                    chunks.append(DocumentChunk.model_validate(json.loads(line)))
        return chunks

    @staticmethod
    def _normalize(matrix: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0.0] = 1.0
        return matrix / norms
