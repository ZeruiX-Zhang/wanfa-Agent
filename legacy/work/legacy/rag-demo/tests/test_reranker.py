from __future__ import annotations

import shutil
import uuid

from app.core.config import AGENT_CORE_ROOT
from app.rag.models import Chunk, SearchResult
from app.rag.rerankers.simple_reranker import SimpleReranker
from app.rag.service import RAGService, RequestContext
from app.rag.vector_stores.faiss_store import FaissVectorStore


def test_simple_reranker_promotes_term_overlap() -> None:
    weak = SearchResult(
        chunk=Chunk(
            id="weak",
            document_id="doc",
            chunk_id="weak",
            domain="customer_support",
            text="general support guidance",
        ),
        score=0.5,
        rank=1,
    )
    strong = SearchResult(
        chunk=Chunk(
            id="strong",
            document_id="doc",
            chunk_id="strong",
            domain="customer_support",
            text="P1 SLA response escalation for customer support",
        ),
        score=0.2,
        rank=2,
    )

    reranked = SimpleReranker().rerank("P1 SLA response", [weak, strong], top_n=2)

    assert reranked[0].chunk.chunk_id == "strong"
    assert reranked[0].metadata["reranker_provider"] == "simple"


def test_rag_debug_includes_reranked_results() -> None:
    storage_dir = AGENT_CORE_ROOT / ".pytest_tmp" / f"rag-reranker-{uuid.uuid4().hex}"
    storage_dir.mkdir(parents=True, exist_ok=True)
    store = FaissVectorStore(storage_dir)
    try:
        store.replace_chunks(
            [
                Chunk(
                    id="support",
                    document_id="support",
                    chunk_id="support",
                    domain="customer_support",
                    text="P1 SLA response escalation for customer support",
                )
            ]
        )
        debug = RAGService(store).debug_query(
            "P1 SLA response",
            top_k=1,
            context=RequestContext(tenant_id="default", roles=["reader"]),
        )

        assert debug["reranked_results"]
        assert debug["reranker_latency_ms"] >= 0
        assert debug["results"][0]["chunk_id"] == "support"
    finally:
        shutil.rmtree(storage_dir, ignore_errors=True)

