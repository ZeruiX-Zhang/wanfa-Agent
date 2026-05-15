from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import asc, desc
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models import Event, EventEvidence, Job, ProductReview, Report, Source, Watchlist
from app.models.all_models import (
    ComplianceDecision,
    CrossLanguageCandidate,
    EventCluster,
    EvidenceLedgerEntry,
    IntelligenceObject,
    SourcePolicy,
)
from app.schemas.common import Page
from app.schemas.compliance import ComplianceDecisionRead, ComplianceEvaluateRequest, SourcePolicyRead, SourcePolicyUpdate
from app.schemas.dashboard import DashboardOverview
from app.schemas.event import EventDetail, EventEvidenceRead, EventRead
from app.schemas.intelligence import (
    CrossLanguageCandidateRead,
    EventClusterRead,
    EvidenceLedgerEntryRead,
    IntelligenceObjectCreate,
    IntelligenceObjectDetail,
    IntelligenceObjectRead,
)
from app.schemas.job import JobCreateRequest, JobDetail, JobRead
from app.schemas.product_review import ProductReviewDetail, ProductReviewRead, ProductReviewRequest
from app.schemas.report import ReportDetail, ReportExport, ReportGenerateRequest, ReportRead
from app.schemas.setting import SettingsRead, SettingsUpdate
from app.schemas.source import SourceCreate, SourceRead, SourceUpdate
from app.schemas.watchlist import WatchlistCreate, WatchlistRead, WatchlistUpdate
from app.services.compliance import ensure_source_policy, evaluate_source_compliance
from app.services.dashboard import dashboard_overview
from app.services.intelligence import create_intelligence_object, sync_objects_from_events
from app.services.job_runner import run_daily_job, run_job_by_type
from app.services.product_reviews import build_product_review
from app.services.report_generator import generate_report
from app.services.settings import read_settings, update_settings

router = APIRouter(prefix="/api")


def paginate(query, limit: int, offset: int):
    total = query.order_by(None).count()
    return query.limit(limit).offset(offset).all(), total


def apply_sort(query, model, sort: str | None, allowed: set[str], default: str):
    field = sort or default
    direction = desc
    if field.startswith("-"):
        field = field[1:]
        direction = desc
    else:
        direction = asc
    if field not in allowed:
        raise HTTPException(status_code=400, detail=f"Invalid sort field: {field}")
    return query.order_by(direction(getattr(model, field)))


@router.get("/dashboard", response_model=DashboardOverview)
def get_dashboard(db: Session = Depends(get_db)):
    return dashboard_overview(db)


@router.get("/sources", response_model=Page[SourceRead])
def list_sources(
    type: str | None = None,
    category: str | None = None,
    enabled: bool | None = None,
    sort: str | None = "-created_at",
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(Source)
    if type:
        query = query.filter(Source.type == type)
    if category:
        query = query.filter(Source.category == category)
    if enabled is not None:
        query = query.filter(Source.enabled == enabled)
    query = apply_sort(query, Source, sort, {"created_at", "updated_at", "name", "trust_score", "last_fetched_at"}, "-created_at")
    items, total = paginate(query, limit, offset)
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.post("/sources", response_model=SourceRead, status_code=201)
def create_source(payload: SourceCreate, db: Session = Depends(get_db)):
    source = Source(**payload.model_dump(exclude={"metadata"}), metadata_=payload.metadata)
    db.add(source)
    db.commit()
    db.refresh(source)
    ensure_source_policy(db, source)
    return source


@router.patch("/sources/{source_id}", response_model=SourceRead)
def update_source(source_id: str, payload: SourceUpdate, db: Session = Depends(get_db)):
    source = db.get(Source, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    data = payload.model_dump(exclude_unset=True)
    metadata = data.pop("metadata", None)
    for key, value in data.items():
        setattr(source, key, value)
    if metadata is not None:
        source.metadata_ = metadata
    db.commit()
    db.refresh(source)
    return source


@router.delete("/sources/{source_id}", status_code=204)
def delete_source(source_id: str, db: Session = Depends(get_db)):
    source = db.get(Source, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    db.delete(source)
    db.commit()
    return None


@router.get("/source-policies", response_model=Page[SourcePolicyRead])
def list_source_policies(
    compliance_status: str | None = None,
    sort: str | None = "-created_at",
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(SourcePolicy)
    if compliance_status:
        query = query.filter(SourcePolicy.compliance_status == compliance_status)
    query = apply_sort(query, SourcePolicy, sort, {"created_at", "updated_at", "compliance_status", "access_type"}, "-created_at")
    items, total = paginate(query, limit, offset)
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.get("/sources/{source_id}/policy", response_model=SourcePolicyRead)
def get_source_policy(source_id: str, db: Session = Depends(get_db)):
    source = db.get(Source, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return ensure_source_policy(db, source)


@router.patch("/sources/{source_id}/policy", response_model=SourcePolicyRead)
def patch_source_policy(source_id: str, payload: SourcePolicyUpdate, db: Session = Depends(get_db)):
    source = db.get(Source, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    policy = ensure_source_policy(db, source)
    data = payload.model_dump(exclude_unset=True)
    metadata = data.pop("metadata", None)
    for key, value in data.items():
        setattr(policy, key, value)
    if metadata is not None:
        policy.metadata_ = metadata
    source.robots_policy = policy.robots_txt_status
    source.license_name = policy.license_name
    source.terms_url = policy.terms_url
    source.attribution_required = policy.requires_attribution
    source.compliance_status = policy.compliance_status
    db.commit()
    db.refresh(policy)
    return policy


@router.post("/sources/{source_id}/compliance/evaluate", response_model=ComplianceDecisionRead)
def evaluate_source_policy(source_id: str, payload: ComplianceEvaluateRequest, db: Session = Depends(get_db)):
    source = db.get(Source, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return evaluate_source_compliance(db, source, mode=payload.mode, decided_by=payload.decided_by)


@router.get("/compliance-decisions", response_model=Page[ComplianceDecisionRead])
def list_compliance_decisions(
    source_id: str | None = None,
    decision: str | None = None,
    mode: str | None = None,
    sort: str | None = "-created_at",
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(ComplianceDecision)
    if source_id:
        query = query.filter(ComplianceDecision.source_id == source_id)
    if decision:
        query = query.filter(ComplianceDecision.decision == decision)
    if mode:
        query = query.filter(ComplianceDecision.mode == mode)
    query = apply_sort(query, ComplianceDecision, sort, {"created_at", "decision", "mode"}, "-created_at")
    items, total = paginate(query, limit, offset)
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.get("/events", response_model=Page[EventRead])
def list_events(
    category: str | None = None,
    verification_status: str | None = None,
    min_confidence: float | None = Query(default=None, ge=0.0, le=1.0),
    sort: str | None = "-importance_score",
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(Event)
    if category:
        query = query.filter(Event.category == category)
    if verification_status:
        query = query.filter(Event.verification_status == verification_status)
    if min_confidence is not None:
        query = query.filter(Event.confidence >= min_confidence)
    query = apply_sort(
        query,
        Event,
        sort,
        {"created_at", "event_time", "importance_score", "confidence", "index_credibility", "index_impact", "index_urgency"},
        "-importance_score",
    )
    items, total = paginate(query, limit, offset)
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.get("/events/{event_id}", response_model=EventDetail)
def get_event(event_id: str, db: Session = Depends(get_db)):
    event = (
        db.query(Event)
        .options(selectinload(Event.claims), selectinload(Event.evidence))
        .filter(Event.id == event_id)
        .first()
    )
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.get("/events/{event_id}/evidence", response_model=list[EventEvidenceRead])
def get_event_evidence(event_id: str, db: Session = Depends(get_db)):
    if not db.get(Event, event_id):
        raise HTTPException(status_code=404, detail="Event not found")
    return db.query(EventEvidence).filter(EventEvidence.event_id == event_id).all()


@router.post("/intelligence-objects/sync", response_model=list[IntelligenceObjectRead])
def sync_intelligence_objects(
    mode: str = Query("speed", pattern="^(speed|verified)$"),
    limit: int = Query(500, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    return sync_objects_from_events(db, limit=limit, mode=mode)


@router.get("/intelligence-objects", response_model=Page[IntelligenceObjectRead])
def list_intelligence_objects(
    domain: str | None = None,
    mode: str | None = Query(default=None, pattern="^(speed|verified)$"),
    verification_status: str | None = None,
    compliance_status: str | None = None,
    language: str | None = None,
    sort: str | None = "-aggregate_score",
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(IntelligenceObject)
    if domain:
        query = query.filter(IntelligenceObject.domain == domain)
    if mode:
        query = query.filter(IntelligenceObject.mode == mode)
    if verification_status:
        query = query.filter(IntelligenceObject.verification_status == verification_status)
    if compliance_status:
        query = query.filter(IntelligenceObject.compliance_status == compliance_status)
    if language:
        query = query.filter(IntelligenceObject.language == language)
    query = apply_sort(
        query,
        IntelligenceObject,
        sort,
        {"created_at", "updated_at", "aggregate_score", "index_credibility", "index_impact", "index_urgency"},
        "-aggregate_score",
    )
    items, total = paginate(query, limit, offset)
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.post("/intelligence-objects", response_model=IntelligenceObjectRead, status_code=201)
def create_intelligence_object_endpoint(payload: IntelligenceObjectCreate, db: Session = Depends(get_db)):
    return create_intelligence_object(db, payload)


@router.get("/intelligence-objects/{object_id}", response_model=IntelligenceObjectDetail)
def get_intelligence_object(object_id: str, db: Session = Depends(get_db)):
    obj = (
        db.query(IntelligenceObject)
        .options(selectinload(IntelligenceObject.ledger_entries))
        .filter(IntelligenceObject.id == object_id)
        .first()
    )
    if not obj:
        raise HTTPException(status_code=404, detail="Intelligence object not found")
    return obj


@router.get("/intelligence-objects/{object_id}/evidence-ledger", response_model=list[EvidenceLedgerEntryRead])
def get_intelligence_object_ledger(object_id: str, db: Session = Depends(get_db)):
    if not db.get(IntelligenceObject, object_id):
        raise HTTPException(status_code=404, detail="Intelligence object not found")
    return (
        db.query(EvidenceLedgerEntry)
        .filter(EvidenceLedgerEntry.intelligence_object_id == object_id)
        .order_by(EvidenceLedgerEntry.created_at.asc())
        .all()
    )


@router.get("/evidence-ledger", response_model=Page[EvidenceLedgerEntryRead])
def list_evidence_ledger(
    source_id: str | None = None,
    event_id: str | None = None,
    compliance_status: str | None = None,
    sort: str | None = "-captured_at",
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(EvidenceLedgerEntry)
    if source_id:
        query = query.filter(EvidenceLedgerEntry.source_id == source_id)
    if event_id:
        query = query.filter(EvidenceLedgerEntry.event_id == event_id)
    if compliance_status:
        query = query.filter(EvidenceLedgerEntry.compliance_status == compliance_status)
    query = apply_sort(query, EvidenceLedgerEntry, sort, {"created_at", "captured_at", "trust_score", "relevance_score"}, "-captured_at")
    items, total = paginate(query, limit, offset)
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.get("/clusters", response_model=Page[EventClusterRead])
def list_clusters(
    category: str | None = None,
    language: str | None = None,
    verification_status: str | None = None,
    sort: str | None = "-importance_score",
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(EventCluster)
    if category:
        query = query.filter(EventCluster.category == category)
    if language:
        query = query.filter(EventCluster.language == language)
    if verification_status:
        query = query.filter(EventCluster.verification_status == verification_status)
    query = apply_sort(query, EventCluster, sort, {"created_at", "importance_score", "confidence_score"}, "-importance_score")
    items, total = paginate(query, limit, offset)
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.get("/cross-language-candidates", response_model=Page[CrossLanguageCandidateRead])
def list_cross_language_candidates(
    source_language: str | None = None,
    target_language: str | None = None,
    status: str | None = None,
    sort: str | None = "-similarity_score",
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(CrossLanguageCandidate)
    if source_language:
        query = query.filter(CrossLanguageCandidate.source_language == source_language)
    if target_language:
        query = query.filter(CrossLanguageCandidate.target_language == target_language)
    if status:
        query = query.filter(CrossLanguageCandidate.status == status)
    query = apply_sort(query, CrossLanguageCandidate, sort, {"created_at", "similarity_score"}, "-similarity_score")
    items, total = paginate(query, limit, offset)
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.get("/reports", response_model=Page[ReportRead])
def list_reports(
    report_type: str | None = None,
    mode: str | None = Query(default=None, pattern="^(speed|verified)$"),
    sort: str | None = "-created_at",
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(Report)
    if report_type:
        query = query.filter(Report.report_type == report_type)
    if mode:
        query = query.filter(Report.mode == mode)
    query = apply_sort(query, Report, sort, {"created_at", "generation_seconds", "title", "mode"}, "-created_at")
    items, total = paginate(query, limit, offset)
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.post("/reports/generate", response_model=ReportDetail)
def generate_report_endpoint(payload: ReportGenerateRequest, db: Session = Depends(get_db)):
    report = generate_report(db, payload.report_type, payload.category, payload.limit, payload.mode)
    return (
        db.query(Report)
        .options(selectinload(Report.items))
        .filter(Report.id == report.id)
        .first()
    )


@router.get("/reports/{report_id}", response_model=ReportDetail)
def get_report(report_id: str, db: Session = Depends(get_db)):
    report = (
        db.query(Report)
        .options(selectinload(Report.items))
        .filter(Report.id == report_id)
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@router.get("/reports/{report_id}/export", response_model=ReportExport)
def export_report(report_id: str, format: str = Query("markdown", pattern="^(markdown|json)$"), db: Session = Depends(get_db)):
    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return ReportExport(format=format, content=report.markdown if format == "markdown" else report.json_content)


@router.get("/watchlists", response_model=Page[WatchlistRead])
def list_watchlists(
    type: str | None = None,
    enabled: bool | None = None,
    sort: str | None = "type",
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(Watchlist)
    if type:
        query = query.filter(Watchlist.type == type)
    if enabled is not None:
        query = query.filter(Watchlist.enabled == enabled)
    query = apply_sort(query, Watchlist, sort, {"created_at", "type", "name"}, "type")
    items, total = paginate(query, limit, offset)
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.post("/watchlists", response_model=WatchlistRead, status_code=201)
def create_watchlist(payload: WatchlistCreate, db: Session = Depends(get_db)):
    item = Watchlist(**payload.model_dump(exclude={"metadata"}), metadata_=payload.metadata)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/watchlists/{watchlist_id}", response_model=WatchlistRead)
def update_watchlist(watchlist_id: str, payload: WatchlistUpdate, db: Session = Depends(get_db)):
    item = db.get(Watchlist, watchlist_id)
    if not item:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    data = payload.model_dump(exclude_unset=True)
    metadata = data.pop("metadata", None)
    for key, value in data.items():
        setattr(item, key, value)
    if metadata is not None:
        item.metadata_ = metadata
    db.commit()
    db.refresh(item)
    return item


@router.delete("/watchlists/{watchlist_id}", status_code=204)
def delete_watchlist(watchlist_id: str, db: Session = Depends(get_db)):
    item = db.get(Watchlist, watchlist_id)
    if not item:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    db.delete(item)
    db.commit()
    return None


@router.post("/jobs/run-daily", response_model=JobDetail)
async def run_daily(mode: str = Query("verified", pattern="^(speed|verified)$"), db: Session = Depends(get_db)):
    job = Job(name="Daily intelligence run", type="daily", mode=mode, status="queued", parameters={}, metadata_={})
    db.add(job)
    db.commit()
    db.refresh(job)
    await run_daily_job(db, job, mode=mode)
    return db.query(Job).options(selectinload(Job.logs)).filter(Job.id == job.id).first()


@router.post("/jobs", response_model=JobDetail, status_code=201)
async def create_job(payload: JobCreateRequest, db: Session = Depends(get_db)):
    job = Job(
        name=payload.name,
        type=payload.type,
        mode=payload.mode,
        status="queued",
        parameters=payload.parameters,
        metadata_={"created_via": "api"},
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    if payload.run_now:
        await run_job_by_type(db, job)
    return db.query(Job).options(selectinload(Job.logs)).filter(Job.id == job.id).first()


@router.get("/jobs", response_model=Page[JobRead])
def list_jobs(
    status: str | None = None,
    mode: str | None = Query(default=None, pattern="^(speed|verified)$"),
    sort: str | None = "-created_at",
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(Job)
    if status:
        query = query.filter(Job.status == status)
    if mode:
        query = query.filter(Job.mode == mode)
    query = apply_sort(query, Job, sort, {"created_at", "started_at", "finished_at", "status", "mode"}, "-created_at")
    items, total = paginate(query, limit, offset)
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.post("/jobs/{job_id}/run", response_model=JobDetail)
async def run_existing_job(job_id: str, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status == "running":
        raise HTTPException(status_code=409, detail="Job is already running")
    await run_job_by_type(db, job)
    return db.query(Job).options(selectinload(Job.logs)).filter(Job.id == job.id).first()


@router.get("/jobs/{job_id}", response_model=JobDetail)
def get_job(job_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).options(selectinload(Job.logs)).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/product-reviews", response_model=ProductReviewDetail, status_code=201)
def create_product_review(payload: ProductReviewRequest, db: Session = Depends(get_db)):
    review = build_product_review(db, payload)
    return (
        db.query(ProductReview)
        .options(selectinload(ProductReview.evidence))
        .filter(ProductReview.id == review.id)
        .first()
    )


@router.get("/product-reviews", response_model=Page[ProductReviewRead])
def list_product_reviews(
    sort: str | None = "-created_at",
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = apply_sort(db.query(ProductReview), ProductReview, sort, {"created_at", "product_name", "confidence"}, "-created_at")
    items, total = paginate(query, limit, offset)
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.get("/product-reviews/{review_id}", response_model=ProductReviewDetail)
def get_product_review(review_id: str, db: Session = Depends(get_db)):
    review = (
        db.query(ProductReview)
        .options(selectinload(ProductReview.evidence))
        .filter(ProductReview.id == review_id)
        .first()
    )
    if not review:
        raise HTTPException(status_code=404, detail="Product review not found")
    return review


@router.get("/settings", response_model=SettingsRead)
def get_settings_endpoint(db: Session = Depends(get_db)):
    return read_settings(db)


@router.patch("/settings", response_model=SettingsRead)
def patch_settings(payload: SettingsUpdate, db: Session = Depends(get_db)):
    return update_settings(db, payload)
