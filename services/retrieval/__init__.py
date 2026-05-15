"""Retrieval service-layer adapter exports."""

from services.retrieval.adapter import InMemoryRetrievalAdapter
from services.retrieval.models import (
    EvidenceRole,
    RetrievalQuery,
    RetrievalResult,
    RetrievedEvidence,
)

__all__ = [
    "EvidenceRole",
    "InMemoryRetrievalAdapter",
    "RetrievalQuery",
    "RetrievalResult",
    "RetrievedEvidence",
]
