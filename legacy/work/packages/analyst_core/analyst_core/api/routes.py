from __future__ import annotations

from fastapi import APIRouter, Depends

from analyst_core.core.auth import require_api_key
from analyst_core.core.config import get_settings
from analyst_core.service import run_analysis
from platform_common.models import AnalysisQueryRequest, HealthResponse, UnifiedRunResponse


public_router = APIRouter(tags=["Deprecated Analyst"])
data_agent_router = APIRouter(prefix="/data-agent", tags=["Deprecated Analyst"])


@public_router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service="analyst-core-compat",
        version="compat",
        trace_store=str(settings.trace_path),
    )


@data_agent_router.post("/query", response_model=UnifiedRunResponse)
def query(
    request: AnalysisQueryRequest,
    _api_key: str = Depends(require_api_key),
) -> UnifiedRunResponse:
    result = run_analysis(request.question, include_trace=request.include_trace, enable_internal_trace=False)
    return UnifiedRunResponse(
        run_id=result.run_id,
        trace_id=result.trace_id,
        status="completed" if result.status == "completed" else "failed",
        scenario="data_analysis",
        mode="analysis",
        final_answer=result.final_answer,
        sources=[],
        data_artifacts=result.data_artifacts,
        pending_action=None,
        trace_url=f"/data-agent/runs/{result.run_id}" if request.include_trace else None,
        safety={},
        tool_steps=[],
    )
