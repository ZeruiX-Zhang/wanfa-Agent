from __future__ import annotations

from app.schemas.agent import CSVAnalysisResult, PendingAction, RAGSearchResult


def _format_sources(rag_result: RAGSearchResult | None) -> str:
    if not rag_result or not rag_result.sources:
        return "sources: 暂无可用引用。"
    titles = [source.title for source in rag_result.sources if source.title]
    return "sources: " + "；".join(titles[:5])


def _format_csv(csv_result: CSVAnalysisResult | None) -> str:
    if not csv_result:
        return ""
    lines = [
        f"CSV 计算结果：共 {csv_result.row_count} 行，列为 {', '.join(csv_result.columns)}。",
        f"按季度营收汇总：{csv_result.quarter_summary}",
        f"按区域营收增长率：{csv_result.growth_rates}",
    ]
    if csv_result.fastest_growth_region:
        rate = csv_result.growth_rates.get(csv_result.fastest_growth_region, 0)
        lines.append(f"增长最快区域：{csv_result.fastest_growth_region}，增长率 {rate:.2%}。")
    lines.append(f"计算逻辑：{csv_result.calculation_logic}")
    return "\n".join(lines)


def summarize_workflow_result(
    scenario: str,
    intent: str,
    user_input: str,
    rag_result: RAGSearchResult | None = None,
    csv_result: CSVAnalysisResult | None = None,
    pending_action: PendingAction | None = None,
    severity: str = "unknown",
) -> str:
    source_line = _format_sources(rag_result)
    rag_answer = rag_result.answer.strip() if rag_result and rag_result.answer else ""
    rag_error = rag_result.error if rag_result else None

    if scenario == "customer_support":
        if rag_answer:
            answer = f"基于客服知识库检索结果：{rag_answer}"
        elif rag_error:
            answer = f"客服知识库暂时不可用，无法核验政策细节。错误：{rag_error}"
        else:
            answer = "当前检索上下文不足，不能可靠回答该客服问题，建议转人工确认。"
        if pending_action:
            answer += f"\n我已生成 {pending_action.tool} 草稿，等待人工审批后执行。"
        return f"{answer}\n{source_line}"

    if scenario == "finance_research":
        parts = ["以下为投研摘要，不构成投资建议。"]
        if rag_answer:
            parts.append(f"财报/研报检索摘要：{rag_answer}")
        elif rag_error:
            parts.append(f"财报/研报 RAG 检索不可用，无法引用外部知识库结论。错误：{rag_error}")
        else:
            parts.append("财报/研报检索上下文不足，不能编造财务结论。")
        csv_text = _format_csv(csv_result)
        if csv_text:
            parts.append(csv_text)
        else:
            parts.append("本次问题未触发 CSV 指标计算，或没有可用 CSV 数据。")
        parts.append(source_line)
        return "\n".join(parts)

    if scenario == "ops_runbook":
        if rag_answer:
            answer = f"基于运维 runbook 检索结果：{rag_answer}"
        elif rag_error:
            answer = f"运维知识库暂时不可用，无法核验 runbook。错误：{rag_error}"
        else:
            answer = "当前 runbook 上下文不足，不能可靠给出处理步骤，建议联系值班人员。"
        answer += f"\n严重级别判断：{severity}。"
        if pending_action:
            answer += f"\n我已生成 {pending_action.tool} 草稿，等待人工审批后执行。"
        return f"{answer}\n{source_line}"

    if scenario == "unsafe_request":
        return "该请求涉及敏感文件、密钥或凭证访问，已按安全策略拒绝。"

    return "当前请求不属于已支持的三个业务场景，无法进入可靠 workflow。"

