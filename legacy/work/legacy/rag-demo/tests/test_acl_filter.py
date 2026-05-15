from __future__ import annotations

import shutil
import uuid

from app.core.config import AGENT_CORE_ROOT
from app.rag.models import Chunk
from app.rag.service import RAGService, RequestContext
from app.rag.vector_stores.faiss_store import FaissVectorStore


def test_tenant_filter_blocks_cross_tenant_retrieval() -> None:
    storage_dir = AGENT_CORE_ROOT / ".pytest_tmp" / f"rag-acl-tenant-{uuid.uuid4().hex}"
    storage_dir.mkdir(parents=True, exist_ok=True)
    store = FaissVectorStore(storage_dir)
    try:
        store.replace_chunks(
            [
                Chunk(
                    id="tenant-b-secret",
                    document_id="doc",
                    chunk_id="tenant-b-secret",
                    domain="customer_support",
                    tenant_id="tenant-b",
                    text="P1 SLA private tenant data",
                )
            ]
        )
        debug = RAGService(store).debug_query(
            "P1 SLA private tenant data",
            top_k=3,
            domain="customer_support",
            context=RequestContext(tenant_id="tenant-a", roles=["reader"]),
        )

        assert debug["results"] == []
    finally:
        shutil.rmtree(storage_dir, ignore_errors=True)


def test_access_roles_filter_blocks_role_mismatch() -> None:
    storage_dir = AGENT_CORE_ROOT / ".pytest_tmp" / f"rag-acl-role-{uuid.uuid4().hex}"
    storage_dir.mkdir(parents=True, exist_ok=True)
    store = FaissVectorStore(storage_dir)
    try:
        store.replace_chunks(
            [
                Chunk(
                    id="admin-only",
                    document_id="doc",
                    chunk_id="admin-only",
                    domain="ops_runbook",
                    tenant_id="default",
                    access_roles=["admin"],
                    text="ERROR E503 admin-only runbook",
                )
            ]
        )
        debug = RAGService(store).debug_query(
            "ERROR E503 admin-only runbook",
            top_k=3,
            domain="ops_runbook",
            context=RequestContext(tenant_id="default", roles=["reader"]),
        )

        assert debug["results"] == []
        assert debug["dense_results"] == []
        assert debug["bm25_results"] == []
    finally:
        shutil.rmtree(storage_dir, ignore_errors=True)

