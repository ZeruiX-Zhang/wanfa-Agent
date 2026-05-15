from __future__ import annotations

from fastapi import APIRouter, Request

from app.rag.ingestion_service import DocumentIngestionService
from app.schemas.documents import IngestLocalRequest, IngestLocalResponse

router = APIRouter(prefix="/documents", tags=["\u6587\u6863\u5904\u7406"])


@router.post(
    "/ingest-local",
    response_model=IngestLocalResponse,
    summary="\u5bfc\u5165\u672c\u5730\u6587\u6863",
    description="\u8bfb\u53d6 data/raw \u4e0b\u7684 md/txt/pdf/csv \u6587\u6863\uff0c\u6e05\u6d17\u540e\u5207\u5757\uff0c\u53ef\u9009\u6784\u5efa FAISS \u7d22\u5f15\u3002",
)
def ingest_local(payload: IngestLocalRequest, request: Request) -> IngestLocalResponse:
    service = DocumentIngestionService()
    result = service.ingest_local(
        domain=payload.domain,
        directory=payload.directory,
        glob_pattern=payload.glob_pattern,
        build_index=payload.build_index,
        trace_id=request.state.trace_id,
    )
    return result
