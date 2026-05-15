from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


TrustLevel = Literal["trusted", "untrusted"]
InputStatus = Literal["pending_input", "rejected", "accepted"]
ClarificationStatus = Literal["needs_clarification", "ready_for_retrieval"]


@dataclass(slots=True)
class CaptureSource:
    kind: str = "unknown"
    title: str = ""
    url: str = ""
    content_type: str = "text/plain"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class CapturedInput:
    id: str
    text: str
    source: CaptureSource
    trust_level: TrustLevel = "untrusted"
    status: InputStatus = "pending_input"
    write_policy: str = "pending_review_only"
    captured_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["is_formal_knowledge"] = False
        return data


@dataclass(slots=True)
class ClarifiedProblem:
    id: str
    original_problem: str
    normalized_problem: str
    status: ClarificationStatus
    clarifying_questions: list[str] = field(default_factory=list)
    missing_information: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    ready_for_retrieval: bool = False
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class KnowledgeOSSummary:
    adapter_mode: str
    sources_count: int = 0
    claims_count: int = 0
    pending_inputs_count: int = 0
    review_required_count: int = 0
    summary: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
