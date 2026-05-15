"""Dataclass schemas for knowledge, source, evidence, and pending writes."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


JsonDict = dict[str, Any]


class SourceKind(str, Enum):
    """Known source categories used by read projections."""

    INTERNAL = "internal"
    LEGACY_SOU = "legacy_sou"
    WEB = "web"
    FILE = "file"
    USER_CAPTURE = "user_capture"
    SYSTEM = "system"


class TrustLevel(str, Enum):
    """Trust state for source and evidence material."""

    TRUSTED = "trusted"
    UNKNOWN = "unknown"
    UNTRUSTED = "untrusted"


class ReviewStatus(str, Enum):
    """Review lifecycle for knowledge writes."""

    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class KnowledgeItemKind(str, Enum):
    """Knowledge item categories."""

    FORMAL = "formal"
    CAPTURE = "capture"
    REFLECTION = "reflection"
    AI_GENERATED = "ai_generated"


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    """Create a short, opaque service-layer identifier."""

    return f"{prefix}_{uuid4().hex}"


def _json_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value):
        return dataclass_to_dict(value)
    if isinstance(value, tuple | list):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    return value


def dataclass_to_dict(value: Any) -> JsonDict:
    """Serialize a dataclass tree using API-friendly primitive values."""

    if not is_dataclass(value):
        raise TypeError("dataclass_to_dict expects a dataclass instance")
    return {key: _json_value(item) for key, item in asdict(value).items()}


@dataclass(frozen=True)
class SourceRef:
    """Read model for a knowledge source.

    External web pages and files default to untrusted until reviewed.
    """

    id: str
    title: str
    kind: SourceKind = SourceKind.INTERNAL
    uri: str | None = None
    trust_level: TrustLevel = TrustLevel.UNKNOWN
    is_external: bool = False
    untrusted_reason: str | None = None
    metadata: JsonDict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.is_external and self.trust_level is TrustLevel.UNKNOWN:
            object.__setattr__(self, "trust_level", TrustLevel.UNTRUSTED)
        if (
            self.is_external
            and self.trust_level is TrustLevel.UNTRUSTED
            and self.untrusted_reason is None
        ):
            object.__setattr__(
                self,
                "untrusted_reason",
                "External source requires review before it can support formal knowledge.",
            )

    @classmethod
    def external(
        cls,
        *,
        id: str,
        title: str,
        uri: str,
        kind: SourceKind = SourceKind.WEB,
        metadata: JsonDict | None = None,
    ) -> "SourceRef":
        """Create an external source that is untrusted by default."""

        return cls(
            id=id,
            title=title,
            kind=kind,
            uri=uri,
            trust_level=TrustLevel.UNTRUSTED,
            is_external=True,
            metadata=metadata or {},
        )

    @property
    def is_untrusted(self) -> bool:
        """Return whether the source is not usable as trusted evidence."""

        return self.trust_level is TrustLevel.UNTRUSTED

    def to_dict(self) -> JsonDict:
        """Return a JSON-ready source projection."""

        return dataclass_to_dict(self)


@dataclass(frozen=True)
class EvidenceRecord:
    """Evidence ledger entry linked to a source."""

    id: str
    source_id: str
    claim: str
    excerpt: str
    uri: str | None = None
    trust_level: TrustLevel = TrustLevel.UNKNOWN
    supports: bool = True
    is_external: bool = False
    untrusted_reason: str | None = None
    metadata: JsonDict = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if self.is_external and self.trust_level is TrustLevel.UNKNOWN:
            object.__setattr__(self, "trust_level", TrustLevel.UNTRUSTED)
        if (
            self.is_external
            and self.trust_level is TrustLevel.UNTRUSTED
            and self.untrusted_reason is None
        ):
            object.__setattr__(
                self,
                "untrusted_reason",
                "External evidence requires review before it can support a decision memo.",
            )

    @property
    def usable_as_evidence(self) -> bool:
        """Return whether this ledger entry can support a formal decision."""

        return self.supports and self.trust_level is TrustLevel.TRUSTED

    def to_dict(self) -> JsonDict:
        """Return a JSON-ready evidence projection."""

        return dataclass_to_dict(self)


@dataclass(frozen=True)
class IntelligenceObject:
    """Read projection for derived intelligence from legacy/source systems."""

    id: str
    title: str
    summary: str
    source_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    metadata: JsonDict = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)

    def to_dict(self) -> JsonDict:
        """Return a JSON-ready intelligence object."""

        return dataclass_to_dict(self)


@dataclass(frozen=True)
class KnowledgeSettings:
    """Read-only operational settings for the knowledge adapter."""

    formal_writes_enabled: bool = False
    pending_review_required: bool = True
    ai_generated_formal_writes_enabled: bool = False
    reflection_formal_writes_enabled: bool = False
    external_sources_default_trust: TrustLevel = TrustLevel.UNTRUSTED

    def to_dict(self) -> JsonDict:
        """Return JSON-ready settings."""

        return dataclass_to_dict(self)


@dataclass(frozen=True)
class KnowledgeItem:
    """Knowledge item schema.

    AI-generated and reflection items must remain pending review and cannot be
    represented as approved formal knowledge by this service layer.
    """

    id: str
    title: str
    body: str
    kind: KnowledgeItemKind
    status: ReviewStatus = ReviewStatus.PENDING_REVIEW
    source_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    submitted_by: str = "system"
    generated_by_ai: bool = False
    metadata: JsonDict = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        restricted = self.generated_by_ai or self.kind in {
            KnowledgeItemKind.AI_GENERATED,
            KnowledgeItemKind.REFLECTION,
        }
        if restricted and self.status is ReviewStatus.APPROVED:
            raise ValueError(
                "AI-generated and reflection knowledge must remain pending review."
            )

    @property
    def can_enter_formal_knowledge(self) -> bool:
        """Return whether the item is eligible for formal knowledge storage."""

        if self.generated_by_ai:
            return False
        if self.kind in {KnowledgeItemKind.AI_GENERATED, KnowledgeItemKind.REFLECTION}:
            return False
        return self.status is ReviewStatus.APPROVED

    def to_dict(self) -> JsonDict:
        """Return a JSON-ready knowledge item."""

        return dataclass_to_dict(self)


@dataclass(frozen=True)
class KnowledgeWriteRequest:
    """Request schema for pending knowledge writes."""

    title: str
    body: str
    kind: KnowledgeItemKind = KnowledgeItemKind.CAPTURE
    source_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    submitted_by: str = "system"
    generated_by_ai: bool = False
    reason: str = "capture"
    metadata: JsonDict = field(default_factory=dict)


@dataclass(frozen=True)
class PendingKnowledgeWrite:
    """Pending review queue item for knowledge writes."""

    id: str
    item: KnowledgeItem
    reason: str
    submitted_by: str
    status: ReviewStatus = ReviewStatus.PENDING_REVIEW
    created_at: datetime = field(default_factory=utc_now)
    closed_at: datetime | None = None
    closed_reason: str | None = None

    def __post_init__(self) -> None:
        if self.item.status is not ReviewStatus.PENDING_REVIEW:
            raise ValueError("Pending writes can only contain pending review items.")
        if self.item.can_enter_formal_knowledge:
            raise ValueError("Pending writes must not contain formal knowledge items.")

    def to_dict(self) -> JsonDict:
        """Return a JSON-ready pending write."""

        return dataclass_to_dict(self)
