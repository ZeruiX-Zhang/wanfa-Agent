from __future__ import annotations

from time import perf_counter

from app.rag.models import SearchFilters, SearchResult, candidate_k_for
from app.rag.rank_fusion import reciprocal_rank_fusion
from app.rag.retrievers.base import BaseRetriever
from app.rag.retrievers.bm25_retriever import BM25Retriever
from app.rag.retrievers.faiss_retriever import FaissRetriever
from app.rag.settings import env_int


class HybridRetriever(BaseRetriever):
    def __init__(
        self,
        dense_retriever: FaissRetriever | None = None,
        bm25_retriever: BM25Retriever | None = None,
        dense_top_k: int | None = None,
        bm25_top_k: int | None = None,
        rrf_k: int | None = None,
    ) -> None:
        self.dense_retriever = dense_retriever or FaissRetriever()
        self.bm25_retriever = bm25_retriever or BM25Retriever()
        self.dense_top_k = dense_top_k or env_int("DENSE_TOP_K", 20)
        self.bm25_top_k = bm25_top_k or env_int("BM25_TOP_K", 20)
        self.rrf_k = rrf_k or env_int("RRF_K", 60)

    def retrieve(
        self,
        query: str,
        top_k: int,
        filters: SearchFilters | None = None,
    ) -> tuple[list[SearchResult], dict[str, object]]:
        dense_start = perf_counter()
        dense_results, dense_debug = self.dense_retriever.vector_store.search(
            query,
            top_k=self.dense_top_k,
            filters=filters,
            candidate_k=candidate_k_for(top_k, bool(filters and filters.domain)),
        )
        dense_latency_ms = round((perf_counter() - dense_start) * 1000, 3)
        bm25_start = perf_counter()
        bm25_results, bm25_debug = self.bm25_retriever.retrieve(query, self.bm25_top_k, filters)
        bm25_latency_ms = round((perf_counter() - bm25_start) * 1000, 3)
        fusion_start = perf_counter()
        fused_results = reciprocal_rank_fusion([dense_results, bm25_results], top_k=top_k, rrf_k=self.rrf_k)
        fusion_latency_ms = round((perf_counter() - fusion_start) * 1000, 3)
        return fused_results, {
            "dense_results": dense_results,
            "bm25_results": bm25_results,
            "fused_results": fused_results,
            "dense_debug": dense_debug,
            "bm25_debug": bm25_debug,
            "rrf_k": self.rrf_k,
            "dense_latency_ms": dense_latency_ms,
            "bm25_latency_ms": bm25_latency_ms,
            "fusion_latency_ms": fusion_latency_ms,
        }
