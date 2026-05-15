from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.documents import RetrievedChunk
from app.schemas.domain import DomainName, DomainRequestValue


class RAGQueryRequest(BaseModel):
    question: str = Field(min_length=1)
    domain: DomainRequestValue = "auto"
    top_k: int = Field(default=5, ge=1, le=20)


class RAGSource(BaseModel):
    domain: DomainName
    filename: str
    page: int | None = None
    chunk_id: str
    score: float


class RAGQueryResponse(BaseModel):
    success: bool
    answer: str
    sources: list[RAGSource]
    selected_domain: DomainName
    router_confidence: float
    router_reason: str
    latency_ms: float
    trace_id: str


class RAGDebugResponse(RAGQueryResponse):
    retrieved_chunks: list[RetrievedChunk]
    prompt: str
    retrieval_latency_ms: float
    llm_latency_ms: float
