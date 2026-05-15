from __future__ import annotations

from analyst_core.service import AnalysisServiceResult
from workflow_core.runtime_context import get_run_mode
from workflow_core.schemas.agent import IntentResult
from workflow_core.tools.analysis_tool import run_structured_analysis
from workflow_core.tools.rag_tool import search_knowledge_base
from workflow_core.workflows.runtime import WorkflowRuntime
from workflow_core.workflows.types import WorkflowOutcome


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def _mentions_metrics(user_input: str) -> bool:
    return _contains_any(
        user_input,
        (
            "csv",
            "sql",
            "metric",
            "metrics",
            "trend",
            "growth",
            "region",
            "revenue",
            "gross margin",
            "q1",
            "q2",
            "q3",
            "q4",
            "指标",
            "趋势",
            "增长",
            "区域",
            "营收",
            "收入",
            "毛利",
        ),
    )


def _mentions_external_context(user_input: str) -> bool:
    return _contains_any(
        user_input,
        (
            "source",
            "sources",
            "citation",
            "cite",
            "report",
            "filing",
            "annual report",
            "quarterly report",
            "summary",
            "财报",
            "年报",
            "季报",
            "研报",
            "来源",
            "引用",
            "总结",
            "摘要",
        ),
    )


def _resolve_mode(user_input: str) -> str:
    requested_mode = get_run_mode()
    if requested_mode != "auto":
        return requested_mode
    needs_analysis = _mentions_metrics(user_input)
    needs_knowledge = _mentions_external_context(user_input)
    if needs_analysis and needs_knowledge:
        return "hybrid"
    if needs_analysis:
        return "analysis"
    return "knowledge"


def _analysis_artifacts(result: AnalysisServiceResult | None) -> list[dict[str, object]]:
    if result is None:
        return []
    return [artifact.model_dump() for artifact in result.data_artifacts]


def _summarize_finance_answer(
    *,
    user_input: str,
    mode: str,
    analysis_result: AnalysisServiceResult | None,
    rag_answer: str | None,
) -> str:
    parts = ["This finance research summary is informational only and not investment advice."]
    parts.append(f"Execution mode: {mode}.")
    if rag_answer:
        parts.append(f"Knowledge summary: {rag_answer}")
    if analysis_result is not None:
        parts.append(f"Structured analysis: {analysis_result.final_answer}")
        if analysis_result.sql:
            parts.append(f"SQL: {analysis_result.sql}")
        parts.append(f"Row count: {analysis_result.row_count}")
    if not rag_answer and analysis_result is None:
        parts.append(f"No usable result was produced for: {user_input}")
    return "\n".join(parts)


def _run_finance_rag(user_input: str, runtime: WorkflowRuntime):
    rag_result = runtime.run_tool(
        "search_knowledge_base",
        {"question": user_input, "scenario": "finance_research", "top_k": 5},
        lambda: search_knowledge_base(user_input, "finance_research", top_k=5),
    )
    if rag_result.sources:
        return rag_result
    return runtime.run_tool(
        "search_knowledge_base_fallback",
        {"question": user_input, "scenario": "finance_research", "domain": "data_analysis", "top_k": 5},
        lambda: search_knowledge_base(user_input, "finance_research", top_k=5, domain="data_analysis"),
    )


def run_finance_research_workflow(
    user_input: str,
    intent_result: IntentResult,
    runtime: WorkflowRuntime,
) -> WorkflowOutcome:
    mode = _resolve_mode(user_input)
    rag_result = None
    if mode in {"knowledge", "hybrid"}:
        rag_result = _run_finance_rag(user_input, runtime)

    analysis_result: AnalysisServiceResult | None = None
    if mode in {"analysis", "hybrid"}:
        analysis_result = runtime.run_tool(
            "run_structured_analysis",
            {"question": user_input},
            lambda: run_structured_analysis(user_input),
        )

    final_answer = runtime.run_tool(
        "synthesize_finance_answer",
        {"mode": mode, "has_rag": rag_result is not None, "has_analysis": analysis_result is not None},
        lambda: _summarize_finance_answer(
            user_input=user_input,
            mode=mode,
            analysis_result=analysis_result,
            rag_answer=rag_result.answer if rag_result else None,
        ),
    )
    return WorkflowOutcome(
        final_answer=final_answer,
        sources=rag_result.sources if rag_result else [],
        mode=mode,
        data_artifacts=_analysis_artifacts(analysis_result),
        metadata={
            "analysis_trace_id": analysis_result.trace_id if analysis_result else None,
            "analysis_status": analysis_result.status if analysis_result else None,
            "intent": intent_result.intent,
            "rag_source_count": len(rag_result.sources) if rag_result else 0,
        },
    )
