from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import FiveIndexScores, IntelligenceMode, Timestamped


class IntelligenceObjectCreate(BaseModel):
    object_type: str = Field(default="event", max_length=80)
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    domain: str = Field(min_length=1, max_length=80)
    language: str = Field(default="und", max_length=20)
    region: str | None = Field(default=None, max_length=80)
    canonical_url: str | None = None
    entities: list[str] = Field(default_factory=list)
    source_document_ids: list[str] = Field(default_factory=list)
    mode: IntelligenceMode = "speed"
    verification_status: str = "unverified"
    scores: FiveIndexScores | None = None
    compliance_status: str = "unreviewed"
    metadata: dict = Field(default_factory=dict)


class IntelligenceObjectRead(Timestamped):
    id: str
    object_type: str
    title: str
    summary: str
    domain: str
    language: str
    region: str | None
    canonical_url: str | None
    event_id: str | None
    cluster_id: str | None
    normalized_document_id: str | None
    entities: list[str]
    source_document_ids: list[str]
    source_count: int
    evidence_count: int
    mode: str
    status: str
    verification_status: str
    index_credibility: float
    index_novelty: float
    index_impact: float
    index_actionability: float
    index_urgency: float
    aggregate_score: float
    compliance_status: str
    metadata_: dict


class EvidenceLedgerEntryRead(Timestamped):
    id: str
    intelligence_object_id: str | None
    event_id: str | None
    normalized_document_id: str | None
    source_id: str | None
    evidence_url: str
    title: str | None
    source_name: str | None
    source_type: str | None
    quote: str | None
    captured_at: datetime
    content_hash: str | None
    ledger_hash: str
    citation_status: str
    legal_use_policy: str
    compliance_status: str
    trust_score: float
    relevance_score: float
    supports_claims: list[str]
    metadata_: dict


class IntelligenceObjectDetail(IntelligenceObjectRead):
    ledger_entries: list[EvidenceLedgerEntryRead] = Field(default_factory=list)


class EventClusterRead(Timestamped):
    id: str
    title: str
    category: str
    language: str
    cross_language_key: str | None
    merged_summary: str
    source_diversity_score: float
    confidence_score: float
    importance_score: float
    verification_status: str
    metadata_: dict


class CrossLanguageCandidateRead(Timestamped):
    id: str
    cluster_id: str
    candidate_cluster_id: str
    source_language: str
    target_language: str
    similarity_score: float
    shared_entities: list[str]
    reason: str
    status: str
    metadata_: dict
