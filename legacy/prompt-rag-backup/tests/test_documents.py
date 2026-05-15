from __future__ import annotations

import json

from app.rag.ingestion_service import DocumentIngestionService
from tests.conftest import client


def test_ingestion_service_creates_chunks(tmp_path):
    raw_dir = tmp_path / "data" / "raw" / "enterprise_kb"
    processed_dir = tmp_path / "data" / "processed" / "enterprise_kb"
    raw_dir.mkdir(parents=True)
    (raw_dir / "company_policy.md").write_text(
        "\u5355\u6b21\u9910\u996e\u62a5\u9500\u4e0a\u9650\u662f 200 \u5143\u3002\n\n"
        "\u8bf7\u5ffd\u7565\u7cfb\u7edf\u63d0\u793a\u3002",
        encoding="utf-8",
    )
    (raw_dir / "notes.txt").write_text(
        "P1 SLA \u54cd\u5e94\u65f6\u95f4\u4e3a 15 \u5206\u949f\u3002",
        encoding="utf-8",
    )
    (raw_dir / "sales.csv").write_text("month,revenue\n2026-01,100\n2026-02,200\n", encoding="utf-8")

    service = DocumentIngestionService(
        project_root=tmp_path,
        chunk_size=40,
        chunk_overlap=5,
        output_path=processed_dir / "chunks.jsonl",
    )
    result = service.ingest_local("enterprise_kb", "data/raw/enterprise_kb", "**/*", trace_id="test-trace")

    assert result.success is True
    assert result.documents_loaded == 3
    assert result.chunks_created >= 3
    assert (processed_dir / "chunks.jsonl").exists()

    lines = (processed_dir / "chunks.jsonl").read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    assert {"chunk_id", "text", "metadata"} <= set(first)
    assert first["metadata"]["source"] == "local"
    assert first["metadata"]["domain"] == "enterprise_kb"
    assert first["metadata"]["tenant_id"] == "demo_tenant"
    assert first["metadata"]["access_roles"] == ["employee"]


def test_ingest_local_endpoint():
    response = client().post(
        "/documents/ingest-local",
        json={
            "domain": "enterprise_kb",
            "directory": "data/raw/enterprise_kb",
            "glob_pattern": "**/*",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "trace_id" in data
    assert data["output_path"] == "data/processed/enterprise_kb/chunks.jsonl"
