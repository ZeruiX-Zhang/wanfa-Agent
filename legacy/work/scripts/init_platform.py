from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
import sitecustomize  # noqa: F401

from rag_core.rag.ingestion import load_local_documents
from rag_core.rag.service import rag_service
from platform_common.settings import ROOT_DIR as PLATFORM_ROOT, get_settings
from scripts.seed_demo_data import initialize_database


def initialize_platform(reset_traces: bool = True) -> dict[str, int]:
    settings = get_settings()
    settings.rag_storage_dir.mkdir(parents=True, exist_ok=True)
    settings.trace_storage_dir.mkdir(parents=True, exist_ok=True)
    settings.analyst_chart_dir.mkdir(parents=True, exist_ok=True)
    settings.ticket_store_path.parent.mkdir(parents=True, exist_ok=True)
    settings.unified_trace_path.parent.mkdir(parents=True, exist_ok=True)

    if reset_traces:
        for path in (
            settings.unified_trace_path,
            settings.workflow_internal_trace_path,
            settings.analyst_internal_trace_path,
            settings.ticket_store_path,
        ):
            if path.exists():
                path.unlink()

    raw_root = PLATFORM_ROOT / "data" / "raw"
    chunks = []
    for domain_dir in sorted(path for path in raw_root.iterdir() if path.is_dir()):
        chunks.extend(
            load_local_documents(
                raw_path=str(domain_dir),
                tenant_id=settings.default_tenant_id,
                access_roles=settings.default_roles,
                domain=domain_dir.name,
                glob_pattern="**/*",
            )
        )
    sample_docs = PLATFORM_ROOT / "data" / "sample_docs"
    if sample_docs.exists():
        chunks.extend(
            load_local_documents(
                raw_path=str(sample_docs),
                tenant_id=settings.default_tenant_id,
                access_roles=settings.default_roles,
                domain=None,
                glob_pattern="**/*",
            )
        )

    stats = rag_service.ingest_chunks(chunks, replace=True)
    analyst_db_path = Path(urlparse(settings.analyst_database_url).path.lstrip("/"))
    if not analyst_db_path.is_absolute():
        analyst_db_path = (PLATFORM_ROOT / analyst_db_path).resolve()
    db_counts = initialize_database(analyst_db_path)
    return {
        "documents_loaded": stats["documents_loaded"],
        "chunks_created": stats["chunks_created"],
        "analyst_db_exists": int(analyst_db_path.exists()),
        "analyst_rows": sum(db_counts.values()),
    }


if __name__ == "__main__":
    result = initialize_platform(reset_traces=True)
    print(result)
