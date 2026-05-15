"""Dataclass schemas for retrieval results and evidence readiness."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from services.knowledge.models import (
    EvidenceRecord,
    JsonDict,
    SourceRef,
    TrustLevel,
    dataclass_to_dict,
)


class EvidenceRole(str, Enum):
    """How a retrieved record relates to the query."""

    SUPPORTING = "supporting"
    COUNTERARGUMENT = "counterargument"


@dataclass(frozen=True)
class RetrievalQuery:
    """Normalized retrieval request."""

    text: str
    min_trusted_evidence: int = 1
    include_untrusted: bool = True
    metadata: JsonDict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.min_trusted_evidence < 0:
            raise ValueError("min_trusted_evidence must be non-negative")

    def to_dict(self) -> JsonDict:
        """Return a JSON-ready query."""

        return dataclass_to_dict(self)


@dataclass(frozen=True)
class RetrievedEvidence:
    """Evidence returned by retrieval, including trust and source handling."""

    id: str
    source_id: str
    claim: str
    excerpt: str
    uri: str | None = None
    trust_level: TrustLevel = TrustLevel.UNKNOWN
    role: EvidenceRole = EvidenceRole.SUPPORTING
    score: float = 0.0
    is_external: bool = False
    untrusted_reason: str | None = None
    metadata: JsonDict = field(default_factory=dict)

    @classmethod
    def from_ledger(
        cls,
        evidence: EvidenceRecord,
        *,
        source: SourceRef | None = None,
        score: float = 0.0,
    ) -> "RetrievedEvidence":
        """Create a retrieval result from an evidence ledger entry."""

        trust_level = evidence.trust_level
        is_external = evidence.is_external
        untrusted_reason = evidence.untrusted_reason
        uri = evidence.uri

        if source is not None:
            is_external = is_external or source.is_external
            uri = uri or source.uri
            untrusted_reason = untrusted_reason or source.untrusted_reason
            if trust_level is TrustLevel.UNKNOWN:
                trust_level = source.trust_level
            if source.trust_level is TrustLevel.UNTRUSTED:
                trust_level = TrustLevel.UNTRUSTED

        if is_external and trust_level is TrustLevel.UNKNOWN:
            trust_level = TrustLevel.UNTRUSTED
        if is_external and trust_level is TrustLevel.UNTRUSTED and untrusted_reason is None:
            untrusted_reason = (
                "External source requires review before it can support a decision memo."
            )

        return cls(
            id=evidence.id,
            source_id=evidence.source_id,
            claim=evidence.claim,
            excerpt=evidence.excerpt,
            uri=uri,
            trust_level=trust_level,
            role=EvidenceRole.SUPPORTING
            if evidence.supports
            else EvidenceRole.COUNTERARGUMENT,
            score=score,
            is_external=is_external,
            untrusted_reason=untrusted_reason,
            metadata=evidence.metadata,
        )

    @classmethod
    def from_untrusted_external(
        cls,
        *,
        id: str,
        source_id: str,
        claim: str,
        excerpt: str,
        uri: str,
        score: float = 0.0,
        metadata: JsonDict | None = None,
    ) -> "RetrievedEvidence":
        """Create an untrusted external retrieval item."""

        return cls(
            id=id,
            source_id=source_id,
            claim=claim,
            excerpt=excerpt,
            uri=uri,
            trust_level=TrustLevel.UNTRUSTED,
            role=EvidenceRole.SUPPORTING,
            score=score,
            is_external=True,
            untrusted_reason=(
                "External source requires review before it can support a decision memo."
            ),
            metadata=metadata or {},
        )

    @property
    def supports(self) -> bool:
        """Return whether this result supports the queried claim."""

        return self.role is EvidenceRole.SUPPORTING

    @property
    def usable_for_decision(self) -> bool:
        """Return whether this result can support a decision memo."""

        return self.supports and self.trust_level is TrustLevel.TRUSTED

    def to_dict(self) -> JsonDict:
        """Return JSON-ready retrieved evidence."""

        return dataclass_to_dict(self)


@dataclass(frozen=True)
class RetrievalResult:
    """Retrieval response with explicit insufficient-evidence behavior."""

    query: RetrievalQuery
    items: tuple[RetrievedEvidence, ...] = ()
    insufficient_evidence: bool = True
    insufficient_reason: str = "No evidence was retrieved."
    confidence: float = 0.0

    @classmethod
    def from_items(
        cls,
        *,
        query: RetrievalQuery,
        items: tuple[RetrievedEvidence, ...],
    ) -> "RetrievalResult":
        """Build a result and compute evidence sufficiency."""

        trusted_support = tuple(item for item in items if item.usable_for_decision)
        trusted_counter = tuple(
            item
            for item in items
            if item.role is EvidenceRole.COUNTERARGUMENT
            and item.trust_level is TrustLevel.TRUSTED
        )
        if len(trusted_support) < query.min_trusted_evidence:
            if items and all(item.trust_level is TrustLevel.UNTRUSTED for item in items):
                reason = (
                    "Only untrusted evidence was retrieved; mark memo as insufficient evidence."
                )
            elif items:
                reason = (
                    "Retrieved evidence does not meet the trusted evidence threshold."
                )
            else:
                reason = "No evidence was retrieved."
            return cls(
                query=query,
                items=items,
                insufficient_evidence=True,
                insufficient_reason=reason,
                confidence=0.0,
            )

        confidence = min(
            0.95,
            0.45 + (0.2 * len(trusted_support)) - (0.15 * len(trusted_counter)),
        )
        return cls(
            query=query,
            items=items,
            insufficient_evidence=False,
            insufficient_reason="",
            confidence=max(0.1, confidence),
        )

    @property
    def supporting_evidence(self) -> tuple[RetrievedEvidence, ...]:
        """Return supporting retrieval items."""

        return tuple(item for item in self.items if item.role is EvidenceRole.SUPPORTING)

    @property
    def counterarguments(self) -> tuple[RetrievedEvidence, ...]:
        """Return counterargument retrieval items."""

        return tuple(
            item for item in self.items if item.role is EvidenceRole.COUNTERARGUMENT
        )

    @property
    def untrusted_items(self) -> tuple[RetrievedEvidence, ...]:
        """Return untrusted retrieval items."""

        return tuple(item for item in self.items if item.trust_level is TrustLevel.UNTRUSTED)

    def to_dict(self) -> JsonDict:
        """Return a JSON-ready retrieval result."""

        return dataclass_to_dict(self)
