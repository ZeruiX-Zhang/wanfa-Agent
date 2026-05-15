from __future__ import annotations

from fastapi import APIRouter, Request

from app.agent.agent_runner import AgentRunner
from app.agent.trace_store import TraceStore
from app.schemas.agent import AgentRunRequest, AgentRunResponse, AgentTraceResponse

router = APIRouter(prefix="/agent", tags=["\u5de5\u4f5c\u6d41 Agent"])


@router.post(
    "/run",
    response_model=AgentRunResponse,
    summary="\u8fd0\u884c Agent",
    description="\u6839\u636e\u7528\u6237\u8f93\u5165\u4f7f\u7528\u89c4\u5219\u8def\u7531\u9009\u62e9\u767d\u540d\u5355\u5de5\u5177\uff0c\u6267\u884c\u540e\u751f\u6210\u6700\u7ec8\u56de\u7b54\u548c trace\u3002",
)
def run_agent(payload: AgentRunRequest, request: Request) -> AgentRunResponse:
    return AgentRunner().run(user_input=payload.user_input, max_steps=payload.max_steps, trace_id=request.state.trace_id)


@router.get(
    "/runs/{run_id}",
    response_model=AgentTraceResponse,
    summary="\u67e5\u770b Agent Trace",
    description="\u6839\u636e run_id \u8bfb\u53d6 storage/traces \u4e2d\u7684 Agent \u6267\u884c\u8bb0\u5f55\u3002",
)
def get_agent_run(run_id: str, request: Request) -> AgentTraceResponse:
    trace = TraceStore().get(run_id)
    return AgentTraceResponse(success=True, run=trace, trace_id=request.state.trace_id)
