from __future__ import annotations

from abc import ABC, abstractmethod

from app.rag.models import SearchFilters, SearchResult


class BaseRetriever(ABC):
    @abstractmethod
    def retrieve(self, query: str, top_k: int, filters: SearchFilters | None = None) -> tuple[list[SearchResult], dict[str, object]]:
        raise NotImplementedError

