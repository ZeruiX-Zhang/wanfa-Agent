from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Event, EventClaim, EventEvidence, JobLog, NormalizedDocument
from app.schemas.event import Claim, ExtractedEvent
from app.services.collectors.base import ConnectorUnconfigured
from app.services.llm_gateway import LLMGateway
from app.services.scoring import apply_event_indices


def category_from_source(document: NormalizedDocument) -> str:
    category = document.source.category if document.source else "other"
    mapping = {
        "ai_news": "ai_company",
        "crypto_news": "crypto_market",
        "tech_news": "tech_business",
        "ai_product_review": "ai_product",
        "ecommerce_market": "ecommerce_market",
        "github_trending": "open_source",
        "arxiv_research": "paper_research",
    }
    return mapping.get(category, category if category in mapping.values() else "other")


def local_event_from_document(document: NormalizedDocument) -> ExtractedEvent:
    claim = Claim(
        text=document.summary or document.title,
        evidence_quote=(document.clean_text[:240] if document.clean_text else None),
        evidence_url=document.canonical_url,
        confidence=0.45,
        needs_verification=True,
    )
    return ExtractedEvent(
        title=document.title,
        category=category_from_source(document),
        event_time=document.published_at,
        entities=document.entities or [],
        claims=[claim],
        summary=document.summary or document.title,
        why_it_matters="Potentially relevant signal from configured source; requires verification.",
        affected_parties=document.entities[:5] if document.entities else [],
        confidence=0.45,
        novelty_score=0.45,
        impact_score=0.45,
        actionability_score=0.35,
        source_document_ids=[document.id],
    )


def save_extracted_event(db: Session, payload: ExtractedEvent, status: str = "extracted") -> Event:
    documents = [doc for doc in (db.get(NormalizedDocument, doc_id) for doc_id in payload.source_document_ids) if doc]
    languages = [doc.language for doc in documents if doc.language]
    event = Event(
        title=payload.title,
        category=payload.category,
        event_time=payload.event_time,
        entities=payload.entities,
        summary=payload.summary,
        why_it_matters=payload.why_it_matters,
        affected_parties=payload.affected_parties,
        confidence=payload.confidence,
        novelty_score=payload.novelty_score,
        impact_score=payload.impact_score,
        actionability_score=payload.actionability_score,
        extraction_status=status,
        verification_status="unverified",
        metadata_={
            "source_document_ids": payload.source_document_ids,
            "source_languages": sorted(set(languages)),
            "primary_language": max(set(languages), key=languages.count) if languages else "und",
        },
    )
    apply_event_indices(event, source_count=len({doc.source_id for doc in documents}), evidence_count=len(documents))
    db.add(event)
    db.flush()
    for claim in payload.claims:
        db.add(
            EventClaim(
                event_id=event.id,
                text=claim.text,
                evidence_quote=claim.evidence_quote,
                evidence_url=claim.evidence_url,
                confidence=claim.confidence,
                needs_verification=claim.needs_verification,
            )
        )
    for doc in documents:
        db.add(
            EventEvidence(
                event_id=event.id,
                normalized_document_id=doc.id,
                evidence_url=doc.canonical_url,
                title=doc.title,
                source_name=doc.source.name if doc.source else None,
                quote=doc.clean_text[:500],
            )
        )
    db.commit()
    db.refresh(event)
    from app.services.intelligence import upsert_object_from_event

    upsert_object_from_event(db, event, mode="speed" if status == "speed_mode" else "verified")
    return event


def extract_pending(db: Session, job_id: str | None = None, limit: int = 100, mode: str = "verified") -> list[Event]:
    gateway = LLMGateway(db)
    docs = (
        db.query(NormalizedDocument)
        .filter(~NormalizedDocument.id.in_(select(EventEvidence.normalized_document_id)))
        .order_by(NormalizedDocument.fetched_at.desc())
        .limit(limit)
        .all()
    )
    events: list[Event] = []
    for doc in docs:
        try:
            if mode == "speed":
                extracted = local_event_from_document(doc)
                events.append(save_extracted_event(db, extracted, "speed_mode"))
                continue
            extracted = gateway.extract_event(doc)
            if doc.id not in extracted.source_document_ids:
                extracted.source_document_ids.append(doc.id)
            events.append(save_extracted_event(db, extracted, "extracted"))
        except ConnectorUnconfigured:
            extracted = local_event_from_document(doc)
            events.append(save_extracted_event(db, extracted, "local_fallback"))
        except Exception as exc:
            if job_id:
                db.add(
                    JobLog(
                        job_id=job_id,
                        level="error",
                        stage="extract",
                        message=f"Extraction failed for {doc.id}",
                        details={"error": str(exc)[:1000]},
                    )
                )
                db.commit()
            failed = local_event_from_document(doc)
            events.append(save_extracted_event(db, failed, "extraction_failed"))
    return events
