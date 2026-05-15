from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models import Event, Report, ReportItem
from app.models.all_models import EvidenceLedgerEntry, IntelligenceObject
from app.services.intelligence import upsert_object_from_event

SECTION_MAP = {
    "ai_model": "AI Models and Infrastructure",
    "ai_company": "AI Models and Infrastructure",
    "ai_product": "AI Products and Applications",
    "open_source": "Open Source and Developer Ecosystem",
    "paper_research": "Research Papers",
    "crypto_market": "Crypto Markets",
    "crypto_security": "Crypto Markets",
    "defi": "Crypto Markets",
    "ecommerce_market": "Commerce and Marketplaces",
    "regulation": "Policy and Compliance",
}


def recommended_action(event: Event) -> str:
    if event.verification_status in {"unverified", "needs_human_review", "low_quality"}:
        return "Track in speed mode and verify with primary or structured sources before acting."
    if event.importance_score >= 0.75:
        return "Assign an owner for immediate follow-up and impact assessment."
    return "Monitor for second-source confirmation and downstream changes."


def event_citations(event: Event) -> list[str]:
    return [evidence.evidence_url for evidence in event.evidence][:5]


def _event_query(db: Session, category: str | None, mode: str):
    query = db.query(Event).order_by(Event.importance_score.desc(), Event.created_at.desc())
    if category:
        query = query.filter(Event.category == category)
    if mode == "verified":
        verified_query = query.filter(Event.verification_status.in_(["verified", "partially_verified"]))
        if verified_query.count() > 0:
            return verified_query
    return query


def _object_for_event(db: Session, event: Event, mode: str) -> IntelligenceObject:
    obj = db.query(IntelligenceObject).filter(IntelligenceObject.event_id == event.id).first()
    if obj is None or obj.mode != mode or obj.verification_status != event.verification_status:
        obj = upsert_object_from_event(db, event, mode=mode)
    return obj


def _ledger_ids(db: Session, obj: IntelligenceObject) -> list[str]:
    return [
        row.id
        for row in db.query(EvidenceLedgerEntry)
        .filter(EvidenceLedgerEntry.intelligence_object_id == obj.id)
        .order_by(EvidenceLedgerEntry.created_at.asc())
        .limit(20)
        .all()
    ]


def generate_report(
    db: Session,
    report_type: str = "daily",
    category: str | None = None,
    limit: int = 10,
    mode: str = "verified",
) -> Report:
    started = time.perf_counter()
    now = datetime.now(UTC)
    events = _event_query(db, category, mode).limit(max(limit, 10)).all()
    top = events[:limit]
    title = f"{mode.title()} Intelligence Report - {now.date().isoformat()}"
    summary_lines = [
        f"- {event.title} ({event.verification_status}, aggregate {event.importance_score:.2f})"
        for event in top[:5]
    ] or ["- No significant events available yet."]
    lines = [
        f"# {title}",
        "",
        f"Mode: {mode}",
        "",
        "## Executive Summary",
        *summary_lines,
        "",
        "## Top Intelligence Objects",
    ]
    json_items = []
    for rank, event in enumerate(top, start=1):
        obj = _object_for_event(db, event, mode)
        citations = event_citations(event)
        citation_text = ", ".join(citations) if citations else "No citation available"
        action = recommended_action(event)
        indices = {
            "credibility": obj.index_credibility,
            "novelty": obj.index_novelty,
            "impact": obj.index_impact,
            "actionability": obj.index_actionability,
            "urgency": obj.index_urgency,
        }
        lines.extend(
            [
                f"### {rank}. {event.title}",
                f"- Domain: {obj.domain}",
                f"- Category: {event.category}",
                f"- Aggregate score: {obj.aggregate_score:.2f}",
                f"- Five indices: credibility {obj.index_credibility:.2f}, novelty {obj.index_novelty:.2f}, "
                f"impact {obj.index_impact:.2f}, actionability {obj.index_actionability:.2f}, urgency {obj.index_urgency:.2f}",
                f"- Verification: {event.verification_status}",
                f"- Compliance: {obj.compliance_status}",
                f"- Why it matters: {event.why_it_matters}",
                f"- Evidence: {citation_text}",
                f"- Recommended action: {action}",
                "",
            ]
        )
        json_items.append(
            {
                "rank": rank,
                "event_id": event.id,
                "intelligence_object_id": obj.id,
                "title": event.title,
                "domain": obj.domain,
                "category": event.category,
                "aggregate_score": obj.aggregate_score,
                "five_indices": indices,
                "verification_status": event.verification_status,
                "compliance_status": obj.compliance_status,
                "why_it_matters": event.why_it_matters,
                "recommended_action": action,
                "citations": citations,
                "evidence_ledger_entry_ids": _ledger_ids(db, obj),
            }
        )
    for section in sorted(set(SECTION_MAP.values())):
        lines.extend(["", f"## {section}"])
        section_events = [event for event in events if SECTION_MAP.get(event.category) == section]
        if section_events:
            for event in section_events[:8]:
                citations = event_citations(event)
                lines.append(
                    f"- {event.title} | score {event.importance_score:.2f} | {event.verification_status} | "
                    f"{citations[0] if citations else 'no citation'}"
                )
        else:
            lines.append("- No items.")
    lines.extend(["", "## Watch Next"])
    watch_next = [
        event
        for event in events
        if event.verification_status not in {"verified", "partially_verified"} or event.importance_score >= 0.6
    ]
    if watch_next:
        for event in watch_next[:10]:
            lines.append(f"- {event.title} | {event.verification_status} | {recommended_action(event)}")
    else:
        lines.append("- No follow-up items.")
    markdown = "\n".join(lines)
    report = Report(
        title=title,
        report_type=report_type,
        mode=mode,
        period_start=now - timedelta(days=1),
        period_end=now,
        markdown=markdown,
        json_content={"title": title, "mode": mode, "items": json_items},
        html="<pre>" + markdown.replace("&", "&amp;").replace("<", "&lt;") + "</pre>",
        generation_seconds=round(time.perf_counter() - started, 4),
        metadata_={"category": category, "event_count": len(events), "mode": mode},
    )
    db.add(report)
    db.flush()
    for item in json_items:
        db.add(
            ReportItem(
                report_id=report.id,
                event_id=item["event_id"],
                rank=item["rank"],
                title=item["title"],
                summary=item["why_it_matters"],
                recommended_action=item["recommended_action"],
            )
        )
    db.commit()
    db.refresh(report)
    return report
