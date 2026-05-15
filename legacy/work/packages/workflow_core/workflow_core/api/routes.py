from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from guardrails.service import GuardrailService
from platform_common.auth import require_auth
from platform_common.models import ApprovalRequest, ApprovalResponse, AuthContext, HealthResponse, UnifiedRunRequest, UnifiedRunResponse, UnifiedRunTrace
from platform_common.traces import UnifiedTraceStore
from workflow_core.unified_service import approve_unified_run, run_unified_agent


public_router = APIRouter(tags=["Deprecated Workflow"])
agent_router = APIRouter(prefix="/agent", tags=["Deprecated Workflow"])
trace_store = UnifiedTraceStore()
guardrails = GuardrailService()


@public_router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="workflow-core-compat",
        version="compat",
        trace_store=str(trace_store.path),
    )


@agent_router.post("/run", response_model=UnifiedRunResponse)
def run_agent(request: UnifiedRunRequest, auth: AuthContext = Depends(require_auth)) -> UnifiedRunResponse:
    return run_unified_agent(request, auth_context=auth, trace_store=trace_store, guardrail_service=guardrails)


@agent_router.post("/approve/{run_id}", response_model=ApprovalResponse)
def approve_agent(
    run_id: str,
    request: ApprovalRequest,
    auth: AuthContext = Depends(require_auth),
) -> ApprovalResponse:
    del auth
    result = approve_unified_run(run_id, request, trace_store=trace_store, guardrail_service=guardrails)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run_id not found")
    return result


@agent_router.get("/runs/{run_id}", response_model=UnifiedRunTrace)
def get_run(run_id: str, auth: AuthContext = Depends(require_auth)) -> UnifiedRunTrace:
    del auth
    trace = trace_store.get(run_id)
    if trace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run_id not found")
    return trace
