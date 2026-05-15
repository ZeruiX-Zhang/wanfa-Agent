from __future__ import annotations

from fastapi import APIRouter, Request

from app.rag.eval_service import EvalService
from app.schemas.eval import EvalRunRequest, EvalRunResponse

router = APIRouter(prefix="/eval", tags=["RAG \u8bc4\u6d4b"])


@router.post(
    "/run",
    response_model=EvalRunResponse,
    summary="\u8fd0\u884c RAG \u8bc4\u6d4b",
    description="\u8bfb\u53d6 JSONL \u8bc4\u6d4b\u96c6\uff0c\u6309 expected_source \u548c expected_keywords \u8ba1\u7b97\u7b80\u5355\u8bc4\u5206\u3002",
)
def run_eval(payload: EvalRunRequest, request: Request) -> EvalRunResponse:
    return EvalService().run(
        eval_file=payload.eval_file,
        domain=payload.domain,
        top_k=payload.top_k,
        trace_id=request.state.trace_id,
    )
