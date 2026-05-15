from __future__ import annotations

import shutil
import uuid

import pytest

from app.core.config import AGENT_CORE_ROOT
from app.rag.models import Chunk
from app.rag.service import RAGService, RequestContext
from app.rag.vector_stores.faiss_store import FaissVectorStore


def test_domain_filter_uses_candidate_window_when_top_k_is_small(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RERANKER_ENABLED", "false")
    storage_dir = AGENT_CORE_ROOT / ".pytest_tmp" / f"rag-domain-{uuid.uuid4().hex}"
    storage_dir.mkdir(parents=True, exist_ok=True)
    store = FaissVectorStore(storage_dir)
    chunks = [
        Chunk(
            id=f"ops-{index}",
            document_id="ops-doc",
            chunk_id=f"ops-{index}",
            domain="ops_runbook",
            text="P1 SLA escalation shared keyword",
            filename="ops.md",
        )
        for index in range(10)
    ]
    chunks.append(
        Chunk(
            id="support-p1",
            document_id="support-doc",
            chunk_id="support-p1",
            domain="customer_support",
            text="P1 SLA escalation shared keyword for customer support",
            filename="support.md",
        )
    )
    store.replace_chunks(chunks)

    service = RAGService(store)
    debug = service.debug_query(
        "P1 SLA escalation shared keyword",
        top_k=1,
        domain="customer_support",
        context=RequestContext(tenant_id="default", roles=["reader"]),
    )

    assert debug["requested_top_k"] == 1
    assert debug["candidate_k"] == 50
    assert debug["before_filter_count"] == 11
    assert debug["after_filter_count"] == 1
    assert debug["results"][0]["chunk_id"] == "support-p1"
    shutil.rmtree(storage_dir, ignore_errors=True)
