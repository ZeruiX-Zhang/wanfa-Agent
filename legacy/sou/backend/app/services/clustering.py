from __future__ import annotations

from difflib import SequenceMatcher

from sqlalchemy.orm import Session

from app.models import Event, EventCluster, EventEvidence, NormalizedDocument, Source
from app.models.all_models import CrossLanguageCandidate
from app.services.scoring import apply_event_indices, confidence_from_sources, importance_score

RELATED = {
    "crypto_market": {"defi", "crypto_security"},
    "defi": {"crypto_market"},
    "ai_model": {"ai_company", "ai_product"},
    "ai_product": {"ai_company", "ai_model"},
}


def _entity_overlap(a: list[str], b: list[str]) -> float:
    left, right = set(a or []), set(b or [])
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _related(a: str, b: str) -> bool:
    return a == b or b in RELATED.get(a, set()) or a in RELATED.get(b, set())


def _event_language(event: Event) -> str:
    metadata = event.metadata_ or {}
    if metadata.get("primary_language"):
        return metadata["primary_language"]
    languages = metadata.get("source_languages") or []
    return languages[0] if languages else "und"


def _cross_language_key(title: str) -> str:
    tokens = [token for token in title.lower().replace("/", " ").replace("-", " ").split() if len(token) > 2]
    return "-".join(tokens[:8])[:120] or "cluster"


def event_cluster_similarity(event: Event, cluster: EventCluster) -> float:
    title_score = SequenceMatcher(None, event.title.lower(), cluster.title.lower()).ratio()
    cluster_entities = (cluster.metadata_ or {}).get("entities", [])
    entity_score = _entity_overlap(event.entities, cluster_entities)
    category_score = 1.0 if _related(event.category, cluster.category) else 0.0
    return title_score * 0.55 + entity_score * 0.25 + category_score * 0.20


def cluster_similarity(left: EventCluster, right: EventCluster) -> float:
    title_score = SequenceMatcher(None, left.title.lower(), right.title.lower()).ratio()
    entity_score = _entity_overlap((left.metadata_ or {}).get("entities", []), (right.metadata_ or {}).get("entities", []))
    category_score = 1.0 if _related(left.category, right.category) else 0.0
    return title_score * 0.55 + entity_score * 0.25 + category_score * 0.20


def refresh_cluster_scores(db: Session, cluster: EventCluster) -> None:
    events = db.query(Event).filter(Event.cluster_id == cluster.id).all()
    if not events:
        return
    evidences = (
        db.query(EventEvidence, NormalizedDocument, Source)
        .join(NormalizedDocument, EventEvidence.normalized_document_id == NormalizedDocument.id)
        .join(Source, NormalizedDocument.source_id == Source.id)
        .filter(EventEvidence.event_id.in_([event.id for event in events]))
        .all()
    )
    source_ids = {source.id for _, _, source in evidences}
    trust_scores = [source.trust_score for _, _, source in evidences]
    has_official = any(source.type in {"official_blog", "custom_url"} and source.trust_score >= 0.8 for _, _, source in evidences)
    source_diversity = min(1.0, len(source_ids) / 4)
    confidence = confidence_from_sources(has_official, len(source_ids), trust_scores)
    avg_impact = sum(event.impact_score for event in events) / len(events)
    avg_novelty = sum(event.novelty_score for event in events) / len(events)
    avg_action = sum(event.actionability_score for event in events) / len(events)
    cluster.source_diversity_score = source_diversity
    cluster.confidence_score = confidence
    cluster.importance_score = importance_score(
        avg_impact, confidence, avg_novelty, avg_action, source_diversity
    )
    cluster.merged_summary = " ".join(event.summary for event in events[:3])[:1200]
    cluster.metadata_ = {
        **(cluster.metadata_ or {}),
        "event_ids": [event.id for event in events],
        "entities": sorted({entity for event in events for entity in (event.entities or [])})[:50],
        "evidence_document_count": len(evidences),
    }
    for event in events:
        event.confidence = confidence
        apply_event_indices(event, source_count=len(source_ids), evidence_count=len(evidences))
    db.commit()


def register_cross_language_candidates(db: Session, cluster: EventCluster) -> None:
    if cluster.language == "und":
        return
    others = (
        db.query(EventCluster)
        .filter(EventCluster.id != cluster.id, EventCluster.category == cluster.category, EventCluster.language != cluster.language)
        .limit(200)
        .all()
    )
    left_entities = set((cluster.metadata_ or {}).get("entities", []))
    for other in others:
        score = cluster_similarity(cluster, other)
        if score < 0.60:
            continue
        existing = (
            db.query(CrossLanguageCandidate)
            .filter(CrossLanguageCandidate.cluster_id == cluster.id, CrossLanguageCandidate.candidate_cluster_id == other.id)
            .first()
        )
        shared = sorted(left_entities & set((other.metadata_ or {}).get("entities", [])))[:20]
        if existing:
            existing.similarity_score = score
            existing.shared_entities = shared
            existing.reason = "same category with title/entity similarity"
            continue
        db.add(
            CrossLanguageCandidate(
                cluster_id=cluster.id,
                candidate_cluster_id=other.id,
                source_language=cluster.language,
                target_language=other.language,
                similarity_score=score,
                shared_entities=shared,
                reason="same category with title/entity similarity",
                status="candidate",
                metadata_={"cross_language_key": cluster.cross_language_key},
            )
        )
    db.commit()


def cluster_unclustered(db: Session, limit: int = 200) -> list[EventCluster]:
    events = (
        db.query(Event)
        .filter(Event.cluster_id.is_(None))
        .order_by(Event.importance_score.desc())
        .limit(limit)
        .all()
    )
    touched: dict[str, EventCluster] = {}
    for event in events:
        language = _event_language(event)
        clusters = (
            db.query(EventCluster)
            .filter(EventCluster.category == event.category, EventCluster.language == language)
            .limit(100)
            .all()
        )
        best_cluster = None
        best_score = 0.0
        for cluster in clusters:
            score = event_cluster_similarity(event, cluster)
            if score > best_score:
                best_cluster, best_score = cluster, score
        if best_cluster and best_score >= 0.72:
            event.cluster_id = best_cluster.id
            touched[best_cluster.id] = best_cluster
        else:
            cluster = EventCluster(
                title=event.title,
                category=event.category,
                language=language,
                cross_language_key=_cross_language_key(event.title),
                merged_summary=event.summary,
                source_diversity_score=0.0,
                confidence_score=event.confidence,
                importance_score=event.importance_score,
                verification_status=event.verification_status,
                metadata_={"entities": event.entities, "event_ids": [event.id]},
            )
            db.add(cluster)
            db.flush()
            event.cluster_id = cluster.id
            touched[cluster.id] = cluster
            db.commit()
    for cluster in touched.values():
        refresh_cluster_scores(db, cluster)
        register_cross_language_candidates(db, cluster)
    return list(touched.values())
