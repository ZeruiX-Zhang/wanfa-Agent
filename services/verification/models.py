"""Dataclasses for verification adapter payloads."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class EvidenceState(str, Enum):
    """Verification states used by claim and evidence checks."""

    SUPPORTED = "supported"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    UNVERIFIABLE = "unverifiable"
    CONFLICTED = "conflicted"


@dataclass(frozen=True)
class Claim:
    """A checkable statement extracted from a memo or supplied directly."""

    id: str
    text: str
    source: str = "memo"

    def to_dict(self) -> dict[str, str]:
        """Return a JSON-safe representation."""

        return {"id": self.id, "text": self.text, "source": self.source}


@dataclass(frozen=True)
class Evidence:
    """A projected evidence item from retrieval or a safe fixture."""

    id: str
    title: str
    snippet: str
    source_uri: str | None = None
    source_type: str = "retrieval"
    trust: str = "untrusted"
    score: float | None = None

    def to_dict(self) -> dict[str, str | float | None]:
        """Return a JSON-safe representation."""

        return {
            "id": self.id,
            "title": self.title,
            "snippet": self.snippet,
            "source_uri": self.source_uri,
            "source_type": self.source_type,
            "trust": self.trust,
            "score": self.score,
        }


@dataclass(frozen=True)
class EvidenceBinding:
    """A deterministic binding between a claim and one evidence item."""

    claim_id: str
    evidence_id: str
    state: EvidenceState
    relevance: float
    rationale: str
    matched_terms: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, str | float | list[str]]:
        """Return a JSON-safe representation."""

        return {
            "claim_id": self.claim_id,
            "evidence_id": self.evidence_id,
            "state": self.state.value,
            "relevance": self.relevance,
            "rationale": self.rationale,
            "matched_terms": list(self.matched_terms),
        }


@dataclass(frozen=True)
class ConfidenceScore:
    """Confidence attached to a verified claim."""

    claim_id: str
    state: EvidenceState
    score: float
    rationale: str

    def to_dict(self) -> dict[str, str | float]:
        """Return a JSON-safe representation."""

        return {
            "claim_id": self.claim_id,
            "state": self.state.value,
            "score": self.score,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class TraceStep:
    """A normalized RAG/debug trace step."""

    name: str
    status: str
    detail: str = ""
    metadata: dict[str, str | int | float | bool | None] = field(default_factory=dict)

    def to_dict(self) -> dict[str, str | dict[str, str | int | float | bool | None]]:
        """Return a JSON-safe representation."""

        return {
            "name": self.name,
            "status": self.status,
            "detail": self.detail,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class RagDebugTrace:
    """Read-only projection of a retrieval pipeline trace."""

    query: str
    retrieval_count: int
    top_evidence_ids: tuple[str, ...] = field(default_factory=tuple)
    steps: tuple[TraceStep, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, str | int | list[str] | list[dict[str, object]]]:
        """Return a JSON-safe representation."""

        return {
            "query": self.query,
            "retrieval_count": self.retrieval_count,
            "top_evidence_ids": list(self.top_evidence_ids),
            "steps": [step.to_dict() for step in self.steps],
        }


@dataclass(frozen=True)
class VerificationReport:
    """Verification result for a memo or a list of claims."""

    claims: tuple[Claim, ...]
    evidence: tuple[Evidence, ...]
    bindings: tuple[EvidenceBinding, ...]
    confidence: tuple[ConfidenceScore, ...]
    overall_state: EvidenceState
    overall_confidence: float
    warnings: tuple[str, ...] = field(default_factory=tuple)
    trace: RagDebugTrace | None = None

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe representation."""

        return {
            "claims": [claim.to_dict() for claim in self.claims],
            "evidence": [item.to_dict() for item in self.evidence],
            "bindings": [binding.to_dict() for binding in self.bindings],
            "confidence": [score.to_dict() for score in self.confidence],
            "overall_state": self.overall_state.value,
            "overall_confidence": self.overall_confidence,
            "warnings": list(self.warnings),
            "trace": self.trace.to_dict() if self.trace else None,
        }
