from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


AnswerType = Literal[
    "direct_answer",
    "insufficient_evidence",
    "clarification_needed",
    "safety_blocked",
    "approval_required",
]


class QuestionAnalysis(BaseModel):
    original_question: str
    normalized_question: str
    question_type: str = "direct"
    primary_domain: str | None = None
    domains: list[str] = Field(default_factory=list)
    is_multi_hop: bool = False
    needs_clarification: bool = False
    clarification_question: str | None = None
    requires_data_tool: bool = False
    data_tool_reason: str | None = None
    risk_flags: list[str] = Field(default_factory=list)
    route_reason: str = ""


class QAPlanStep(BaseModel):
    step_id: str
    question: str
    domain: str | None = None
    top_k: int = 5
    required_evidence: int = 1
    query_variants: list[str] = Field(default_factory=list)


class QAPlan(BaseModel):
    strategy: str
    allow_data_tool: bool = False
    steps: list[QAPlanStep] = Field(default_factory=list)
    output_requirements: list[str] = Field(default_factory=list)


class EvidenceItem(BaseModel):
    title: str = ""
    snippet: str | None = None
    document_id: str | None = None
    chunk_id: str | None = None
    score: float | None = None
    domain: str | None = None
    query: str = ""
    prompt_injection_flags: list[str] = Field(default_factory=list)
    blocked: bool = False


class SubquestionEvidence(BaseModel):
    step_id: str
    question: str
    domain: str | None = None
    queries: list[str] = Field(default_factory=list)
    answer: str = ""
    items: list[EvidenceItem] = Field(default_factory=list)
    blocked_items: list[EvidenceItem] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class EvidenceReport(BaseModel):
    subquestions: list[SubquestionEvidence] = Field(default_factory=list)
    usable_evidence_count: int = 0
    total_sources: int = 0
    blocked_source_count: int = 0
    prompt_injection_count: int = 0
    coverage: float = 0.0


class VerificationReport(BaseModel):
    status: str
    answer_type: AnswerType
    confidence: float = Field(ge=0, le=1)
    supported_step_count: int = 0
    total_step_count: int = 0
    missing_evidence: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    citation_coverage: float = 0.0


class ComposedAnswer(BaseModel):
    answer_type: AnswerType
    final_answer: str
    confidence: float = Field(ge=0, le=1)
    limitations: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
