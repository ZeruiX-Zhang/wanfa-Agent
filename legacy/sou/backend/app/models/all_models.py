from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def new_id() -> str:
    return str(uuid.uuid4())


def now_utc() -> datetime:
    return datetime.now(UTC)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc
    )


class Source(Base, TimestampMixin):
    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    category: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    url: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    trust_score: Mapped[float] = mapped_column(Float, default=0.6)
    language: Mapped[str] = mapped_column(String(20), default="en")
    country: Mapped[str | None] = mapped_column(String(20))
    fetch_interval_minutes: Mapped[int] = mapped_column(Integer, default=1440)
    rate_limit_per_minute: Mapped[int] = mapped_column(Integer, default=30)
    legal_use_policy: Mapped[str] = mapped_column(String(80), default="metadata_and_snippets", index=True)
    robots_policy: Mapped[str] = mapped_column(String(80), default="unknown", index=True)
    license_name: Mapped[str | None] = mapped_column(String(160))
    terms_url: Mapped[str | None] = mapped_column(Text)
    compliance_status: Mapped[str] = mapped_column(String(80), default="unreviewed", index=True)
    collection_mode: Mapped[str] = mapped_column(String(80), default="metadata_only")
    attribution_required: Mapped[bool] = mapped_column(Boolean, default=True)
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_status: Mapped[str | None] = mapped_column(String(80))
    last_error: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    raw_documents: Mapped[list[RawDocument]] = relationship(back_populates="source")
    legal_policy: Mapped[SourcePolicy | None] = relationship(
        back_populates="source", cascade="all, delete-orphan", uselist=False
    )


class SourcePolicy(Base, TimestampMixin):
    __tablename__ = "source_policies"
    __table_args__ = (UniqueConstraint("source_id", name="uq_source_policies_source_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"), index=True)
    access_type: Mapped[str] = mapped_column(String(80), default="public_web")
    allowed_uses: Mapped[list] = mapped_column(JSON, default=list)
    disallowed_uses: Mapped[list] = mapped_column(JSON, default=list)
    robots_txt_status: Mapped[str] = mapped_column(String(80), default="unknown")
    license_name: Mapped[str | None] = mapped_column(String(160))
    terms_url: Mapped[str | None] = mapped_column(Text)
    retention_days: Mapped[int] = mapped_column(Integer, default=365)
    pii_handling: Mapped[str] = mapped_column(String(120), default="minimize_and_redact")
    requires_attribution: Mapped[bool] = mapped_column(Boolean, default=True)
    compliance_status: Mapped[str] = mapped_column(String(80), default="unreviewed", index=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(120))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    source: Mapped[Source] = relationship(back_populates="legal_policy")


class ComplianceDecision(Base, TimestampMixin):
    __tablename__ = "compliance_decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"), index=True)
    source_policy_id: Mapped[str | None] = mapped_column(ForeignKey("source_policies.id"), index=True)
    mode: Mapped[str] = mapped_column(String(40), default="speed", index=True)
    decision: Mapped[str] = mapped_column(String(80), index=True)
    reason: Mapped[str] = mapped_column(Text)
    checks: Mapped[dict] = mapped_column(JSON, default=dict)
    decided_by: Mapped[str] = mapped_column(String(120), default="system")
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    source: Mapped[Source] = relationship()
    source_policy: Mapped[SourcePolicy | None] = relationship()


class RawDocument(Base, TimestampMixin):
    __tablename__ = "raw_documents"
    __table_args__ = (UniqueConstraint("source_id", "url", name="uq_raw_source_url"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"), index=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    snippet: Mapped[str | None] = mapped_column(Text)
    raw_content: Mapped[str | None] = mapped_column(Text)
    content_type: Mapped[str | None] = mapped_column(String(100))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    status: Mapped[str] = mapped_column(String(80), default="fetched", index=True)
    error_reason: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    source: Mapped[Source] = relationship(back_populates="raw_documents")
    normalized: Mapped[NormalizedDocument | None] = relationship(back_populates="raw_document")


class NormalizedDocument(Base, TimestampMixin):
    __tablename__ = "normalized_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    raw_document_id: Mapped[str] = mapped_column(
        ForeignKey("raw_documents.id"), unique=True, index=True
    )
    canonical_url: Mapped[str] = mapped_column(Text, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    clean_text: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(20), default="en")
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"), index=True)
    author: Mapped[str | None] = mapped_column(String(200))
    entities: Mapped[list] = mapped_column(JSON, default=list)
    domain: Mapped[str | None] = mapped_column(String(80), index=True)
    legal_use_policy: Mapped[str] = mapped_column(String(80), default="metadata_and_snippets")
    compliance_status: Mapped[str] = mapped_column(String(80), default="unreviewed", index=True)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    simhash: Mapped[str | None] = mapped_column(String(32), index=True)
    embedding_id: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(80), default="normalized", index=True)
    quality_flags: Mapped[list] = mapped_column(JSON, default=list)
    published_at_inferred: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    raw_document: Mapped[RawDocument] = relationship(back_populates="normalized")
    source: Mapped[Source] = relationship()


class Event(Base, TimestampMixin):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(80), index=True)
    event_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    entities: Mapped[list] = mapped_column(JSON, default=list)
    summary: Mapped[str] = mapped_column(Text)
    why_it_matters: Mapped[str] = mapped_column(Text)
    affected_parties: Mapped[list] = mapped_column(JSON, default=list)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    novelty_score: Mapped[float] = mapped_column(Float, default=0.5)
    impact_score: Mapped[float] = mapped_column(Float, default=0.5)
    actionability_score: Mapped[float] = mapped_column(Float, default=0.5)
    index_credibility: Mapped[float] = mapped_column(Float, default=0.5, index=True)
    index_novelty: Mapped[float] = mapped_column(Float, default=0.5)
    index_impact: Mapped[float] = mapped_column(Float, default=0.5)
    index_actionability: Mapped[float] = mapped_column(Float, default=0.5)
    index_urgency: Mapped[float] = mapped_column(Float, default=0.5)
    importance_score: Mapped[float] = mapped_column(Float, default=0.5, index=True)
    verification_status: Mapped[str] = mapped_column(String(80), default="unverified", index=True)
    extraction_status: Mapped[str] = mapped_column(String(80), default="extracted", index=True)
    cluster_id: Mapped[str | None] = mapped_column(ForeignKey("event_clusters.id"), index=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    claims: Mapped[list[EventClaim]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )
    evidence: Mapped[list[EventEvidence]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )


class EventClaim(Base, TimestampMixin):
    __tablename__ = "event_claims"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), index=True)
    text: Mapped[str] = mapped_column(Text)
    evidence_quote: Mapped[str | None] = mapped_column(Text)
    evidence_url: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    needs_verification: Mapped[bool] = mapped_column(Boolean, default=True)

    event: Mapped[Event] = relationship(back_populates="claims")


class EventCluster(Base, TimestampMixin):
    __tablename__ = "event_clusters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(80), index=True)
    language: Mapped[str] = mapped_column(String(20), default="und", index=True)
    cross_language_key: Mapped[str | None] = mapped_column(String(120), index=True)
    merged_summary: Mapped[str] = mapped_column(Text)
    source_diversity_score: Mapped[float] = mapped_column(Float, default=0.0)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.5)
    importance_score: Mapped[float] = mapped_column(Float, default=0.5, index=True)
    verification_status: Mapped[str] = mapped_column(String(80), default="unverified", index=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    events: Mapped[list[Event]] = relationship()


class CrossLanguageCandidate(Base, TimestampMixin):
    __tablename__ = "cross_language_candidates"
    __table_args__ = (UniqueConstraint("cluster_id", "candidate_cluster_id", name="uq_cross_language_pair"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    cluster_id: Mapped[str] = mapped_column(ForeignKey("event_clusters.id"), index=True)
    candidate_cluster_id: Mapped[str] = mapped_column(ForeignKey("event_clusters.id"), index=True)
    source_language: Mapped[str] = mapped_column(String(20), index=True)
    target_language: Mapped[str] = mapped_column(String(20), index=True)
    similarity_score: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    shared_entities: Mapped[list] = mapped_column(JSON, default=list)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(80), default="candidate", index=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    cluster: Mapped[EventCluster] = relationship(foreign_keys=[cluster_id])
    candidate_cluster: Mapped[EventCluster] = relationship(foreign_keys=[candidate_cluster_id])


class EventEvidence(Base, TimestampMixin):
    __tablename__ = "event_evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), index=True)
    normalized_document_id: Mapped[str] = mapped_column(
        ForeignKey("normalized_documents.id"), index=True
    )
    evidence_url: Mapped[str] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    source_name: Mapped[str | None] = mapped_column(String(200))
    quote: Mapped[str | None] = mapped_column(Text)
    ledger_hash: Mapped[str | None] = mapped_column(String(64), index=True)

    event: Mapped[Event] = relationship(back_populates="evidence")
    normalized_document: Mapped[NormalizedDocument] = relationship()


class IntelligenceObject(Base, TimestampMixin):
    __tablename__ = "intelligence_objects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    object_type: Mapped[str] = mapped_column(String(80), default="event", index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str] = mapped_column(String(80), index=True)
    language: Mapped[str] = mapped_column(String(20), default="und", index=True)
    region: Mapped[str | None] = mapped_column(String(80), index=True)
    canonical_url: Mapped[str | None] = mapped_column(Text)
    event_id: Mapped[str | None] = mapped_column(ForeignKey("events.id"), index=True)
    cluster_id: Mapped[str | None] = mapped_column(ForeignKey("event_clusters.id"), index=True)
    normalized_document_id: Mapped[str | None] = mapped_column(ForeignKey("normalized_documents.id"), index=True)
    entities: Mapped[list] = mapped_column(JSON, default=list)
    source_document_ids: Mapped[list] = mapped_column(JSON, default=list)
    source_count: Mapped[int] = mapped_column(Integer, default=0)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0)
    mode: Mapped[str] = mapped_column(String(40), default="speed", index=True)
    status: Mapped[str] = mapped_column(String(80), default="active", index=True)
    verification_status: Mapped[str] = mapped_column(String(80), default="unverified", index=True)
    index_credibility: Mapped[float] = mapped_column(Float, default=0.5, index=True)
    index_novelty: Mapped[float] = mapped_column(Float, default=0.5)
    index_impact: Mapped[float] = mapped_column(Float, default=0.5)
    index_actionability: Mapped[float] = mapped_column(Float, default=0.5)
    index_urgency: Mapped[float] = mapped_column(Float, default=0.5)
    aggregate_score: Mapped[float] = mapped_column(Float, default=0.5, index=True)
    compliance_status: Mapped[str] = mapped_column(String(80), default="unreviewed", index=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    event: Mapped[Event | None] = relationship()
    cluster: Mapped[EventCluster | None] = relationship()
    normalized_document: Mapped[NormalizedDocument | None] = relationship()
    ledger_entries: Mapped[list[EvidenceLedgerEntry]] = relationship(
        back_populates="intelligence_object", cascade="all, delete-orphan"
    )


class EvidenceLedgerEntry(Base, TimestampMixin):
    __tablename__ = "evidence_ledger_entries"
    __table_args__ = (UniqueConstraint("ledger_hash", name="uq_evidence_ledger_hash"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    intelligence_object_id: Mapped[str | None] = mapped_column(ForeignKey("intelligence_objects.id"), index=True)
    event_id: Mapped[str | None] = mapped_column(ForeignKey("events.id"), index=True)
    normalized_document_id: Mapped[str | None] = mapped_column(ForeignKey("normalized_documents.id"), index=True)
    source_id: Mapped[str | None] = mapped_column(ForeignKey("sources.id"), index=True)
    evidence_url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    source_name: Mapped[str | None] = mapped_column(String(200))
    source_type: Mapped[str | None] = mapped_column(String(80), index=True)
    quote: Mapped[str | None] = mapped_column(Text)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    ledger_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    citation_status: Mapped[str] = mapped_column(String(80), default="captured", index=True)
    legal_use_policy: Mapped[str] = mapped_column(String(80), default="metadata_and_snippets")
    compliance_status: Mapped[str] = mapped_column(String(80), default="unreviewed", index=True)
    trust_score: Mapped[float] = mapped_column(Float, default=0.5)
    relevance_score: Mapped[float] = mapped_column(Float, default=0.5)
    supports_claims: Mapped[list] = mapped_column(JSON, default=list)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    intelligence_object: Mapped[IntelligenceObject | None] = relationship(back_populates="ledger_entries")
    event: Mapped[Event | None] = relationship()
    normalized_document: Mapped[NormalizedDocument | None] = relationship()
    source: Mapped[Source | None] = relationship()


class Report(Base, TimestampMixin):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    report_type: Mapped[str] = mapped_column(String(80), index=True)
    mode: Mapped[str] = mapped_column(String(40), default="verified", index=True)
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    markdown: Mapped[str] = mapped_column(Text)
    json_content: Mapped[dict] = mapped_column(JSON, default=dict)
    html: Mapped[str | None] = mapped_column(Text)
    generation_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    items: Mapped[list[ReportItem]] = relationship(
        back_populates="report", cascade="all, delete-orphan"
    )


class ReportItem(Base, TimestampMixin):
    __tablename__ = "report_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    report_id: Mapped[str] = mapped_column(ForeignKey("reports.id"), index=True)
    event_id: Mapped[str | None] = mapped_column(ForeignKey("events.id"), index=True)
    rank: Mapped[int] = mapped_column(Integer, default=0)
    title: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text)
    recommended_action: Mapped[str] = mapped_column(Text)

    report: Mapped[Report] = relationship(back_populates="items")
    event: Mapped[Event | None] = relationship()


class Watchlist(Base, TimestampMixin):
    __tablename__ = "watchlists"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    type: Mapped[str] = mapped_column(String(80), index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    value: Mapped[str] = mapped_column(String(300), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)


class Job(Base, TimestampMixin):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(String(80), index=True)
    mode: Mapped[str] = mapped_column(String(40), default="speed", index=True)
    status: Mapped[str] = mapped_column(String(80), default="queued", index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    logs: Mapped[list[JobLog]] = relationship(back_populates="job", cascade="all, delete-orphan")


class JobLog(Base, TimestampMixin):
    __tablename__ = "job_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), index=True)
    level: Mapped[str] = mapped_column(String(30), default="info")
    stage: Mapped[str] = mapped_column(String(80), index=True)
    message: Mapped[str] = mapped_column(Text)
    details: Mapped[dict] = mapped_column(JSON, default=dict)

    job: Mapped[Job] = relationship(back_populates="logs")


class ProductReview(Base, TimestampMixin):
    __tablename__ = "product_reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    product_name: Mapped[str] = mapped_column(String(200), index=True)
    official_url: Mapped[str | None] = mapped_column(Text)
    target_users: Mapped[list] = mapped_column(JSON, default=list)
    competitors: Mapped[list] = mapped_column(JSON, default=list)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(80), default="completed", index=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)

    evidence: Mapped[list[ProductReviewEvidence]] = relationship(
        back_populates="review", cascade="all, delete-orphan"
    )


class ProductReviewEvidence(Base, TimestampMixin):
    __tablename__ = "product_review_evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    review_id: Mapped[str] = mapped_column(ForeignKey("product_reviews.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(80))
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    snippet: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)

    review: Mapped[ProductReview] = relationship(back_populates="evidence")


class Setting(Base, TimestampMixin):
    __tablename__ = "settings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False)


class ApiUsageLog(Base, TimestampMixin):
    __tablename__ = "api_usage_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    provider: Mapped[str] = mapped_column(String(80), index=True)
    operation: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(80), index=True)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    cost_estimate: Mapped[float] = mapped_column(Float, default=0.0)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
