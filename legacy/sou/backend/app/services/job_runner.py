from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import Job, Source
from app.services.clustering import cluster_unclustered
from app.services.collector_runner import fetch_source, log_job
from app.services.compliance import evaluate_source_compliance
from app.services.extraction import extract_pending
from app.services.intelligence import sync_objects_from_events
from app.services.normalization import normalize_pending
from app.services.query_planner import QueryPlanner
from app.services.report_generator import generate_report
from app.services.verification import verify_events


async def run_daily_job(db: Session, job: Job | None = None, mode: str = "verified") -> Job:
    if job is None:
        job = Job(name="Daily intelligence run", type="daily", mode=mode, status="queued", parameters={}, metadata_={})
        db.add(job)
        db.commit()
        db.refresh(job)
    job.mode = mode
    job.status = "running"
    job.started_at = datetime.now(UTC)
    db.commit()
    success = 0
    failure = 0
    try:
        planner = QueryPlanner(db)
        batch = planner.generate_daily_batch()
        job.metadata_ = {**(job.metadata_ or {}), "run_id": batch.run_id, "query_count": len(batch.queries), "mode": mode}
        db.commit()
        log_job(db, job.id, "query_plan", "Generated daily query batch", run_id=batch.run_id, query_count=len(batch.queries))

        sources = db.query(Source).filter(Source.enabled.is_(True)).all()
        if mode == "verified":
            for source in sources:
                decision = evaluate_source_compliance(db, source, mode=mode)
                log_job(db, job.id, "compliance", f"Compliance decision for {source.name}: {decision.decision}", source_id=source.id)
        for source in sources:
            saved, failed = await fetch_source(db, source, job.id, mode=mode)
            success += saved
            failure += failed

        docs = normalize_pending(db)
        log_job(db, job.id, "normalize", f"Normalized {len(docs)} documents")
        events = extract_pending(db, job.id, mode=mode)
        log_job(db, job.id, "extract", f"Extracted {len(events)} events")
        clusters = cluster_unclustered(db)
        log_job(db, job.id, "cluster", f"Updated {len(clusters)} clusters")
        if mode == "verified":
            verified = verify_events(db)
            log_job(db, job.id, "verify", f"Updated verification status for {verified} events")
        objects = sync_objects_from_events(db, mode=mode)
        log_job(db, job.id, "intelligence_objects", f"Synced {len(objects)} universal intelligence objects")
        report = generate_report(db, "daily", limit=10, mode=mode)
        log_job(db, job.id, "report", "Generated daily report", report_id=report.id, seconds=report.generation_seconds)
        job.status = "completed"
    except Exception as exc:
        failure += 1
        job.status = "failed"
        log_job(db, job.id, "job", "Daily job failed", "error", error=str(exc)[:1000])
    finally:
        job.finished_at = datetime.now(UTC)
        job.success_count = success
        job.failure_count = failure
        db.commit()
        db.refresh(job)
    return job


async def run_job_by_type(db: Session, job: Job) -> Job:
    if job.type in {"daily", "intelligence_run", "collect_analyze_report"}:
        return await run_daily_job(db, job, mode=job.mode)
    job.status = "failed"
    job.failure_count = 1
    job.finished_at = datetime.now(UTC)
    log_job(db, job.id, "job", f"Unsupported job type: {job.type}", "error")
    db.commit()
    db.refresh(job)
    return job
