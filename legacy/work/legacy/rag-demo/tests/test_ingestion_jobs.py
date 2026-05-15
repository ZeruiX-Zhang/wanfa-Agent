from __future__ import annotations

import shutil
import uuid

from fastapi.testclient import TestClient

from app.core.config import AGENT_CORE_ROOT
from app.main import app
from app.rag.ingestion_jobs import ingestion_jobs


client = TestClient(app)
AUTH_HEADERS = {"X-API-Key": "change-me"}


def test_ingest_local_sync_creates_succeeded_job() -> None:
    docs_dir = AGENT_CORE_ROOT / ".pytest_tmp" / f"ingest-{uuid.uuid4().hex}"
    docs_dir.mkdir(parents=True, exist_ok=True)
    try:
        (docs_dir / "customer_support.md").write_text("P1 SLA response\n\nRefund ticket workflow", encoding="utf-8")

        response = client.post(
            "/documents/ingest-local?sync=true",
            headers=AUTH_HEADERS,
            json={"path": str(docs_dir), "replace": True, "domain": "customer_support"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "succeeded"
        assert data["documents_loaded"] == 1
        assert data["chunks_created"] == 2

        job_response = client.get(f"/documents/jobs/{data['id']}", headers=AUTH_HEADERS)
        assert job_response.status_code == 200
        assert job_response.json()["status"] == "succeeded"
    finally:
        shutil.rmtree(docs_dir, ignore_errors=True)


def test_cancel_pending_ingestion_job() -> None:
    job = ingestion_jobs.create({"path": str(AGENT_CORE_ROOT / "storage" / "sample_docs")})

    response = client.post(f"/documents/jobs/{job.id}/cancel", headers=AUTH_HEADERS)

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
