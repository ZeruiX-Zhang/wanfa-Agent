from __future__ import annotations

from datetime import UTC, datetime

from app.models import Event, EventEvidence, NormalizedDocument, RawDocument, Source
from app.models.all_models import EvidenceLedgerEntry, IntelligenceObject
from app.schemas.event import ExtractedEvent
from app.services.report_generator import generate_report
from app.services.scoring import importance_score


def test_event_extraction_schema_validation():
    payload = {
        "title": "Demo event",
        "category": "ai_model",
        "event_time": None,
        "entities": ["DemoCo"],
        "claims": [
            {
                "text": "Demo claim",
                "evidence_quote": "quote",
                "evidence_url": "https://example.com",
                "confidence": 0.8,
                "needs_verification": False,
            }
        ],
        "summary": "Summary",
        "why_it_matters": "Reason",
        "affected_parties": ["teams"],
        "confidence": 0.8,
        "novelty_score": 0.7,
        "impact_score": 0.6,
        "actionability_score": 0.5,
        "source_document_ids": ["doc-1"],
    }
    event = ExtractedEvent.model_validate(payload)
    assert event.category == "ai_model"


def test_event_scoring_formula():
    assert importance_score(1, 1, 1, 1, 1) == 1
    assert importance_score(0, 0, 0, 0, 0) == 0
    assert importance_score(0.6, 0.7, 0.5, 0.4, 0.3) == 0.54


def test_report_generation(db_session):
    source = Source(
        name="Official",
        type="official_blog",
        category="ai_news",
        url="https://example.com",
        trust_score=0.9,
        language="en",
        rate_limit_per_minute=10,
        fetch_interval_minutes=60,
        metadata_={},
    )
    db_session.add(source)
    db_session.commit()
    raw = RawDocument(
        source_id=source.id,
        url="https://example.com/evidence",
        title="Evidence",
        raw_content="Evidence text " * 30,
        fetched_at=datetime.now(UTC),
        status="fetched",
        metadata_={},
    )
    db_session.add(raw)
    db_session.commit()
    doc = NormalizedDocument(
        raw_document_id=raw.id,
        canonical_url=raw.url,
        title=raw.title,
        clean_text=raw.raw_content,
        summary="Evidence summary",
        language="en",
        published_at=datetime.now(UTC),
        fetched_at=datetime.now(UTC),
        source_id=source.id,
        entities=["DemoCo"],
        content_hash="hash",
        simhash="1",
        status="normalized",
        quality_flags=[],
        published_at_inferred=False,
        metadata_={},
    )
    db_session.add(doc)
    db_session.commit()
    event = Event(
        title="Important demo event",
        category="ai_model",
        event_time=datetime.now(UTC),
        entities=["DemoCo"],
        summary="Summary",
        why_it_matters="Because it changes a tracked capability.",
        affected_parties=["operators"],
        confidence=0.8,
        novelty_score=0.7,
        impact_score=0.8,
        actionability_score=0.6,
        importance_score=0.75,
        verification_status="verified",
        extraction_status="extracted",
        metadata_={},
    )
    db_session.add(event)
    db_session.flush()
    db_session.add(
        EventEvidence(
            event_id=event.id,
            normalized_document_id=doc.id,
            evidence_url=doc.canonical_url,
            title=doc.title,
            source_name=source.name,
            quote=doc.clean_text[:100],
        )
    )
    db_session.commit()
    report = generate_report(db_session)
    assert "Important demo event" in report.markdown
    assert "https://example.com/evidence" in report.markdown
    obj = db_session.query(IntelligenceObject).filter(IntelligenceObject.event_id == event.id).one()
    assert obj.evidence_count == 1
    assert obj.aggregate_score > 0
    ledger = db_session.query(EvidenceLedgerEntry).filter(EvidenceLedgerEntry.intelligence_object_id == obj.id).one()
    assert ledger.evidence_url == "https://example.com/evidence"
