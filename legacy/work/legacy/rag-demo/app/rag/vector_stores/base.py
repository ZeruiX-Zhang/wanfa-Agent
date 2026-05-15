from __future__ import annotations

from abc import ABC, abstractmethod

from app.rag.models import Chunk, SearchFilters, SearchResult


class BaseVectorStore(ABC):
    @abstractmethod
    def replace_chunks(self, chunks: list[Chunk]) -> None:
        raise NotImplementedError

    @abstractmethod
    def upsert_chunks(self, chunks: list[Chunk]) -> None:
        raise NotImplementedError

    @abstractmethod
    def delete_document(self, document_id: str) -> int:
        raise NotImplementedError

    @abstractmethod
    def list_chunks(self) -> list[Chunk]:
        raise NotImplementedError

    @abstractmethod
    def search(
        self,
        query: str,
        top_k: int,
        filters: SearchFilters | None = None,
        candidate_k: int | None = None,
    ) -> tuple[list[SearchResult], dict[str, int]]:
        raise NotImplementedError

