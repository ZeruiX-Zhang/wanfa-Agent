from __future__ import annotations

from rag_core.rag.models import SearchResult
from rag_core.rag.rerankers.base import BaseReranker
from rag_core.rag.rerankers.simple_reranker import SimpleReranker


class LLMReranker(BaseReranker):
    provider = "llm"

    def __init__(self) -> None:
        self._fallback = SimpleReranker()

    def rerank(self, query: str, results: list[SearchResult], top_n: int) -> list[SearchResult]:
        # Placeholder for provider-backed LLM reranking. The fallback keeps the
        # interface usable offline and avoids external calls without config.
        return self._fallback.rerank(query, results, top_n)


