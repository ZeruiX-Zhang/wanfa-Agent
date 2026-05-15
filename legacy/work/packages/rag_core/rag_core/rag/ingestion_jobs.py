from __future__ import annotations

import uuid
from datetime import datetime, timezone
from threading import Lock
from typing import Any

from pydantic import BaseModel, Field

from rag_core.rag.ingestion import load_local_documents
from rag_core.rag.service import RequestContext, rag_service


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class IngestionJob(BaseModel):
    id: str
    status: str = "pending"
    documents_loaded: int = 0
    chunks_created: int = 0
    embeddings_created: int = 0
    error_message: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    request: dict[str, Any] = Field(default_factory=dict)


class IngestionJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, IngestionJob] = {}
        self._lock = Lock()

    def create(self, request: dict[str, Any]) -> IngestionJob:
        job = IngestionJob(id=str(uuid.uuid4()), request=request)
        with self._lock:
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> IngestionJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def cancel(self, job_id: str) -> IngestionJob | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            if job.status in {"pending", "running"}:
                job.status = "cancelled"
                job.finished_at = utc_now()
            return job

    def run_local(self, job_id: str, context: RequestContext) -> IngestionJob:
        job = self.get(job_id)
        if job is None:
            raise KeyError(job_id)
        if job.status == "cancelled":
            return job
        self._update(job, status="running", started_at=utc_now())
        try:
            chunks = load_local_documents(
                raw_path=job.request.get("directory") or job.request.get("path"),
                tenant_id=context.tenant_id,
                access_roles=context.roles,
                domain=job.request.get("domain"),
                doc_type=job.request.get("doc_type", "kb"),
                glob_pattern=str(job.request.get("glob_pattern", "**/*") or "**/*"),
            )
            stats = rag_service.ingest_chunks(chunks, replace=bool(job.request.get("replace", False)))
            self._update(job, status="succeeded", finished_at=utc_now(), **stats)
        except Exception as exc:  # noqa: BLE001 - job captures error without crashing background worker.
            self._update(job, status="failed", finished_at=utc_now(), error_message=str(exc))
        return job

    def _update(self, job: IngestionJob, **values: Any) -> None:
        with self._lock:
            for key, value in values.items():
                setattr(job, key, value)
            self._jobs[job.id] = job


ingestion_jobs = IngestionJobStore()

