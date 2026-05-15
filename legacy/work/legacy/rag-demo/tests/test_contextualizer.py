from __future__ import annotations

import shutil
import uuid

from app.core.config import AGENT_CORE_ROOT
from app.rag.contextualizer import TemplateContextualizer
from app.rag.models import Chunk, SearchFilters
from app.rag.retrievers.bm25_retriever import BM25Retriever
from app.rag.service import RAGService, RequestContext
from app.rag.vector_stores.faiss_store import FaissVectorStore


def test_template_contextualizer_fallback_contains_metadata() -> None:
    chunk = Chunk(
        id="chunk",
        document_id="doc",
        chunk_id="chunk",
        domain="customer_support",
        filename="handbook.md",
        section_path="sla/p1",
        page=3,
        text="First response is required.",
    )

    contextual_text = TemplateContextualizer().contextualize(chunk)

    assert "customer_support" in contextual_text
    assert "handbook.md" in contextual_text
    assert "sla/p1" in contextual_text
    assert "First response is required." in contextual_text


def test_contextual_text_is_written_to_chunks_jsonl() -> None:
    storage_dir = AGENT_CORE_ROOT / ".pytest_tmp" / f"rag-context-{uuid.uuid4().hex}"
    storage_dir.mkdir(parents=True, exist_ok=True)
    store = FaissVectorStore(storage_dir)
    try:
        RAGService(store).ingest_chunks(
            [
                Chunk(
                    id="chunk",
                    document_id="doc",
                    chunk_id="chunk",
                    domain="customer_support",
                    filename="handbook.md",
                    section_path="sla/p1",
                    text="First response is required.",
                )
            ],
            replace=True,
        )

        loaded = FaissVectorStore(storage_dir).list_chunks()[0]
        assert loaded.text == "First response is required."
        assert loaded.contextual_text
        assert "customer_support" in loaded.contextual_text
    finally:
        shutil.rmtree(storage_dir, ignore_errors=True)


def test_contextual_text_is_used_by_bm25_and_debug() -> None:
    storage_dir = AGENT_CORE_ROOT / ".pytest_tmp" / f"rag-context-bm25-{uuid.uuid4().hex}"
    storage_dir.mkdir(parents=True, exist_ok=True)
    store = FaissVectorStore(storage_dir)
    try:
        service = RAGService(store)
        service.ingest_chunks(
            [
                Chunk(
                    id="chunk",
                    document_id="doc",
                    chunk_id="chunk",
                    domain="customer_support",
                    filename="support_handbook.md",
                    section_path="sla/p1",
                    text="First response is required.",
                )
            ],
            replace=True,
        )
        results, _ = BM25Retriever(store).retrieve(
            "customer_support support_handbook",
            top_k=1,
            filters=SearchFilters(tenant_id="default", access_roles=["reader"]),
        )
        debug = service.debug_query(
            "customer_support support_handbook",
            top_k=1,
            context=RequestContext(tenant_id="default", roles=["reader"]),
        )

        assert results[0].chunk.chunk_id == "chunk"
        assert debug["contextual_text_used"] is True
    finally:
        shutil.rmtree(storage_dir, ignore_errors=True)

