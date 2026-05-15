from __future__ import annotations

from typing import Any

from guardrails.service import GuardrailService, GuardrailViolation
from platform_common.models import (
    ApprovalRequest,
    ApprovalResponse,
    AuthContext,
    PendingAction,
    RunStep,
    SourceRef,
    UnifiedRunRequest,
    UnifiedRunResponse,
    UnifiedRunTrace,
)
from platform_common.traces import UnifiedTraceStore, new_trace_id
from workflow_core.router.scenario_router import classify_intent, classify_scenario
from workflow_core.runtime_context import workflow_session
from workflow_core.schemas.agent import Source, ToolStep
from workflow_core.qa.orchestrator import run_qa_orchestrator
from workflow_core.tools.notification_tool import notify_human_agent
from workflow_core.tools.ticket_tool import create_ticket
from workflow_core.workflows.customer_support import run_customer_support_workflow
from workflow_core.workflows.finance_research import run_finance_research_workflow
from workflow_core.workflows.ops_runbook import run_ops_runbook_workflow
from workflow_core.workflows.runtime import StepLimitExceeded, WorkflowRuntime
from workflow_core.workflows.types import WorkflowOutcome


def _trace_url(run_id: str) -> str:
    return f"/api/v1/runs/{run_id}"


def _to_source_refs(sources: list[Source]) -> list[SourceRef]:
    return [
        SourceRef(
            title=source.title,
            snippet=source.snippet,
            url=source.url,
            document_id=source.document_id,
            chunk_id=source.chunk_id,
            score=source.score,
        )
        for source in sources
    ]


def _to_steps(tool_steps: list[ToolStep]) -> list[RunStep]:
    return [
        RunStep(
            name=step.name,
            status=step.status,
            args=step.args,
            result=step.result,
            error=step.error,
            started_at=step.started_at,
            ended_at=step.ended_at,
        )
        for step in tool_steps
    ]


def _to_pending_action(action: Any | None) -> PendingAction | None:
    if action is None:
        return None
    return PendingAction(tool=action.tool, args=action.args, reason=action.reason)


def _guardrail_safety(guardrails: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "guardrails": guardrails,
        "tool_whitelist_enabled": True,
        "write_tools_require_approval": ["create_ticket", "notify_human_agent"],
        "shell_execution_allowed": False,
    }


def _build_trace(
    *,
    request: UnifiedRunRequest,
    auth_context: AuthContext,
    run_id: str,
    trace_id: str,
    scenario: str,
    mode: str,
    outcome: WorkflowOutcome,
    runtime: WorkflowRuntime,
    guardrails: list[dict[str, Any]],
    metadata: dict[str, Any] | None = None,
) -> UnifiedRunTrace:
    return UnifiedRunTrace(
        run_id=run_id,
        trace_id=trace_id,
        user_input=request.user_input,
        scenario=scenario,
        mode=mode,
        status=outcome.status,
        final_answer=outcome.final_answer,
        answer_type=outcome.answer_type,
        confidence=outcome.confidence,
        auth_context=auth_context,
        sources=_to_source_refs(outcome.sources),
        data_artifacts=outcome.data_artifacts,
        pending_action=_to_pending_action(outcome.pending_action),
        tool_steps=_to_steps(runtime.tool_steps),
        guardrails=guardrails,
        safety=_guardrail_safety(guardrails),
        qa_plan=outcome.qa_plan,
        evidence_report=outcome.evidence_report,
        verification=outcome.verification,
        metadata=metadata or outcome.metadata,
    )


def _response_from_trace(trace: UnifiedRunTrace) -> UnifiedRunResponse:
    return UnifiedRunResponse(
        run_id=trace.run_id,
        trace_id=trace.trace_id,
        status=trace.status,
        scenario=trace.scenario,
        mode=trace.mode,
        final_answer=trace.final_answer,
        answer_type=trace.answer_type,
        confidence=trace.confidence,
        sources=trace.sources,
        data_artifacts=trace.data_artifacts,
        pending_action=trace.pending_action,
        trace_url=_trace_url(trace.run_id),
        safety=trace.safety,
        tool_steps=trace.tool_steps,
        qa_plan=trace.qa_plan,
        evidence_report=trace.evidence_report,
        verification=trace.verification,
    )


def _blocked_outcome(message: str, mode: str) -> WorkflowOutcome:
    return WorkflowOutcome(final_answer=message, status="rejected", mode=mode, answer_type="safety_blocked", confidence=0.0)


def _unknown_outcome(mode: str) -> WorkflowOutcome:
    return WorkflowOutcome(
        final_answer="The request did not match a supported workflow scenario.",
        status="completed",
        mode=mode,
        answer_type="insufficient_evidence",
        confidence=0.0,
    )


def run_unified_agent(
    request: UnifiedRunRequest,
    auth_context: AuthContext,
    trace_store: UnifiedTraceStore | None = None,
    guardrail_service: GuardrailService | None = None,
) -> UnifiedRunResponse:
    store = trace_store or UnifiedTraceStore()
    guardrails = guardrail_service or GuardrailService()
    run_id = new_trace_id("run")
    trace_id = new_trace_id("trace")
    runtime = WorkflowRuntime(max_steps=request.max_steps)
    request_decision = guardrails.check_request(request.user_input)
    decisions = [request_decision.model_dump()]
    if request_decision.decision == "block":
        outcome = _blocked_outcome(request_decision.reason, request.mode)
        trace = _build_trace(
            request=request,
            auth_context=auth_context,
            run_id=run_id,
            trace_id=trace_id,
            scenario="unsafe_request",
            mode=request.mode,
            outcome=outcome,
            runtime=runtime,
            guardrails=decisions,
        )
        store.save(trace)
        return _response_from_trace(trace)

    def tool_guard(tool_name: str, args: dict[str, Any]) -> None:
        decision = guardrails.check_tool_call(tool_name, args)
        decisions.append(decision.model_dump())
        if decision.decision == "block":
            raise GuardrailViolation(decision)

    scenario_result = None
    intent_result = None
    actual_mode = request.mode
    outcome = _unknown_outcome(request.mode)
    with workflow_session(auth_context=auth_context, run_mode=request.mode, tool_guard=tool_guard):
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
            scenario = scenario_result.scenario
            if scenario == "finance_research" and request.mode in {"analysis", "hybrid"}:
                outcome = run_finance_research_workflow(request.user_input, intent_result, runtime)
            elif scenario in {"customer_support", "ops_runbook", "finance_research"}:
                outcome = run_qa_orchestrator(
                    user_input=request.user_input,
                    scenario=scenario,
                    intent_result=intent_result,
                    mode=request.mode,
                    runtime=runtime,
                    guardrail_service=guardrails,
                    guardrail_decisions=decisions,
                )
            elif scenario == "unsafe_request":
                outcome = _blocked_outcome("The request was blocked by workflow safety policies.", request.mode)
            elif request.mode in {"analysis", "hybrid"}:
                scenario = "finance_research"
                outcome = run_finance_research_workflow(request.user_input, intent_result, runtime)
            elif scenario == "unknown":
                outcome = run_qa_orchestrator(
                    user_input=request.user_input,
                    scenario=scenario,
                    intent_result=intent_result,
                    mode=request.mode,
                    runtime=runtime,
                    guardrail_service=guardrails,
                    guardrail_decisions=decisions,
                )
            else:
                outcome = _unknown_outcome(request.mode)
            actual_mode = outcome.mode
        except GuardrailViolation as exc:
            decisions.append(exc.decision.model_dump())
            outcome = _blocked_outcome(exc.decision.reason, request.mode)
        except StepLimitExceeded as exc:
            outcome = WorkflowOutcome(final_answer=str(exc), status="error", mode=request.mode)
        except Exception as exc:  # pragma: no cover
            outcome = WorkflowOutcome(final_answer=f"workflow execution failed: {exc}", status="error", mode=request.mode)

    output_decision, sanitized_answer = guardrails.check_output(outcome.final_answer)
    decisions.append(output_decision.model_dump())
    outcome.final_answer = sanitized_answer
    trace = _build_trace(
        request=request,
        auth_context=auth_context,
        run_id=run_id,
        trace_id=trace_id,
        scenario=(scenario_result.scenario if scenario_result else "unknown"),
        mode=actual_mode,
        outcome=outcome,
        runtime=runtime,
        guardrails=decisions,
        metadata={"intent": intent_result.intent if intent_result else "unknown", **outcome.metadata},
    )
    store.save(trace)
    return _response_from_trace(trace)


def approve_unified_run(
    run_id: str,
    request: ApprovalRequest,
    trace_store: UnifiedTraceStore | None = None,
    guardrail_service: GuardrailService | None = None,
) -> ApprovalResponse | None:
    store = trace_store or UnifiedTraceStore()
    trace = store.get(run_id)
    if trace is None:
        return None
    if trace.pending_action is None:
        return ApprovalResponse(
            run_id=run_id,
            status=trace.status,
            approval_executed=False,
            pending_action=None,
            final_answer="No pending action exists for this run.",
            trace_url=_trace_url(run_id),
        )
    if not request.approved:
        trace.status = "rejected"
        trace.final_answer = f"Approval rejected: {request.comment or 'no comment'}"
        trace.pending_action = None
        store.save(trace)
        return ApprovalResponse(
            run_id=run_id,
            status=trace.status,
            approval_executed=False,
            pending_action=None,
            final_answer=trace.final_answer,
            trace_url=_trace_url(run_id),
        )

    pending_action = trace.pending_action
    guardrails = guardrail_service or GuardrailService()
    decision = guardrails.check_tool_call(pending_action.tool, pending_action.args)
    if decision.decision == "block":
        trace.status = "rejected"
        trace.final_answer = decision.reason
        trace.pending_action = None
        store.save(trace)
        return ApprovalResponse(
            run_id=run_id,
            status=trace.status,
            approval_executed=False,
            pending_action=None,
            final_answer=trace.final_answer,
            trace_url=_trace_url(run_id),
        )

    ticket_id = None
    if pending_action.tool == "create_ticket":
        ticket = create_ticket(**pending_action.args)
        ticket_id = ticket.ticket_id
        message = f"Approval executed. Ticket created: {ticket.ticket_id}"
    elif pending_action.tool == "notify_human_agent":
        ticket = notify_human_agent(**pending_action.args)
        ticket_id = ticket.ticket_id
        message = f"Approval executed. Notification created: {ticket.ticket_id}"
    else:
        message = f"Unknown pending action tool: {pending_action.tool}"

    trace.status = "completed" if ticket_id else "error"
    trace.final_answer = message
    trace.pending_action = None
    trace.tool_steps.append(
        RunStep(
            name=pending_action.tool,
            status="success" if ticket_id else "error",
            args=pending_action.args,
            result={"ticket_id": ticket_id} if ticket_id else None,
            error=None if ticket_id else message,
        )
    )
    store.save(trace)
    return ApprovalResponse(
        run_id=run_id,
        status=trace.status,
        approval_executed=bool(ticket_id),
        pending_action=None,
        final_answer=trace.final_answer,
        trace_url=_trace_url(run_id),
        ticket_id=ticket_id,
    )
