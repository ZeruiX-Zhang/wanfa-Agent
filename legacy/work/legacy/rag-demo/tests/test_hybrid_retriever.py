from __future__ import annotations

import shutil
import uuid

from app.core.config import AGENT_CORE_ROOT
from app.rag.models import Chunk, SearchFilters
from app.rag.retrievers.bm25_retriever import BM25Retriever
from app.rag.retrievers.faiss_retriever import FaissRetriever
from app.rag.service import RAGService, RequestContext
from app.rag.vector_stores.faiss_store import FaissVectorStore


def _store() -> tuple[FaissVectorStore, object]:
    storage_dir = AGENT_CORE_ROOT / ".pytest_tmp" / f"rag-hybrid-{uuid.uuid4().hex}"
    storage_dir.mkdir(parents=True, exist_ok=True)
    store = FaissVectorStore(storage_dir)
    store.replace_chunks(
        [
            Chunk(
                id="support-p1",
                document_id="support",
                chunk_id="support-p1",
                domain="customer_support",
                text="P1 customer support incidents require 15 minute SLA response and escalation.",
                filename="support.md",
            ),
            Chunk(
                id="ops-e503",
                document_id="ops",
                chunk_id="ops-e503",
                domain="ops_runbook",
                text="ERROR E503 upstream gateway failure requires runbook restart and incident escalation.",
                filename="ops.md",
            ),
            Chunk(
                id="enterprise-semantic",
                document_id="enterprise",
                chunk_id="enterprise-semantic",
                domain="enterprise_kb",
                text="Enterprise semantic knowledge architecture links policy strategy and governance.",
                filename="enterprise.md",
            ),
        ]
    )
    return store, storage_dir


def test_bm25_hits_customer_support_p1_sla() -> None:
    store, storage_dir = _store()
    try:
        results, _ = BM25Retriever(store).retrieve(
            "P1 SLA response",
            top_k=3,
            filters=SearchFilters(domain="customer_support", tenant_id="default", access_roles=["reader"]),
        )
        assert results[0].chunk.chunk_id == "support-p1"
    finally:
        shutil.rmtree(storage_dir, ignore_errors=True)


def test_bm25_hits_ops_error_code() -> None:
    store, storage_dir = _store()
    try:
        results, _ = BM25Retriever(store).retrieve(
            "ERROR E503 runbook",
            top_k=3,
            filters=SearchFilters(domain="ops_runbook", tenant_id="default", access_roles=["reader"]),
        )
        assert results[0].chunk.chunk_id == "ops-e503"
    finally:
        shutil.rmtree(storage_dir, ignore_errors=True)


def test_dense_hits_enterprise_semantic_query() -> None:
    store, storage_dir = _store()
    try:
        results, _ = FaissRetriever(store).retrieve(
            "semantic architecture strategy governance",
            top_k=3,
            filters=SearchFilters(domain="enterprise_kb", tenant_id="default", access_roles=["reader"]),
        )
        assert results[0].chunk.chunk_id == "enterprise-semantic"
    finally:
        shutil.rmtree(storage_dir, ignore_errors=True)


def test_hybrid_fusion_returns_correct_domain_chunk() -> None:
    store, storage_dir = _store()
    try:
        debug = RAGService(store).debug_query(
            "Which P1 SLA response applies to customer support?",
            top_k=2,
            context=RequestContext(tenant_id="default", roles=["reader"]),
        )
        assert debug["retrieval_mode"] == "hybrid"
        assert debug["selected_domain"] == "customer_support"
        assert debug["router_confidence"] > 0
        assert debug["dense_results"]
        assert debug["bm25_results"]
        assert debug["fused_results"][0]["chunk_id"] == "support-p1"
    finally:
        shutil.rmtree(storage_dir, ignore_errors=True)

