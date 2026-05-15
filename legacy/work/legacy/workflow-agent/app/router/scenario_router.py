from __future__ import annotations

import re

from app.schemas.agent import IntentResult, ScenarioRouteResult
from app.security.policies import is_unsafe_request


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword.lower() in text for keyword in keywords)


def classify_scenario(user_input: str) -> ScenarioRouteResult:
    text = user_input.lower()
    if is_unsafe_request(user_input):
        return ScenarioRouteResult(
            scenario="unsafe_request",
            confidence=0.99,
            reason="请求涉及读取敏感文件、密钥或凭证，命中安全边界。",
        )

    customer_keywords = (
        "企业客户",
        "客户",
        "sla",
        "退款",
        "售后",
        "客服",
        "faq",
        "私有化",
        "合规",
        "评审",
        "投诉",
        "工单",
    )
    finance_keywords = (
        "投研",
        "金融",
        "财报",
        "年报",
        "季报",
        "研报",
        "营收",
        "收入",
        "指标",
        "区域",
        "增长",
        "毛利",
        "gross_margin",
        "revenue",
        "csv",
        "q1",
        "q2",
        "q3",
        "q4",
    )
    ops_keywords = (
        "错误码",
        "故障",
        "runbook",
        "sop",
        "值班",
        "incident",
        "支付错误",
        "pay-",
        "e1027",
        "p0",
        "p1",
        "p2",
    )

    customer_score = sum(1 for item in customer_keywords if item.lower() in text)
    finance_score = sum(1 for item in finance_keywords if item.lower() in text)
    ops_score = sum(1 for item in ops_keywords if item.lower() in text)

    if customer_score:
        return ScenarioRouteResult(
            scenario="customer_support",
            confidence=min(0.95, 0.65 + customer_score * 0.08),
            reason="命中 SLA、退款、客户服务或客服工单相关关键词。",
        )
    if finance_score:
        return ScenarioRouteResult(
            scenario="finance_research",
            confidence=min(0.95, 0.65 + finance_score * 0.08),
            reason="命中财报、投研、营收、区域增长或 CSV 指标相关关键词。",
        )
    if ops_score or re.search(r"\b(p0|p1|p2)\b", text):
        return ScenarioRouteResult(
            scenario="ops_runbook",
            confidence=min(0.95, 0.7 + ops_score * 0.08),
            reason="命中错误码、故障、SOP、值班或 incident 相关关键词。",
        )
    return ScenarioRouteResult(
        scenario="unknown",
        confidence=0.45,
        reason="未匹配到已支持的业务场景关键词。",
    )


def classify_intent(user_input: str, scenario: str) -> IntentResult:
    text = user_input.lower()
    if is_unsafe_request(user_input) or scenario == "unsafe_request":
        return IntentResult(
            intent="unsafe_request",
            confidence=0.99,
            reason="请求触发敏感信息或越权访问规则。",
        )

    if scenario == "customer_support":
        if _contains_any(text, ("退款", "退费", "售后", "超过 7 天", "超过7天")):
            return IntentResult(intent="refund_or_after_sales", confidence=0.9, reason="用户在询问退款或售后政策。")
        if _contains_any(text, ("投诉", "不满", "抱怨")):
            return IntentResult(intent="complaint", confidence=0.87, reason="用户表达投诉或不满。")
        if _contains_any(text, ("转人工", "人工", "联系客户经理", "通知客服")):
            return IntentResult(intent="handoff_to_human", confidence=0.9, reason="用户要求人工介入。")
        if _contains_any(text, ("创建工单", "开工单", "提交工单")):
            return IntentResult(intent="create_ticket_request", confidence=0.92, reason="用户明确要求创建工单。")
        if _contains_any(text, ("p1", "问题", "故障")):
            return IntentResult(intent="technical_issue", confidence=0.78, reason="用户在客服语境中询问技术问题或 SLA。")
        return IntentResult(intent="knowledge_question", confidence=0.78, reason="客服知识库问答意图。")

    if scenario == "finance_research":
        if _contains_any(text, ("总结", "摘要", "概览", "变化", "q1-q3", "q1 到 q3")):
            return IntentResult(intent="financial_summary", confidence=0.9, reason="用户要求生成投研摘要或趋势总结。")
        return IntentResult(intent="financial_analysis", confidence=0.86, reason="用户要求结合结构化指标进行投研分析。")

    if scenario == "ops_runbook":
        if _contains_any(text, ("升级", "通知", "值班", "p0", "p1", "incident")):
            return IntentResult(intent="incident_escalation", confidence=0.9, reason="用户在询问或触发故障升级流程。")
        if _contains_any(text, ("错误码", "怎么处理", "处理", "排查", "pay-", "e1027")):
            return IntentResult(intent="incident_troubleshooting", confidence=0.88, reason="用户需要错误码或故障处理步骤。")
        return IntentResult(intent="knowledge_question", confidence=0.7, reason="运维知识库问答意图。")

    return IntentResult(intent="unknown", confidence=0.4, reason="未识别到稳定意图。")

