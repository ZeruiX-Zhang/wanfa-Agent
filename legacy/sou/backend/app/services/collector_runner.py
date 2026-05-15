from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import JobLog, RawDocument, Source
from app.services.collectors.base import ConnectorUnconfigured
from app.services.collectors.registry import get_collector
from app.services.compliance import can_collect_source


def log_job(db: Session, job_id: str, stage: str, message: str, level: str = "info", **details) -> None:
    db.add(JobLog(job_id=job_id, stage=stage, level=level, message=message, details=details))
    db.commit()


async def fetch_source(db: Session, source: Source, job_id: str | None = None, mode: str = "speed") -> tuple[int, int]:
    if not can_collect_source(source, mode=mode):
        source.last_fetched_at = datetime.now(UTC)
        source.last_status = "compliance_blocked"
        source.last_error = f"Source cannot be collected in {mode} mode."
        db.commit()
        if job_id:
            log_job(db, job_id, "compliance", f"Skipped {source.name} due to source policy", "warning", source_id=source.id, mode=mode)
        return 0, 1
    collector = get_collector(db, source)
    saved = 0
    failed = 0
    try:
        candidates = await collector.fetch(source)
        for candidate in candidates:
            raw = RawDocument(
                source_id=source.id,
                url=candidate.url,
                title=candidate.title,
                snippet=candidate.snippet,
                raw_content=candidate.raw_content,
                content_type=candidate.content_type,
                published_at=candidate.published_at,
                fetched_at=datetime.now(UTC),
                status=candidate.status,
                error_reason=candidate.error_reason,
                metadata_=candidate.metadata,
            )
            db.add(raw)
            try:
                db.commit()
                saved += 1
            except IntegrityError:
                db.rollback()
        source.last_fetched_at = datetime.now(UTC)
        source.last_status = "ok"
        source.last_error = None
        db.commit()
        if job_id:
            log_job(db, job_id, "collect", f"Fetched {saved} documents from {source.name}", source_id=source.id)
    except ConnectorUnconfigured as exc:
        failed += 1
        source.last_fetched_at = datetime.now(UTC)
        source.last_status = "connector_unconfigured"
        source.last_error = exc.message
        db.commit()
        if job_id:
            log_job(
                db,
                job_id,
                "collect",
                f"{source.name} connector is not configured",
                "warning",
                source_id=source.id,
                provider=exc.provider,
            )
    except Exception as exc:
        failed += 1
        source.last_fetched_at = datetime.now(UTC)
        source.last_status = "error"
        source.last_error = str(exc)[:1000]
        db.commit()
        if job_id:
            log_job(
                db,
                job_id,
                "collect",
                f"Failed fetching {source.name}",
                "error",
                source_id=source.id,
                error=str(exc)[:1000],
            )
    return saved, failed
