from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes_agent import router as agent_router
from app.api.routes_documents import router as documents_router
from app.api.routes_eval import router as eval_router
from app.api.routes_rag import router as rag_router
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import TraceIdMiddleware
from app.schemas.health import HealthResponse

configure_logging(settings.log_level)

OPENAPI_TAGS = [
    {
        "name": "\u5065\u5eb7\u68c0\u67e5",
        "description": "\u68c0\u67e5 API \u670d\u52a1\u662f\u5426\u6b63\u5e38\u8fd0\u884c\u3002",
    },
    {
        "name": "\u6587\u6863\u5904\u7406",
        "description": "\u672c\u5730\u6587\u6863\u8bfb\u53d6\u3001\u6e05\u6d17\u3001\u5207\u5757\u548c FAISS \u7d22\u5f15\u6784\u5efa\u3002",
    },
    {
        "name": "RAG \u95ee\u7b54",
        "description": "\u57fa\u4e8e\u77e5\u8bc6\u5e93\u68c0\u7d22\u7684\u95ee\u7b54\u548c Debug \u63a5\u53e3\u3002",
    },
    {
        "name": "\u5de5\u4f5c\u6d41 Agent",
        "description": "\u4f01\u4e1a\u843d\u5730\u578b\u5de5\u4f5c\u6d41 Agent\u3001\u5de5\u5177\u8c03\u7528\u548c trace \u67e5\u8be2\u3002",
    },
    {
        "name": "RAG \u8bc4\u6d4b",
        "description": "\u4f7f\u7528 JSONL \u8bc4\u6d4b\u96c6\u8fd0\u884c\u57fa\u7840 RAG \u8bc4\u5206\u3002",
    },
]


class UTF8JSONResponse(JSONResponse):
    media_type = "application/json; charset=utf-8"


app = FastAPI(
    title="\u4f01\u4e1a\u77e5\u8bc6\u5e93 RAG Agent Demo",
    description=(
        "\u4e00\u4e2a\u53ef\u8fd0\u884c\u3001\u53ef\u622a\u56fe\u3001\u53ef\u7528\u4e8e\u9762\u8bd5\u8bb2\u89e3\u7684"
        "\u4f01\u4e1a\u77e5\u8bc6\u5e93 RAG + \u591a\u5de5\u5177 Agent \u6f14\u793a\u9879\u76ee\u3002"
    ),
    version="0.1.0",
    openapi_tags=OPENAPI_TAGS,
    default_response_class=UTF8JSONResponse,
)
app.add_middleware(TraceIdMiddleware)
register_exception_handlers(app)


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["\u5065\u5eb7\u68c0\u67e5"],
    summary="\u5065\u5eb7\u68c0\u67e5",
    description="\u8fd4\u56de\u670d\u52a1\u72b6\u6001\u548c\u5f53\u524d\u8bf7\u6c42\u7684 trace_id\u3002",
)
def health(request: Request) -> HealthResponse:
    return HealthResponse(status="ok", service=settings.app_name, trace_id=request.state.trace_id)


app.include_router(documents_router)
app.include_router(rag_router)
app.include_router(agent_router)
app.include_router(eval_router)
