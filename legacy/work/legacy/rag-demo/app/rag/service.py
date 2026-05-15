from __future__ import annotations

import uuid
from time import perf_counter
from dataclasses import dataclass, field
from typing import Any

from app.rag.models import Chunk, SearchFilters
from app.rag.contextualizer import build_contextualizer
from app.observability.events import record_rag_trace
from app.observability.tracing import new_trace_id
from app.router.domain_router import select_domain
from app.security.output_sanitizer import sanitize_output
from app.rag.rerankers.base import BaseReranker
from app.rag.rerankers.llm_reranker import LLMReranker
from app.rag.rerankers.simple_reranker import SimpleReranker
from app.rag.retrievers.bm25_retriever import BM25Retriever
from app.rag.retrievers.faiss_retriever import FaissRetriever
from app.rag.retrievers.hybrid_retriever import HybridRetriever
from app.rag.settings import env_bool, env_int, env_str
from app.rag.vector_stores.faiss_store import FaissVectorStore


@dataclass
class RequestContext:
    user_id: str = "anonymous"
    tenant_id: str = "default"
    roles: list[str] = field(default_factory=lambda: ["reader"])


class RAGService:
    def __init__(self, vector_store: FaissVectorStore | None = None) -> None:
        self.vector_store = vector_store or FaissVectorStore()
        self.dense_retriever = FaissRetriever(self.vector_store)
        self.bm25_retriever = BM25Retriever(self.vector_store)
        self.hybrid_retriever = HybridRetriever(self.dense_retriever, self.bm25_retriever)
        self.reranker = self._build_reranker()
        self.contextualizer = build_contextualizer()

    def ingest_chunks(self, chunks: list[Chunk], replace: bool = False) -> dict[str, int]:
        chunks = [self._with_contextual_text(chunk) for chunk in chunks]
        if replace:
            self.vector_store.replace_chunks(chunks)
        else:
            self.vector_store.upsert_chunks(chunks)
        return {
            "documents_loaded": len({chunk.document_id for chunk in chunks}),
            "chunks_created": len(chunks),
            "embeddings_created": len(chunks),
        }

    def query(
        self,
        query: str,
        top_k: int = 5,
        domain: str | None = None,
        context: RequestContext | None = None,
        doc_type: str | None = None,
    ) -> dict[str, Any]:
        debug = self.debug_query(query=query, top_k=top_k, domain=domain, context=context, doc_type=doc_type)
        llm_start = perf_counter()
        sources = debug.get("reranked_results") or debug["results"]
        answer = self._build_answer(query, sources)
        llm_latency_ms = round((perf_counter() - llm_start) * 1000, 3)
        record_rag_trace(
            {
                "trace_id": debug["trace_id"],
                "selected_domain": debug["selected_domain"],
                "router_latency_ms": debug["router_latency_ms"],
                "dense_latency_ms": debug["dense_latency_ms"],
                "bm25_latency_ms": debug["bm25_latency_ms"],
                "fusion_latency_ms": debug["fusion_latency_ms"],
                "reranker_latency_ms": debug["reranker_latency_ms"],
                "llm_latency_ms": llm_latency_ms,
                "total_latency_ms": round(debug["total_latency_ms"] + llm_latency_ms, 3),
                "model": "local-mock",
                "token_usage": {},
                "sources": sources,
            }
        )
        return {
            "answer": answer,
            "sources": sources,
            "debug": {key: value for key, value in debug.items() if key != "results"},
        }

    def debug_query(
        self,
        query: str,
        top_k: int = 5,
        domain: str | None = None,
        context: RequestContext | None = None,
        doc_type: str | None = None,
    ) -> dict[str, Any]:
        total_start = perf_counter()
        trace_id = new_trace_id()
        context = context or RequestContext()
        router_start = perf_counter()
        selected_domain, router_confidence = self._select_domain(query, domain)
        router_latency_ms = round((perf_counter() - router_start) * 1000, 3)
        filters = SearchFilters(
            tenant_id=context.tenant_id,
            domain=selected_domain,
            access_roles=context.roles,
            doc_type=doc_type,
        )
        retrieval_mode = env_str("RETRIEVAL_MODE", "hybrid")
        reranker_enabled = env_bool("RERANKER_ENABLED", True)
        recall_top_k = env_int("RETRIEVAL_CANDIDATES", 30) if reranker_enabled else top_k
        dense_latency_ms = 0.0
        bm25_latency_ms = 0.0
        fusion_latency_ms = 0.0
        if retrieval_mode == "dense":
            retrieval_start = perf_counter()
            results, retrieval_debug = self.dense_retriever.retrieve(query, top_k=recall_top_k, filters=filters)
            dense_latency_ms = round((perf_counter() - retrieval_start) * 1000, 3)
            dense_results = results
            bm25_results = []
            fused_results = results
        elif retrieval_mode == "bm25":
            retrieval_start = perf_counter()
            results, retrieval_debug = self.bm25_retriever.retrieve(query, top_k=recall_top_k, filters=filters)
            bm25_latency_ms = round((perf_counter() - retrieval_start) * 1000, 3)
            dense_results = []
            bm25_results = results
            fused_results = results
        else:
            retrieval_mode = "hybrid"
            results, retrieval_debug = self.hybrid_retriever.retrieve(query, top_k=recall_top_k, filters=filters)
            dense_latency_ms = float(retrieval_debug.get("dense_latency_ms", 0.0))
            bm25_latency_ms = float(retrieval_debug.get("bm25_latency_ms", 0.0))
            fusion_latency_ms = float(retrieval_debug.get("fusion_latency_ms", 0.0))
            dense_results = retrieval_debug["dense_results"]
            bm25_results = retrieval_debug["bm25_results"]
            fused_results = retrieval_debug["fused_results"]
            dense_debug = retrieval_debug.get("dense_debug", {})
            retrieval_debug = {
                "requested_top_k": top_k,
                "candidate_k": dense_debug.get("candidate_k", top_k),
                "before_filter_count": dense_debug.get("before_filter_count", len(dense_results)),
                "after_filter_count": dense_debug.get("after_filter_count", len(dense_results)),
            }
        reranked_results = []
        reranker_latency_ms = 0.0
        if reranker_enabled:
            rerank_top_n = env_int("RERANK_TOP_N", 5)
            reranker_start = perf_counter()
            reranked_results = self.reranker.rerank(query, fused_results, top_n=rerank_top_n)
            reranker_latency_ms = round((perf_counter() - reranker_start) * 1000, 3)
            results = reranked_results[: max(top_k, 1)]
        retrieval_debug = {
            "requested_top_k": retrieval_debug.get("requested_top_k", top_k),
            "candidate_k": retrieval_debug.get("candidate_k", top_k),
            "before_filter_count": retrieval_debug.get("before_filter_count", len(fused_results)),
            "after_filter_count": retrieval_debug.get("after_filter_count", len(fused_results)),
        }
        contextual_text_used = any(bool(result.chunk.contextual_text) for result in fused_results)
        dense_public = [self._sanitize_source(result.public_dict()) for result in dense_results]
        bm25_public = [self._sanitize_source(result.public_dict()) for result in bm25_results]
        fused_public = [self._sanitize_source(result.public_dict()) for result in fused_results]
        reranked_public = [self._sanitize_source(result.public_dict()) for result in reranked_results]
        results_public = [self._sanitize_source(result.public_dict()) for result in results]
        return {
            "query_id": str(uuid.uuid4()),
            "trace_id": trace_id,
            "retrieval_mode": retrieval_mode,
            "requested_top_k": retrieval_debug["requested_top_k"],
            "candidate_k": retrieval_debug["candidate_k"],
            "before_filter_count": retrieval_debug["before_filter_count"],
            "after_filter_count": retrieval_debug["after_filter_count"],
            "selected_domain": selected_domain,
            "router_confidence": router_confidence,
            "router_latency_ms": router_latency_ms,
            "dense_latency_ms": dense_latency_ms,
            "bm25_latency_ms": bm25_latency_ms,
            "fusion_latency_ms": fusion_latency_ms,
            "dense_results": dense_public,
            "bm25_results": bm25_public,
            "fused_results": fused_public,
            "reranked_results": reranked_public,
            "reranker_latency_ms": reranker_latency_ms,
            "contextual_text_used": contextual_text_used,
            "total_latency_ms": round((perf_counter() - total_start) * 1000, 3),
            "results": results_public,
            "sources": results_public,
        }

    def _build_answer(self, query: str, sources: list[dict[str, Any]]) -> str:
        if not sources:
            return "No authorized context was found for this query."
        snippets = " ".join(str(source.get("text", "")) for source in sources[:2])
        return sanitize_output(f"Based on retrieved context for '{query}': {snippets[:500]}")

    def _select_domain(self, query: str, requested_domain: str | None) -> tuple[str | None, float]:
        return select_domain(query, requested_domain)

    def _build_reranker(self) -> BaseReranker:
        provider = env_str("RERANKER_PROVIDER", "simple")
        if provider == "llm":
            return LLMReranker()
        return SimpleReranker()

    def _with_contextual_text(self, chunk: Chunk) -> Chunk:
        if not env_bool("CONTEXTUAL_RETRIEVAL_ENABLED", True):
            return chunk
        if chunk.contextual_text:
            return chunk
        data = chunk.model_dump()
        data["contextual_text"] = self.contextualizer.contextualize(chunk)
        return Chunk.model_validate(data)

    def _sanitize_source(self, source: dict[str, Any]) -> dict[str, Any]:
        cleaned = dict(source)
        if "text" in cleaned:
            cleaned["text"] = sanitize_output(str(cleaned["text"]))
        return cleaned


rag_service = RAGService()
