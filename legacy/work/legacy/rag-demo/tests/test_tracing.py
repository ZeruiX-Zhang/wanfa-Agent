from __future__ import annotations

import json
import shutil
import uuid

import pytest

from app.agent.trace import record_agent_run
from app.core.config import AGENT_CORE_ROOT
from app.rag.models import Chunk
from app.rag.service import RAGService, RequestContext
from app.rag.vector_stores.faiss_store import FaissVectorStore


def test_rag_query_writes_trace_file(monkeypatch: pytest.MonkeyPatch) -> None:
    trace_dir = AGENT_CORE_ROOT / ".pytest_tmp" / f"traces-{uuid.uuid4().hex}"
    storage_dir = AGENT_CORE_ROOT / ".pytest_tmp" / f"rag-trace-{uuid.uuid4().hex}"
    trace_dir.mkdir(parents=True, exist_ok=True)
    storage_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("TRACE_STORAGE_DIR", str(trace_dir))
    try:
        store = FaissVectorStore(storage_dir)
        store.replace_chunks(
            [
                Chunk(
                    id="support",
                    document_id="support",
                    chunk_id="support",
                    domain="customer_support",
                    text="P1 SLA response",
                )
            ]
        )

        result = RAGService(store).query(
            "P1 SLA response",
            top_k=1,
            domain="customer_support",
            context=RequestContext(tenant_id="default", roles=["reader"]),
        )

        trace_id = result["debug"]["trace_id"]
        trace_file = trace_dir / "rag" / f"{trace_id}.json"
        assert trace_file.exists()
        data = json.loads(trace_file.read_text(encoding="utf-8"))
        assert data["selected_domain"] == "customer_support"
        assert "dense_latency_ms" in data
        assert data["sources"]
    finally:
        shutil.rmtree(trace_dir, ignore_errors=True)
        shutil.rmtree(storage_dir, ignore_errors=True)


def test_agent_run_writes_trace_file(monkeypatch: pytest.MonkeyPatch) -> None:
    trace_dir = AGENT_CORE_ROOT / ".pytest_tmp" / f"agent-traces-{uuid.uuid4().hex}"
    trace_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("TRACE_STORAGE_DIR", str(trace_dir))
    try:
        trace_id = record_agent_run(
            selected_workflow="demo",
            selected_tools=["search_knowledge"],
            tool_args={"query": "P1"},
            tool_result_summary="one result",
            tool_latency_ms=1.2,
            final_answer="done",
        )
        trace_file = trace_dir / "agent" / f"{trace_id}.json"
        assert trace_file.exists()
        data = json.loads(trace_file.read_text(encoding="utf-8"))
        assert data["selected_workflow"] == "demo"
        assert data["selected_tools"] == ["search_knowledge"]
    finally:
        shutil.rmtree(trace_dir, ignore_errors=True)

