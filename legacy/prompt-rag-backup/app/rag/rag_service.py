from __future__ import annotations

import time

from app.llm.llm_client import LLMClient
from app.rag.prompt_builder import PromptBuilder
from app.rag.prompts import RAG_SYSTEM_PROMPT
from app.rag.retriever import Retriever
from app.router.domain_router import DomainRouter
from app.schemas.documents import RetrievedChunk
from app.schemas.domain import DomainRequestValue
from app.schemas.rag import RAGDebugResponse, RAGQueryResponse, RAGSource


class RAGService:
    def __init__(
        self,
        retriever: Retriever | None = None,
        llm_client: LLMClient | None = None,
        prompt_builder: PromptBuilder | None = None,
        domain_router: DomainRouter | None = None,
    ) -> None:
        self.retriever = retriever or Retriever()
        self.llm_client = llm_client or LLMClient()
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.domain_router = domain_router or DomainRouter()

    def query(self, question: str, top_k: int, trace_id: str, domain: DomainRequestValue = "auto") -> RAGQueryResponse:
        result = self._run(question=question, top_k=top_k, domain=domain)
        return RAGQueryResponse(
            success=True,
            answer=result["answer"],
            sources=result["sources"],
            selected_domain=result["selected_domain"],
            router_confidence=result["router_confidence"],
            router_reason=result["router_reason"],
            latency_ms=result["latency_ms"],
            trace_id=trace_id,
        )

    def debug(self, question: str, top_k: int, trace_id: str, domain: DomainRequestValue = "auto") -> RAGDebugResponse:
        result = self._run(question=question, top_k=top_k, domain=domain)
        return RAGDebugResponse(
            success=True,
            answer=result["answer"],
            sources=result["sources"],
            selected_domain=result["selected_domain"],
            router_confidence=result["router_confidence"],
            router_reason=result["router_reason"],
            latency_ms=result["latency_ms"],
            trace_id=trace_id,
            retrieved_chunks=result["chunks"],
            prompt=result["prompt"],
            retrieval_latency_ms=result["retrieval_latency_ms"],
            llm_latency_ms=result["llm_latency_ms"],
        )

    def _run(self, question: str, top_k: int, domain: DomainRequestValue) -> dict[str, object]:
        start = time.perf_counter()
        route = self.domain_router.route(question, requested_domain=domain)
        retrieval_start = time.perf_counter()
        chunks = self.retriever.retrieve(question, top_k=top_k, domain=route.domain)
        retrieval_latency_ms = (time.perf_counter() - retrieval_start) * 1000

        user_prompt = self.prompt_builder.build_user_prompt(question, chunks)
        debug_prompt = self.prompt_builder.build_debug_prompt(question, chunks)

        llm_latency_ms = 0.0
        if chunks:
            llm_start = time.perf_counter()
            answer = self.llm_client.chat(
                messages=[
                    {"role": "system", "content": RAG_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
            )
            llm_latency_ms = (time.perf_counter() - llm_start) * 1000
        else:
            answer = "\u4e0d\u77e5\u9053\n\nsources: []"

        sources = self._build_sources(chunks)
        answer = self._ensure_sources_in_answer(answer, sources)
        return {
            "answer": answer,
            "sources": sources,
            "chunks": chunks,
            "prompt": debug_prompt,
            "selected_domain": route.domain,
            "router_confidence": route.confidence,
            "router_reason": route.reason,
            "retrieval_latency_ms": retrieval_latency_ms,
            "llm_latency_ms": llm_latency_ms,
            "latency_ms": (time.perf_counter() - start) * 1000,
        }

    def _build_sources(self, chunks: list[RetrievedChunk]) -> list[RAGSource]:
        return [
            RAGSource(
                domain=chunk.metadata.domain,
                filename=chunk.metadata.filename,
                page=chunk.metadata.page,
                chunk_id=chunk.chunk_id,
                score=chunk.score,
            )
            for chunk in chunks
        ]

    def _ensure_sources_in_answer(self, answer: str, sources: list[RAGSource]) -> str:
        lowered = answer.lower()
        if "sources" in lowered or "\u6765\u6e90" in answer:
            return answer
        source_labels = [f"{source.filename}:{source.chunk_id}" for source in sources]
        return f"{answer}\n\nsources: {source_labels}"
