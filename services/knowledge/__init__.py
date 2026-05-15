"""Knowledge service-layer adapter exports."""

from services.knowledge.adapter import (
    InMemoryKnowledgeAdapter,
    KnowledgeAdapterError,
    PendingWriteAlreadyClosed,
    PendingWriteNotFound,
)
from services.knowledge.models import (
    EvidenceRecord,
    IntelligenceObject,
    KnowledgeItem,
    KnowledgeItemKind,
    KnowledgeSettings,
    KnowledgeWriteRequest,
    PendingKnowledgeWrite,
    ReviewStatus,
    SourceKind,
    SourceRef,
    TrustLevel,
)

__all__ = [
    "EvidenceRecord",
    "InMemoryKnowledgeAdapter",
    "IntelligenceObject",
    "KnowledgeAdapterError",
    "KnowledgeItem",
    "KnowledgeItemKind",
    "KnowledgeSettings",
    "KnowledgeWriteRequest",
    "PendingKnowledgeWrite",
    "PendingWriteAlreadyClosed",
    "PendingWriteNotFound",
    "ReviewStatus",
    "SourceKind",
    "SourceRef",
    "TrustLevel",
]
