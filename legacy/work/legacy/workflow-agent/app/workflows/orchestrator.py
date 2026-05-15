from __future__ import annotations

import uuid

from app.router.scenario_router import classify_intent, classify_scenario
from app.schemas.agent import (
    AgentApproveRequest,
    AgentApproveResponse,
    AgentRunRequest,
    AgentRunResponse,
    AgentTrace,
    IntentResult,
    PendingAction,
    ScenarioRouteResult,
)
from app.tools.notification_tool import notify_human_agent
from app.tools.summary_tool import summarize_workflow_result
from app.tools.ticket_tool import create_ticket
from app.trace.store import TraceStore
from app.workflows.customer_support import run_customer_support_workflow
from app.workflows.finance_research import run_finance_research_workflow
from app.workflows.ops_runbook import run_ops_runbook_workflow
from app.workflows.runtime import StepLimitExceeded, WorkflowRuntime
from app.workflows.types import WorkflowOutcome


def _trace_url(run_id: str) -> str:
    return f"/agent/runs/{run_id}"


def _response_from_trace(trace: AgentTrace) -> AgentRunResponse:
    return AgentRunResponse(
        run_id=trace.run_id,
        status=trace.status,
        scenario=trace.scenario,
        intent=trace.intent,
        approval_required=trace.approval_required,
        pending_action=trace.pending_action,
        final_answer=trace.final_answer,
        sources=trace.sources,
        tool_steps=trace.tool_steps,
        trace_url=_trace_url(trace.run_id),
    )


def _build_trace(
    request: AgentRunRequest,
    runtime: WorkflowRuntime,
    scenario_result: ScenarioRouteResult,
    intent_result: IntentResult,
    outcome: WorkflowOutcome,
) -> AgentTrace:
    return AgentTrace(
        run_id=f"run_{uuid.uuid4().hex[:12]}",
        user_input=request.user_input,
        scenario=scenario_result.scenario,
        intent=intent_result.intent,
        status=outcome.status,
        approval_required=bool(outcome.pending_action),
        pending_action=outcome.pending_action,
        final_answer=outcome.final_answer,
        sources=outcome.sources,
        tool_steps=runtime.tool_steps,
        max_steps=request.max_steps,
        safety={
            "tool_whitelist_enabled": True,
            "write_tools_require_approval": ["create_ticket", "notify_human_agent"],
            "shell_execution_allowed": False,
        },
    )


def run_agent(request: AgentRunRequest, store: TraceStore | None = None) -> AgentRunResponse:
    trace_store = store or TraceStore()
    runtime = WorkflowRuntime(max_steps=request.max_steps)
    scenario_result = ScenarioRouteResult(scenario="unknown", confidence=0, reason="")
    intent_result = IntentResult(intent="unknown", confidence=0, reason="")
    try:
        scenario_result = runtime.run_tool(
            "classify_scenario",
            {"user_input": request.user_input},
            lambda: classify_scenario(request.user_input),
        )
        intent_result = runtime.run_tool(
            "classify_intent",
            {"user_input": request.user_input, "scenario": scenario_result.scenario},
            lambda: classify_intent(request.user_input, scenario_result.scenario),
        )

        if scenario_result.scenario == "unsafe_request":
            outcome = WorkflowOutcome(
                final_answer=summarize_workflow_result(
                    scenario="unsafe_request",
                    intent=intent_result.intent,
                    user_input=request.user_input,
                ),
                status="rejected",
            )
        elif scenario_result.scenario == "customer_support":
            outcome = run_customer_support_workflow(request.user_input, intent_result, runtime)
        elif scenario_result.scenario == "finance_research":
            outcome = run_finance_research_workflow(request.user_input, intent_result, runtime)
        elif scenario_result.scenario == "ops_runbook":
            outcome = run_ops_runbook_workflow(request.user_input, intent_result, runtime)
        else:
            outcome = WorkflowOutcome(
                final_answer="当前请求不属于已支持的客服、金融投研或运维场景，无法进入可靠 workflow。",
                status="completed",
            )
    except StepLimitExceeded as exc:
        outcome = WorkflowOutcome(final_answer=str(exc), status="error")
    except Exception as exc:
        outcome = WorkflowOutcome(final_answer=f"workflow 执行失败: {exc}", status="error")

    trace = _build_trace(request, runtime, scenario_result, intent_result, outcome)
    trace_store.save(trace)
    return _response_from_trace(trace)


def approve_run(
    run_id: str,
    request: AgentApproveRequest,
    store: TraceStore | None = None,
) -> AgentApproveResponse | None:
    trace_store = store or TraceStore()
    trace = trace_store.get(run_id)
    if not trace:
        return None
    if not trace.pending_action:
        return AgentApproveResponse(
            run_id=run_id,
            status=trace.status,
            approval_executed=False,
            pending_action=None,
            final_answer="当前 run 没有待审批动作。",
        )
    if not request.approved:
        trace.status = "rejected"
        trace.approval_required = False
        trace.final_answer = f"人工审批已拒绝：{request.comment or '无备注'}"
        trace.pending_action = None
        trace_store.save(trace)
        return AgentApproveResponse(
            run_id=run_id,
            status=trace.status,
            approval_executed=False,
            pending_action=None,
            final_answer=trace.final_answer,
        )

    action: PendingAction = trace.pending_action
    runtime = WorkflowRuntime(max_steps=max(trace.max_steps, len(trace.tool_steps) + 1))
    runtime.tool_steps = list(trace.tool_steps)
    ticket_id: str | None = None
    if action.tool == "create_ticket":
        ticket = runtime.run_tool(action.tool, action.args, lambda: create_ticket(**action.args))
        ticket_id = ticket.ticket_id
        result_message = f"审批通过，已创建工单 {ticket.ticket_id}。"
    elif action.tool == "notify_human_agent":
        ticket = runtime.run_tool(action.tool, action.args, lambda: notify_human_agent(**action.args))
        ticket_id = ticket.ticket_id
        result_message = f"审批通过，已发送 mock 通知 {ticket.ticket_id}。"
    else:
        trace.status = "error"
        result_message = f"待审批工具不在写操作白名单内: {action.tool}"

    trace.tool_steps = runtime.tool_steps
    trace.status = "completed" if ticket_id else "error"
    trace.approval_required = False
    trace.pending_action = None
    trace.final_answer = result_message
    trace_store.save(trace)
    return AgentApproveResponse(
        run_id=run_id,
        status=trace.status,
        approval_executed=bool(ticket_id),
        pending_action=None,
        final_answer=trace.final_answer,
        ticket_id=ticket_id,
    )

