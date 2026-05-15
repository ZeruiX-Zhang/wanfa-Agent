from __future__ import annotations

from datetime import UTC, datetime

from app.models import Event


def clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def importance_score(
    impact_score: float,
    confidence_score: float,
    novelty_score: float,
    actionability_score: float,
    source_diversity_score: float,
) -> float:
    return round(
        clamp(
            impact_score * 0.30
            + confidence_score * 0.25
            + novelty_score * 0.15
            + actionability_score * 0.20
            + source_diversity_score * 0.10
        ),
        4,
    )


def event_importance(event: Event, source_diversity_score: float = 0.1) -> float:
    return importance_score(
        event.impact_score,
        event.confidence,
        event.novelty_score,
        event.actionability_score,
        source_diversity_score,
    )


def urgency_index(event_time: datetime | None, impact_score: float) -> float:
    if event_time is None:
        return round(clamp(0.35 + impact_score * 0.35), 4)
    if event_time.tzinfo is None:
        event_time = event_time.replace(tzinfo=UTC)
    age_hours = max((datetime.now(UTC) - event_time).total_seconds() / 3600, 0.0)
    freshness = max(0.0, 1.0 - age_hours / 72.0)
    return round(clamp(freshness * 0.60 + impact_score * 0.40), 4)


def five_indices(
    *,
    credibility: float,
    novelty: float,
    impact: float,
    actionability: float,
    urgency: float,
) -> dict[str, float]:
    return {
        "credibility": round(clamp(credibility), 4),
        "novelty": round(clamp(novelty), 4),
        "impact": round(clamp(impact), 4),
        "actionability": round(clamp(actionability), 4),
        "urgency": round(clamp(urgency), 4),
    }


def aggregate_index_score(indices: dict[str, float]) -> float:
    return round(
        clamp(
            indices.get("impact", 0.0) * 0.30
            + indices.get("credibility", 0.0) * 0.25
            + indices.get("novelty", 0.0) * 0.15
            + indices.get("actionability", 0.0) * 0.20
            + indices.get("urgency", 0.0) * 0.10
        ),
        4,
    )


def event_five_indices(event: Event, source_count: int = 0, evidence_count: int = 0) -> dict[str, float]:
    source_bonus = min(source_count, 4) * 0.035
    evidence_bonus = min(evidence_count, 5) * 0.02
    verified_bonus = (
        0.1
        if event.verification_status == "verified"
        else 0.05
        if event.verification_status == "partially_verified"
        else 0.0
    )
    return five_indices(
        credibility=event.confidence + source_bonus + evidence_bonus + verified_bonus,
        novelty=event.novelty_score,
        impact=event.impact_score,
        actionability=event.actionability_score,
        urgency=urgency_index(event.event_time, event.impact_score),
    )


def apply_event_indices(event: Event, source_count: int = 0, evidence_count: int = 0) -> dict[str, float]:
    indices = event_five_indices(event, source_count=source_count, evidence_count=evidence_count)
    event.index_credibility = indices["credibility"]
    event.index_novelty = indices["novelty"]
    event.index_impact = indices["impact"]
    event.index_actionability = indices["actionability"]
    event.index_urgency = indices["urgency"]
    event.importance_score = aggregate_index_score(indices)
    return indices


def confidence_from_sources(has_official: bool, source_count: int, trust_scores: list[float]) -> float:
    max_trust = max(trust_scores or [0.5])
    avg_trust = sum(trust_scores or [0.5]) / max(len(trust_scores), 1)
    if has_official and source_count >= 2 and avg_trust >= 0.75:
        return 0.92
    if has_official:
        return max(0.8, max_trust)
    if source_count >= 3:
        return clamp(0.65 + avg_trust * 0.15)
    if source_count >= 2:
        return clamp(0.55 + avg_trust * 0.15)
    return clamp(min(max_trust, 0.65))
