from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Event
from app.models.all_models import IntelligenceObject
from app.schemas.dashboard import DashboardOverview


def dashboard_overview(db: Session) -> DashboardOverview:
    since = datetime.now(UTC) - timedelta(days=1)
    total_today = db.query(Event).filter(Event.created_at >= since).count()
    total_objects = db.query(IntelligenceObject).count()
    verified = db.query(Event).filter(Event.verification_status == "verified").count()
    high_impact = db.query(Event).filter(Event.importance_score >= 0.7).count()
    low_trust = db.query(Event).filter(Event.confidence < 0.5).count()
    category_rows = (
        db.query(Event.category, func.count(Event.id))
        .group_by(Event.category)
        .order_by(func.count(Event.id).desc())
        .all()
    )
    mode_rows = db.query(IntelligenceObject.mode, func.count(IntelligenceObject.id)).group_by(IntelligenceObject.mode).all()
    index_row = db.query(
        func.avg(IntelligenceObject.index_credibility),
        func.avg(IntelligenceObject.index_novelty),
        func.avg(IntelligenceObject.index_impact),
        func.avg(IntelligenceObject.index_actionability),
        func.avg(IntelligenceObject.index_urgency),
    ).first()
    trend = []
    for i in range(6, -1, -1):
        day = datetime.now(UTC).date() - timedelta(days=i)
        start = datetime.combine(day, datetime.min.time(), tzinfo=UTC)
        end = start + timedelta(days=1)
        trend.append(
            {
                "date": day.isoformat(),
                "events": db.query(Event).filter(Event.created_at >= start, Event.created_at < end).count(),
            }
        )
    top_events = [
        {
            "id": event.id,
            "title": event.title,
            "category": event.category,
            "importance_score": event.importance_score,
            "confidence": event.confidence,
            "verification_status": event.verification_status,
        }
        for event in db.query(Event).order_by(Event.importance_score.desc()).limit(10).all()
    ]
    return DashboardOverview(
        total_events_today=total_today,
        total_intelligence_objects=total_objects,
        verified_events=verified,
        high_impact_events=high_impact,
        low_trust_events=low_trust,
        mode_distribution=[{"mode": row[0], "count": row[1]} for row in mode_rows],
        five_index_averages={
            "credibility": round(float(index_row[0] or 0.0), 4),
            "novelty": round(float(index_row[1] or 0.0), 4),
            "impact": round(float(index_row[2] or 0.0), 4),
            "actionability": round(float(index_row[3] or 0.0), 4),
            "urgency": round(float(index_row[4] or 0.0), 4),
        },
        category_distribution=[{"category": row[0], "count": row[1]} for row in category_rows],
        trend=trend,
        top_events=top_events,
    )
