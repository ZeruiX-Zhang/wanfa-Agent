from __future__ import annotations

import pytest

from app.core.config import AGENT_CORE_ROOT
from app.db.session import can_connect
from app.rag.models import Chunk, SearchFilters
from app.rag.vector_stores.pgvector_store import PgVectorStore


def test_pgvector_migration_contains_required_tables_and_filters() -> None:
    sql = (AGENT_CORE_ROOT / "app" / "db" / "migrations" / "001_init_pgvector.sql").read_text(encoding="utf-8")

    for table in ["documents", "chunks", "embeddings", "ingestion_jobs", "eval_runs", "agent_runs"]:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in sql
    for column in ["tenant_id", "domain", "access_roles", "doc_type", "contextual_text"]:
        assert column in sql


@pytest.mark.pgvector
def test_pgvector_store_roundtrip_when_database_is_available() -> None:
    connected, reason = can_connect()
    if not connected:
        pytest.skip(reason)

    store = PgVectorStore()
    store.apply_migrations()
    store.reindex_document(
        "test-doc",
        [
            Chunk(
                id="test-doc:chunk",
                document_id="test-doc",
                chunk_id="test-doc:chunk",
                domain="customer_support",
                tenant_id="tenant-a",
                access_roles=["support"],
                doc_type="kb",
                text="P1 SLA support response",
            )
        ],
    )

    results, _ = store.search(
        "P1 SLA",
        top_k=1,
        filters=SearchFilters(tenant_id="tenant-a", domain="customer_support", access_roles=["support"]),
    )

    assert results[0].chunk.chunk_id == "test-doc:chunk"
    store.delete_document("test-doc")

