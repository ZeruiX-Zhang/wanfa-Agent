from __future__ import annotations

from abc import ABC, abstractmethod

from rag_core.rag.models import SearchResult


class BaseReranker(ABC):
    provider: str

    @abstractmethod
    def rerank(self, query: str, results: list[SearchResult], top_n: int) -> list[SearchResult]:
        raise NotImplementedError


