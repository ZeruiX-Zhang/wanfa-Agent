from __future__ import annotations

from fastapi import APIRouter, Depends

from platform_common.auth import require_auth
from platform_common.models import AuthContext, HealthResponse, RagQueryRequest, RagQueryResponse, SourceRef
from rag_core.rag.service import RequestContext, rag_service
from rag_core.rag.ingestion import load_local_documents


public_router = APIRouter(tags=["Deprecated RAG"])
rag_router = APIRouter(tags=["Deprecated RAG"])


def _sources(payload: list[dict]) -> list[SourceRef]:
    return [
        SourceRef(
            title=str(item.get("title") or item.get("source") or item.get("document_id") or "source"),
            snippet=item.get("text"),
            document_id=item.get("document_id"),
            chunk_id=item.get("chunk_id"),
            score=float(item["score"]) if item.get("score") is not None else None,
            domain=item.get("domain"),
        )
        for item in payload
    ]


@public_router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="rag-core-compat",
        version="compat",
        trace_store="storage/traces/rag_compat.jsonl",
    )


@rag_router.post("/rag/query", response_model=RagQueryResponse)
def query(request: RagQueryRequest, auth: AuthContext = Depends(require_auth)) -> RagQueryResponse:
    payload = rag_service.query(
        query=request.question,
        top_k=request.top_k,
        domain=None if request.domain == "auto" else request.domain,
        context=RequestContext(user_id=auth.user_id, tenant_id=auth.tenant_id, roles=auth.roles),
    )
    return RagQueryResponse(
        run_id=payload.get("debug", {}).get("trace_id", "rag-compat"),
        trace_id=payload.get("debug", {}).get("trace_id", "rag-compat"),
        answer=str(payload.get("answer") or ""),
        sources=_sources(payload.get("sources", [])),
        trace_url=None,
        safety={},
        debug=payload.get("debug", {}),
    )


@rag_router.post("/rag/ingest/local")
def ingest_local(directory: str, domain: str = "enterprise_kb") -> dict[str, int]:
    chunks = load_local_documents(
        raw_path=directory,
        tenant_id="compat",
        access_roles=["reader"],
        domain=domain,
    )
    return rag_service.ingest_chunks(chunks, replace=False)
