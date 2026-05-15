from __future__ import annotations

from rag_core.rag.models import SearchFilters, SearchResult, candidate_k_for
from rag_core.rag.retrievers.base import BaseRetriever
from rag_core.rag.vector_stores.faiss_store import FaissVectorStore


class FaissRetriever(BaseRetriever):
    def __init__(self, vector_store: FaissVectorStore | None = None) -> None:
        self.vector_store = vector_store or FaissVectorStore()

    def retrieve(
        self,
        query: str,
        top_k: int,
        filters: SearchFilters | None = None,
    ) -> tuple[list[SearchResult], dict[str, object]]:
        filters = filters or SearchFilters()
        candidate_k = candidate_k_for(top_k, bool(filters.domain))
        results, debug = self.vector_store.search(query, top_k=top_k, filters=filters, candidate_k=candidate_k)
        return results, debug


