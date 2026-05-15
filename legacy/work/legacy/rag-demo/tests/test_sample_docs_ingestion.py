from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.core.auth import DEMO_ROLES
from app.core.config import AGENT_CORE_ROOT
from app.main import app
from app.rag.settings import rag_storage_dir
from app.rag.service import rag_service
from scripts.create_sample_docs import main as create_sample_docs


client = TestClient(app)
AUTH_HEADERS = {"X-API-Key": "change-me"}
MOJIBAKE_MARKERS = ["ä¼", "å®", "åˆ†", "浼佷笟"]
SLA_TEXT = "企业客户 P1 SLA 响应时间为 30 分钟"


def test_create_sample_docs_generates_customer_support_and_eval_files() -> None:
    create_sample_docs()

    support_doc = AGENT_CORE_ROOT / "data" / "raw" / "customer_support" / "enterprise_sla.txt"
    eval_file = AGENT_CORE_ROOT / "data" / "eval" / "customer_support_eval.jsonl"

    assert support_doc.exists()
    assert eval_file.exists()
    content = support_doc.read_text(encoding="utf-8")
    for expected in ["企业客户", "P1", "SLA", "30 分钟"]:
        assert expected in content


def test_ingest_customer_support_directory_creates_demo_acl_chunks() -> None:
    create_sample_docs()

    response = client.post(
        "/documents/ingest-local?sync=true",
        headers=AUTH_HEADERS,
        json={
            "domain": "customer_support",
            "directory": "data/raw/customer_support",
            "glob_pattern": "**/*",
            "build_index": True,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "succeeded"
    assert data["documents_loaded"] >= 1
    assert data["chunks_created"] >= 1

    support_chunks = [
        chunk for chunk in rag_service.vector_store.list_chunks() if chunk.filename == "enterprise_sla.txt"
    ]
    assert support_chunks
    assert any("企业客户" in chunk.text and "P1" in chunk.text and "30 分钟" in chunk.text for chunk in support_chunks)
    for chunk in support_chunks:
        assert chunk.metadata["tenant_id"] == "demo"
        assert chunk.metadata["domain"] == "customer_support"
        assert set(chunk.metadata["access_roles"]) & set(DEMO_ROLES)

    chunks_jsonl = (rag_storage_dir() / "chunks.jsonl").read_text(encoding="utf-8")
    assert SLA_TEXT in chunks_jsonl
    assert not any(marker in chunks_jsonl for marker in MOJIBAKE_MARKERS)


def test_valid_api_key_query_p1_sla_returns_customer_support_source() -> None:
    create_sample_docs()
    client.post(
        "/documents/ingest-local?sync=true",
        headers=AUTH_HEADERS,
        json={
            "domain": "customer_support",
            "directory": "data/raw/customer_support",
            "glob_pattern": "**/*",
            "build_index": True,
        },
    )

    body = json.dumps(
        {"question": "企业客户 P1 响应时间是多少？", "domain": "auto", "top_k": 5},
        ensure_ascii=False,
    ).encode("utf-8")
    response = client.post(
        "/rag/query",
        content=body,
        headers={**AUTH_HEADERS, "content-type": "application/json; charset=utf-8"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["answer"]
    assert data["answer"] != "No authorized context was found for this query."
    assert data["sources"]
    assert data["sources"][0]["domain"] == "customer_support"
    assert data["sources"][0]["filename"] == "enterprise_sla.txt"
    source_text = " ".join(str(source.get("text", "")) for source in data["sources"])
    assert "企业客户" in source_text
    assert "30 分钟" in source_text
    assert not any(marker in source_text for marker in MOJIBAKE_MARKERS)
