from __future__ import annotations

from workflow_core.schemas.agent import PendingAction, RAGSearchResult


def _format_sources(rag_result: RAGSearchResult | None) -> str:
    if not rag_result or not rag_result.sources:
        return "Sources: none"
    titles = [source.title for source in rag_result.sources if source.title]
    return "Sources: " + ", ".join(titles[:5])


def summarize_workflow_result(
    scenario: str,
    intent: str,
    user_input: str,
    rag_result: RAGSearchResult | None = None,
    pending_action: PendingAction | None = None,
    severity: str = "unknown",
) -> str:
    source_line = _format_sources(rag_result)
    rag_answer = rag_result.answer.strip() if rag_result and rag_result.answer else ""
    rag_error = rag_result.error if rag_result else None

    if scenario == "customer_support":
        if rag_answer:
            answer = f"Customer support answer: {rag_answer}"
        elif rag_error:
            answer = f"Customer support knowledge lookup failed: {rag_error}"
        else:
            answer = "Customer support context was insufficient."
        if pending_action:
            answer += f" Pending approval required for {pending_action.tool}."
        return f"{answer}\n{source_line}"

    if scenario == "ops_runbook":
        if rag_answer:
            answer = f"Operations answer: {rag_answer}"
        elif rag_error:
            answer = f"Operations knowledge lookup failed: {rag_error}"
        else:
            answer = "Operations context was insufficient."
        answer += f"\nSeverity: {severity}."
        if pending_action:
            answer += f" Pending approval required for {pending_action.tool}."
        return f"{answer}\n{source_line}"

    if scenario == "unsafe_request":
        return "The request was blocked by workflow safety policies."

    return f"Scenario={scenario}, intent={intent}, input={user_input}\n{source_line}"
