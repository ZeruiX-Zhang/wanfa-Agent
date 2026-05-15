from __future__ import annotations

import json
from pathlib import Path

from rag_core.rag.embedding import cosine_similarity, embed_text
from rag_core.rag.filters import chunk_matches_filters
from rag_core.rag.models import Chunk, SearchFilters, SearchResult, candidate_k_for
from rag_core.rag.settings import rag_storage_dir
from rag_core.rag.vector_stores.base import BaseVectorStore


class FaissVectorStore(BaseVectorStore):
    """Local dense vector store with FAISS-compatible semantics.

    The project previously had no working FAISS dependency. This backend keeps
    the local file-based contract and can later be swapped to a native FAISS
    index without changing retriever/service code.
    """

    def __init__(self, storage_dir: Path | None = None) -> None:
        self.storage_dir = storage_dir or rag_storage_dir()
        self.chunks_path = self.storage_dir / "chunks.jsonl"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._chunks: list[Chunk] | None = None

    def replace_chunks(self, chunks: list[Chunk]) -> None:
        self._chunks = list(chunks)
        self._write_chunks(self._chunks)

    def upsert_chunks(self, chunks: list[Chunk]) -> None:
        existing = {chunk.chunk_id: chunk for chunk in self.list_chunks()}
        for chunk in chunks:
            existing[chunk.chunk_id] = chunk
        self.replace_chunks(list(existing.values()))

    def delete_document(self, document_id: str) -> int:
        chunks = self.list_chunks()
        kept = [chunk for chunk in chunks if chunk.document_id != document_id]
        self.replace_chunks(kept)
        return len(chunks) - len(kept)

    def reindex_document(self, document_id: str, chunks: list[Chunk]) -> None:
        self.delete_document(document_id)
        self.upsert_chunks(chunks)

    def list_chunks(self) -> list[Chunk]:
        if self._chunks is not None:
            return list(self._chunks)
        if not self.chunks_path.exists():
            self._chunks = []
            return []
        loaded: list[Chunk] = []
        with self.chunks_path.open("r", encoding="utf-8-sig") as file:
            for line in file:
                if line.strip():
                    loaded.append(Chunk.model_validate_json(line))
        self._chunks = loaded
        return list(loaded)

    def search(
        self,
        query: str,
        top_k: int,
        filters: SearchFilters | None = None,
        candidate_k: int | None = None,
    ) -> tuple[list[SearchResult], dict[str, int]]:
        filters = filters or SearchFilters()
        candidate_k = candidate_k or candidate_k_for(top_k, bool(filters.domain))
        query_vector = embed_text(query)
        scored: list[SearchResult] = []
        for chunk in self.list_chunks():
            if not chunk_matches_filters(chunk, filters, include_domain=False):
                continue
            score = cosine_similarity(query_vector, embed_text(chunk.searchable_text))
            scored.append(SearchResult(chunk=chunk, score=score, rank=0, source="dense"))

        scored.sort(key=lambda item: item.score, reverse=True)
        candidates = scored[:candidate_k]
        before_filter_count = len(candidates)
        if filters.domain:
            candidates = [item for item in candidates if item.chunk.domain == filters.domain]
        after_filter_count = len(candidates)
        selected = candidates[: max(top_k, 1)]
        for index, item in enumerate(selected, start=1):
            item.rank = index
        debug = {
            "requested_top_k": max(top_k, 1),
            "candidate_k": candidate_k,
            "before_filter_count": before_filter_count,
            "after_filter_count": after_filter_count,
        }
        return selected, debug

    def _write_chunks(self, chunks: list[Chunk]) -> None:
        tmp_path = self.chunks_path.with_suffix(".jsonl.tmp")
        with tmp_path.open("w", encoding="utf-8") as file:
            for chunk in chunks:
                file.write(json.dumps(chunk.model_dump(mode="json"), ensure_ascii=False) + "\n")
        tmp_path.replace(self.chunks_path)

