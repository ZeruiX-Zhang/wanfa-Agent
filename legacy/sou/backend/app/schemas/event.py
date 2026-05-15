from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import Timestamped

EventCategory = Literal[
    "ai_model",
    "ai_product",
    "ai_company",
    "crypto_market",
    "crypto_security",
    "defi",
    "tech_business",
    "ecommerce_market",
    "paper_research",
    "open_source",
    "regulation",
    "other",
]

VerificationStatus = Literal[
    "verified",
    "partially_verified",
    "unverified",
    "conflicting",
    "low_quality",
    "needs_human_review",
]


class Claim(BaseModel):
    text: str = Field(min_length=1)
    evidence_quote: str | None = None
    evidence_url: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    needs_verification: bool = True


class ExtractedEvent(BaseModel):
    title: str = Field(min_length=1)
    category: EventCategory
    event_time: datetime | None = None
    entities: list[str] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    summary: str = Field(min_length=1)
    why_it_matters: str = Field(min_length=1)
    affected_parties: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    novelty_score: float = Field(ge=0.0, le=1.0)
    impact_score: float = Field(ge=0.0, le=1.0)
    actionability_score: float = Field(ge=0.0, le=1.0)
    source_document_ids: list[str] = Field(min_length=1)

    @field_validator("claims")
    @classmethod
    def important_claims_have_evidence(cls, claims: list[Claim]) -> list[Claim]:
        for claim in claims:
            if claim.confidence >= 0.7 and not claim.evidence_url:
                raise ValueError("high-confidence claims require evidence_url")
        return claims


class EventEvidenceRead(Timestamped):
    id: str
    event_id: str
    normalized_document_id: str
    evidence_url: str
    title: str | None
    source_name: str | None
    quote: str | None


class EventClaimRead(Timestamped):
    id: str
    event_id: str
    text: str
    evidence_quote: str | None
    evidence_url: str
    confidence: float
    needs_verification: bool


class EventRead(Timestamped):
    id: str
    title: str
    category: str
    event_time: datetime | None
    entities: list[str]
    summary: str
    why_it_matters: str
    affected_parties: list[str]
    confidence: float
    novelty_score: float
    impact_score: float
    actionability_score: float
    index_credibility: float
    index_novelty: float
    index_impact: float
    index_actionability: float
    index_urgency: float
    importance_score: float
    verification_status: str
    extraction_status: str
    cluster_id: str | None
    metadata_: dict


class EventDetail(EventRead):
    claims: list[EventClaimRead] = Field(default_factory=list)
    evidence: list[EventEvidenceRead] = Field(default_factory=list)
