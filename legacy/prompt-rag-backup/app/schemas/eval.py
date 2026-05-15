from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.domain import DomainRequestValue
from app.schemas.rag import RAGSource


class EvalRunRequest(BaseModel):
    eval_file: str = Field(default="data/eval/enterprise_kb_eval.jsonl", min_length=1)
    domain: DomainRequestValue = "auto"
    top_k: int = Field(default=5, ge=1, le=20)


class EvalItemResult(BaseModel):
    question: str
    answer: str
    sources: list[RAGSource]
    expected_source: str
    source_hit: bool
    keyword_hit: bool
    score: float


class EvalRunResponse(BaseModel):
    success: bool
    total: int
    results: list[EvalItemResult]
    average_score: float
    trace_id: str
