from __future__ import annotations

from app.schemas.agent import CSVAnalysisResult, IntentResult
from app.tools.csv_tool import analyze_csv
from app.tools.rag_tool import search_knowledge_base
from app.tools.summary_tool import summarize_workflow_result
from app.workflows.runtime import WorkflowRuntime
from app.workflows.types import WorkflowOutcome


def _should_analyze_csv(user_input: str) -> bool:
    text = user_input.lower()
    return any(
        keyword in text
        for keyword in ("csv", "指标", "区域", "增长", "营收", "收入", "q1", "q2", "q3", "q1-q3", "毛利")
    )


def run_finance_research_workflow(
    user_input: str,
    intent_result: IntentResult,
    runtime: WorkflowRuntime,
) -> WorkflowOutcome:
    rag_result = runtime.run_tool(
        "search_knowledge_base",
        {"question": user_input, "scenario": "finance_research", "top_k": 5},
        lambda: search_knowledge_base(user_input, "finance_research", top_k=5),
    )

    csv_result: CSVAnalysisResult | None = None
    if _should_analyze_csv(user_input):
        csv_result = runtime.run_tool(
            "analyze_csv",
            {"path": "data/finance/financial_metrics.csv"},
            lambda: analyze_csv(),
        )

    final_answer = runtime.run_tool(
        "summarize_workflow_result",
        {
            "scenario": "finance_research",
            "intent": intent_result.intent,
            "has_csv": bool(csv_result),
            "has_rag_error": bool(rag_result.error),
        },
        lambda: summarize_workflow_result(
            scenario="finance_research",
            intent=intent_result.intent,
            user_input=user_input,
            rag_result=rag_result,
            csv_result=csv_result,
        ),
    )
    return WorkflowOutcome(final_answer=final_answer, sources=rag_result.sources)

