from __future__ import annotations

from app.schemas.agent import IntentResult, PendingAction
from app.tools.rag_tool import search_knowledge_base
from app.tools.summary_tool import summarize_workflow_result
from app.workflows.runtime import WorkflowRuntime
from app.workflows.types import WorkflowOutcome


def detect_severity(user_input: str) -> str:
    text = user_input.lower()
    if "p0" in text:
        return "P0"
    if "p1" in text:
        return "P1"
    if "p2" in text:
        return "P2"
    if "pay-502" in text or "e1027" in text or "错误码" in text:
        return "P2"
    return "unknown"


def run_ops_runbook_workflow(
    user_input: str,
    intent_result: IntentResult,
    runtime: WorkflowRuntime,
) -> WorkflowOutcome:
    rag_result = runtime.run_tool(
        "search_knowledge_base",
        {"question": user_input, "scenario": "ops_runbook", "top_k": 5},
        lambda: search_knowledge_base(user_input, "ops_runbook", top_k=5),
    )

    severity = detect_severity(user_input)
    text = user_input.lower()
    pending_action: PendingAction | None = None
    needs_approval = severity in {"P0", "P1"} and (
        intent_result.intent == "incident_escalation"
        or "通知" in text
        or "值班" in text
        or "升级" in text
    )
    if needs_approval and ("通知" in text or "值班" in text):
        pending_action = PendingAction(
            tool="notify_human_agent",
            reason="P0/P1 故障升级通知属于写操作，需要人工审批。",
            args={
                "target_role": "运维值班人员",
                "message": user_input,
                "scenario": "ops_runbook",
                "severity": severity,
                "metadata": {"intent": intent_result.intent},
            },
        )
    elif needs_approval:
        pending_action = PendingAction(
            tool="create_ticket",
            reason="P0/P1 incident 创建属于写操作，需要人工审批。",
            args={
                "title": f"{severity} incident 草稿",
                "description": user_input,
                "scenario": "ops_runbook",
                "severity": severity,
                "ticket_type": "incident_ticket",
                "metadata": {"intent": intent_result.intent},
            },
        )

    final_answer = runtime.run_tool(
        "summarize_workflow_result",
        {
            "scenario": "ops_runbook",
            "intent": intent_result.intent,
            "severity": severity,
            "pending_action": pending_action.model_dump() if pending_action else None,
        },
        lambda: summarize_workflow_result(
            scenario="ops_runbook",
            intent=intent_result.intent,
            user_input=user_input,
            rag_result=rag_result,
            pending_action=pending_action,
            severity=severity,
        ),
    )

    return WorkflowOutcome(
        final_answer=final_answer,
        sources=rag_result.sources,
        pending_action=pending_action,
        status="waiting_approval" if pending_action else "completed",
        severity=severity,
    )

