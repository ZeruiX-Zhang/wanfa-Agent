from __future__ import annotations

from typing import Any

from guardrails.service import GuardrailService
from platform_common.models import ApprovalRequest, AuthContext, UnifiedRunRequest
from platform_common.traces import UnifiedTraceStore
from workflow_core.unified_service import approve_unified_run, run_unified_agent


def _request_value(request: Any, name: str, default: Any = None) -> Any:
    if hasattr(request, name):
        return getattr(request, name)
    if isinstance(request, dict):
        return request.get(name, default)
    return default


def run_agent(request: Any, store: UnifiedTraceStore | None = None):
    unified_request = UnifiedRunRequest(
        user_input=_request_value(request, "user_input", ""),
        mode=_request_value(request, "mode", "auto"),
        include_trace=_request_value(request, "include_trace", True),
        max_steps=_request_value(request, "max_steps", 6),
    )
    auth = AuthContext(
        user_id="compat-user",
        tenant_id="compat",
        roles=["employee", "support", "finance", "ops", "analyst", "manager"],
    )
    return run_unified_agent(
        unified_request,
        auth_context=auth,
        trace_store=store or UnifiedTraceStore(),
        guardrail_service=GuardrailService(),
    )


def approve_run(run_id: str, request: Any, store: UnifiedTraceStore | None = None):
    approval_request = ApprovalRequest(
        approved=bool(_request_value(request, "approved", True)),
        comment=_request_value(request, "comment"),
    )
    return approve_unified_run(
        run_id,
        approval_request,
        trace_store=store or UnifiedTraceStore(),
        guardrail_service=GuardrailService(),
    )
