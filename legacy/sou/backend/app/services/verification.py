from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Event, EventCluster, EventEvidence, NormalizedDocument, Source
from app.services.scoring import apply_event_indices


def verify_event(db: Session, event: Event) -> str:
    evidences = (
        db.query(EventEvidence, NormalizedDocument, Source)
        .join(NormalizedDocument, EventEvidence.normalized_document_id == NormalizedDocument.id)
        .join(Source, NormalizedDocument.source_id == Source.id)
        .filter(EventEvidence.event_id == event.id)
        .all()
    )
    if not evidences:
        return "unverified"
    if any("low_content_quality" in (doc.quality_flags or []) for _, doc, _ in evidences):
        return "low_quality"
    if any(source.compliance_status in {"blocked", "disallowed", "takedown_required"} for _, _, source in evidences):
        return "low_quality"
    source_types = {source.type for _, _, source in evidences}
    official = any(source.type in {"official_blog", "custom_url"} and source.trust_score >= 0.8 for _, _, source in evidences)
    structured = {"coingecko", "defillama", "github", "arxiv"} & source_types
    if event.category in {"crypto_market", "defi"} and structured:
        return "verified" if len(evidences) >= 1 else "partially_verified"
    if event.category == "open_source" and "github" in source_types:
        return "verified"
    if event.category == "paper_research" and "arxiv" in source_types:
        return "verified"
    if official and len(evidences) >= 2:
        return "verified"
    if official:
        return "partially_verified"
    if len({source.id for _, _, source in evidences}) >= 3:
        return "partially_verified"
    if event.confidence < 0.45:
        return "needs_human_review"
    return "unverified"


def verify_events(db: Session, limit: int = 300) -> int:
    events = db.query(Event).order_by(Event.importance_score.desc()).limit(limit).all()
    count = 0
    for event in events:
        status = verify_event(db, event)
        if event.verification_status != status:
            event.verification_status = status
            count += 1
        evidences = (
            db.query(EventEvidence, NormalizedDocument, Source)
            .join(NormalizedDocument, EventEvidence.normalized_document_id == NormalizedDocument.id)
            .join(Source, NormalizedDocument.source_id == Source.id)
            .filter(EventEvidence.event_id == event.id)
            .all()
        )
        apply_event_indices(event, source_count=len({source.id for _, _, source in evidences}), evidence_count=len(evidences))
    db.commit()
    clusters = db.query(EventCluster).limit(limit).all()
    for cluster in clusters:
        statuses = {event.verification_status for event in db.query(Event).filter(Event.cluster_id == cluster.id).all()}
        if "conflicting" in statuses:
            cluster.verification_status = "conflicting"
        elif "verified" in statuses:
            cluster.verification_status = "verified"
        elif "partially_verified" in statuses:
            cluster.verification_status = "partially_verified"
        elif "low_quality" in statuses:
            cluster.verification_status = "low_quality"
        elif "needs_human_review" in statuses:
            cluster.verification_status = "needs_human_review"
        else:
            cluster.verification_status = "unverified"
    db.commit()
    return count
