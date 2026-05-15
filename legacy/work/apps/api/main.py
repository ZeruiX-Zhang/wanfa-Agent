from __future__ import annotations

import time
from pathlib import Path

from fastapi import FastAPI
from fastapi import HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles

from .docs_localization import (
    OPENAPI_INFO,
    OPENAPI_TAGS,
    install_localized_openapi,
    localized_redoc_html,
    localized_swagger_ui_html,
    swagger_oauth_redirect_html,
)
from .rag_routes import router as rag_router
from .routes import router
from .routers.production import router as production_router
from .workbench import router as workbench_router
from platform_common.settings import get_settings
from platform_common.events import log_event
from platform_common.rate_limit import check_rate_limit
from platform_common.traces import new_trace_id


settings = get_settings()

app = FastAPI(
    title=OPENAPI_INFO["title"],
    version="1.0.0",
    summary=OPENAPI_INFO["summary"],
    description=OPENAPI_INFO["description"],
    openapi_tags=OPENAPI_TAGS,
    docs_url=None,
    redoc_url=None,
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(rag_router)
app.include_router(production_router)
app.include_router(workbench_router)

static_dir = Path(__file__).resolve().parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

install_localized_openapi(app)


@app.middleware("http")
async def request_observability_middleware(request: Request, call_next):
    started = time.perf_counter()
    trace_id = request.headers.get("X-Trace-Id") or new_trace_id("trace")
    request.state.trace_id = trace_id
    client_host = request.client.host if request.client else "unknown"
    check_rate_limit(client_host)
    try:
        response = await call_next(request)
        return response
    finally:
        log_event(
            {
                "trace_id": trace_id,
                "endpoint": request.url.path,
                "method": request.method,
                "latency_ms": round((time.perf_counter() - started) * 1000, 3),
            }
        )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail)}
    trace_id = getattr(request.state, "trace_id", None)
    payload = {
        "error_code": detail.get("error_code") or detail.get("code") or "http_error",
        "message": detail.get("message") or str(exc.detail),
        "detail": detail.get("detail"),
        "trace_id": trace_id,
        "suggestion": detail.get("suggestion"),
    }
    return JSONResponse(status_code=exc.status_code, content=payload)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error_code": "validation_error",
            "message": "Request validation failed.",
            "detail": exc.errors(),
            "trace_id": getattr(request.state, "trace_id", None),
            "suggestion": "Check request JSON fields and types.",
        },
    )


@app.get("/docs", include_in_schema=False)
def custom_docs() -> HTMLResponse:
    return localized_swagger_ui_html(app)


@app.get(app.swagger_ui_oauth2_redirect_url, include_in_schema=False)
def swagger_redirect() -> HTMLResponse:
    return swagger_oauth_redirect_html()


@app.get("/redoc", include_in_schema=False)
def custom_redoc() -> HTMLResponse:
    return localized_redoc_html(app)
