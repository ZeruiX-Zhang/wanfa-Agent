from __future__ import annotations

import hashlib
import json

from sqlalchemy.orm import Session

from app.models.all_models import (
    Event,
    EventEvidence,
    EvidenceLedgerEntry,
    IntelligenceObject,
    NormalizedDocument,
    Source,
)
from app.schemas.intelligence import IntelligenceObjectCreate
from app.services.scoring import aggregate_index_score, apply_event_indices

DOMAIN_MAP = {
    "ai_model": "ai",
    "ai_product": "ai",
    "ai_company": "ai",
    "open_source": "developer_ecosystem",
    "paper_research": "research",
    "crypto_market": "crypto",
    "crypto_security": "crypto",
    "defi": "crypto",
    "ecommerce_market": "commerce",
    "regulation": "policy",
}


def domain_from_category(category: str) -> str:
    return DOMAIN_MAP.get(category, category or "other")


def _hash_payload(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _language_for_event(evidences: list[tuple[EventEvidence, NormalizedDocument, Source]]) -> str:
    languages = [doc.language for _, doc, _ in evidences if doc.language]
    if languages:
        return max(set(languages), key=languages.count)
    return "und"


def _compliance_for_sources(sources: list[Source]) -> str:
    statuses = {source.compliance_status for source in sources}
    if not statuses:
        return "unreviewed"
    if statuses & {"blocked", "disallowed", "takedown_required"}:
        return "blocked"
    if statuses <= {"approved"}:
        return "approved"
    if statuses <= {"approved", "approved_limited"}:
        return "approved_limited"
    return "needs_review"


def _event_evidence_rows(db: Session, event_id: str) -> list[tuple[EventEvidence, NormalizedDocument, Source]]:
    return (
        db.query(EventEvidence, NormalizedDocument, Source)
        .join(NormalizedDocument, EventEvidence.normalized_document_id == NormalizedDocument.id)
        .join(Source, NormalizedDocument.source_id == Source.id)
        .filter(EventEvidence.event_id == event_id)
        .all()
    )


def append_ledger_for_event(
    db: Session,
    intelligence_object: IntelligenceObject,
    event: Event,
    evidences: list[tuple[EventEvidence, NormalizedDocument, Source]] | None = None,
) -> list[EvidenceLedgerEntry]:
    rows = evidences if evidences is not None else _event_evidence_rows(db, event.id)
    entries: list[EvidenceLedgerEntry] = []
    claim_texts = [claim.text for claim in event.claims] if event.claims else []
    for evidence, document, source in rows:
        ledger_hash = _hash_payload(
            {
                "object_id": intelligence_object.id,
                "event_id": event.id,
                "document_id": document.id,
                "source_id": source.id,
                "url": evidence.evidence_url,
                "content_hash": document.content_hash,
            }
        )
        existing = db.query(EvidenceLedgerEntry).filter(EvidenceLedgerEntry.ledger_hash == ledger_hash).first()
        if existing:
            entries.append(existing)
            evidence.ledger_hash = ledger_hash
            continue
        entry = EvidenceLedgerEntry(
            intelligence_object_id=intelligence_object.id,
            event_id=event.id,
            normalized_document_id=document.id,
            source_id=source.id,
            evidence_url=evidence.evidence_url,
            title=evidence.title or document.title,
            source_name=evidence.source_name or source.name,
            source_type=source.type,
            quote=evidence.quote,
            content_hash=document.content_hash,
            ledger_hash=ledger_hash,
            citation_status="captured",
            legal_use_policy=source.legal_use_policy,
            compliance_status=source.compliance_status,
            trust_score=source.trust_score,
            relevance_score=max(event.confidence, 0.1),
            supports_claims=claim_texts[:10],
            metadata_={
                "document_language": document.language,
                "source_policy": source.legal_use_policy,
                "attribution_required": source.attribution_required,
            },
        )
        db.add(entry)
        evidence.ledger_hash = ledger_hash
        entries.append(entry)
        db.flush()
    return entries


def upsert_object_from_event(db: Session, event: Event, mode: str = "speed") -> IntelligenceObject:
    evidences = _event_evidence_rows(db, event.id)
    sources = [source for _, _, source in evidences]
    documents = [document for _, document, _ in evidences]
    source_ids = {source.id for source in sources}
    source_document_ids = [document.id for document in documents] or (event.metadata_ or {}).get("source_document_ids", [])
    indices = apply_event_indices(event, source_count=len(source_ids), evidence_count=len(evidences))
    aggregate = aggregate_index_score(indices)
    obj = db.query(IntelligenceObject).filter(IntelligenceObject.event_id == event.id).first()
    if obj is None:
        obj = IntelligenceObject(event_id=event.id)
        db.add(obj)
    obj.object_type = "event"
    obj.title = event.title
    obj.summary = event.summary
    obj.domain = domain_from_category(event.category)
    obj.language = _language_for_event(evidences)
    obj.region = (event.metadata_ or {}).get("region")
    obj.canonical_url = evidences[0][0].evidence_url if evidences else None
    obj.cluster_id = event.cluster_id
    obj.entities = event.entities or []
    obj.source_document_ids = source_document_ids
    obj.source_count = len(source_ids)
    obj.evidence_count = len(evidences)
    obj.mode = mode
    obj.status = "active"
    obj.verification_status = event.verification_status
    obj.index_credibility = indices["credibility"]
    obj.index_novelty = indices["novelty"]
    obj.index_impact = indices["impact"]
    obj.index_actionability = indices["actionability"]
    obj.index_urgency = indices["urgency"]
    obj.aggregate_score = aggregate
    obj.compliance_status = _compliance_for_sources(sources)
    obj.metadata_ = {
        **(obj.metadata_ or {}),
        "event_category": event.category,
        "five_indices": indices,
        "source_ids": sorted(source_ids),
    }
    db.flush()
    append_ledger_for_event(db, obj, event, evidences)
    db.commit()
    db.refresh(obj)
    return obj


def sync_objects_from_events(db: Session, limit: int = 500, mode: str = "speed") -> list[IntelligenceObject]:
    events = db.query(Event).order_by(Event.importance_score.desc(), Event.created_at.desc()).limit(limit).all()
    return [upsert_object_from_event(db, event, mode=mode) for event in events]


def create_intelligence_object(db: Session, payload: IntelligenceObjectCreate) -> IntelligenceObject:
    scores = payload.scores
    if scores:
        indices = scores.model_dump()
    else:
        indices = {
            "credibility": 0.4,
            "novelty": 0.4,
            "impact": 0.4,
            "actionability": 0.4,
            "urgency": 0.4,
        }
    obj = IntelligenceObject(
        object_type=payload.object_type,
        title=payload.title,
        summary=payload.summary,
        domain=payload.domain,
        language=payload.language,
        region=payload.region,
        canonical_url=payload.canonical_url,
        entities=payload.entities,
        source_document_ids=payload.source_document_ids,
        source_count=0,
        evidence_count=0,
        mode=payload.mode,
        verification_status=payload.verification_status,
        index_credibility=indices["credibility"],
        index_novelty=indices["novelty"],
        index_impact=indices["impact"],
        index_actionability=indices["actionability"],
        index_urgency=indices["urgency"],
        aggregate_score=aggregate_index_score(indices),
        compliance_status=payload.compliance_status,
        metadata_=payload.metadata,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj
