from __future__ import annotations

from app.schemas.agent import IntentResult, PendingAction
from app.tools.rag_tool import search_knowledge_base
from app.tools.summary_tool import summarize_workflow_result
from app.workflows.runtime import WorkflowRuntime
from app.workflows.types import WorkflowOutcome


def run_customer_support_workflow(
    user_input: str,
    intent_result: IntentResult,
    runtime: WorkflowRuntime,
) -> WorkflowOutcome:
    rag_result = runtime.run_tool(
        "search_knowledge_base",
        {"question": user_input, "scenario": "customer_support", "top_k": 5},
        lambda: search_knowledge_base(user_input, "customer_support", top_k=5),
    )

    pending_action: PendingAction | None = None
    if intent_result.intent in {"complaint", "create_ticket_request"}:
        pending_action = PendingAction(
            tool="create_ticket",
            reason="创建客服工单属于写操作，需要人工审批。",
            args={
                "title": "客服工单草稿",
                "description": user_input,
                "scenario": "customer_support",
                "severity": "P2",
                "ticket_type": "customer_ticket",
                "metadata": {"intent": intent_result.intent},
            },
        )
    elif intent_result.intent == "handoff_to_human":
        pending_action = PendingAction(
            tool="notify_human_agent",
            reason="通知人工客服属于写操作，需要人工审批。",
            args={
                "target_role": "人工客服",
                "message": user_input,
                "scenario": "customer_support",
                "severity": "P2",
                "metadata": {"intent": intent_result.intent},
            },
        )

    final_answer = runtime.run_tool(
        "summarize_workflow_result",
        {
            "scenario": "customer_support",
            "intent": intent_result.intent,
            "has_rag_error": bool(rag_result.error),
            "pending_action": pending_action.model_dump() if pending_action else None,
        },
        lambda: summarize_workflow_result(
            scenario="customer_support",
            intent=intent_result.intent,
            user_input=user_input,
            rag_result=rag_result,
            pending_action=pending_action,
        ),
    )

    return WorkflowOutcome(
        final_answer=final_answer,
        sources=rag_result.sources,
        pending_action=pending_action,
        status="waiting_approval" if pending_action else "completed",
    )

