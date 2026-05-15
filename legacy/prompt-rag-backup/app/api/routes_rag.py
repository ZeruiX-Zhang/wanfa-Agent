from __future__ import annotations

from fastapi import APIRouter, Request

from app.rag.rag_service import RAGService
from app.schemas.rag import RAGDebugResponse, RAGQueryRequest, RAGQueryResponse

router = APIRouter(prefix="/rag", tags=["RAG \u95ee\u7b54"])


@router.post(
    "/query",
    response_model=RAGQueryResponse,
    summary="RAG \u77e5\u8bc6\u5e93\u95ee\u7b54",
    description="\u6839\u636e\u7528\u6237\u95ee\u9898\u68c0\u7d22\u76f8\u5173 chunks\uff0c\u5e76\u8c03\u7528 LLM \u57fa\u4e8e context \u751f\u6210\u7b54\u6848\u3002",
)
def query(payload: RAGQueryRequest, request: Request) -> RAGQueryResponse:
    return RAGService().query(
        question=payload.question,
        domain=payload.domain,
        top_k=payload.top_k,
        trace_id=request.state.trace_id,
    )


@router.post(
    "/debug",
    response_model=RAGDebugResponse,
    summary="RAG Debug \u8c03\u8bd5",
    description="\u8fd4\u56de\u68c0\u7d22\u5230\u7684 chunks\u3001\u5b8c\u6574 prompt \u548c\u68c0\u7d22/LLM \u8017\u65f6\uff0c\u7528\u4e8e\u6392\u67e5 RAG \u6548\u679c\u3002",
)
def debug(payload: RAGQueryRequest, request: Request) -> RAGDebugResponse:
    return RAGService().debug(
        question=payload.question,
        domain=payload.domain,
        top_k=payload.top_k,
        trace_id=request.state.trace_id,
    )
