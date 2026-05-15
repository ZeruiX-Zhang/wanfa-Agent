from __future__ import annotations

import re

from workflow_core.schemas.agent import IntentResult, ScenarioRouteResult
from workflow_core.security.policies import is_unsafe_request


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def classify_scenario(user_input: str) -> ScenarioRouteResult:
    text = user_input.lower()
    if is_unsafe_request(user_input):
        return ScenarioRouteResult(
            scenario="unsafe_request",
            confidence=0.99,
            reason="Sensitive file, secret, or shell access was requested.",
        )

    customer_keywords = (
        "customer",
        "support",
        "ticket",
        "sla",
        "refund",
        "after-sales",
        "customer success",
        "客户",
        "客服",
        "工单",
        "退款",
        "售后",
        "响应时间",
    )
    finance_keywords = (
        "finance",
        "financial",
        "revenue",
        "gross margin",
        "earnings",
        "annual report",
        "quarterly",
        "analyst",
        "q1",
        "q2",
        "q3",
        "q4",
        "财报",
        "年报",
        "季报",
        "投研",
        "营收",
        "收入",
        "毛利",
        "指标",
        "增长",
        "区域",
    )
    ops_keywords = (
        "incident",
        "runbook",
        "rollback",
        "deploy",
        "payment gateway",
        "error code",
        "p0",
        "p1",
        "p2",
        "故障",
        "运维",
        "值班",
        "升级",
        "告警",
        "错误码",
        "支付",
    )

    customer_score = sum(1 for item in customer_keywords if item.lower() in text)
    finance_score = sum(1 for item in finance_keywords if item.lower() in text)
    ops_score = sum(1 for item in ops_keywords if item.lower() in text)

    if finance_score:
        return ScenarioRouteResult(
            scenario="finance_research",
            confidence=min(0.95, 0.65 + finance_score * 0.08),
            reason="Matched finance or structured-analysis keywords.",
        )
    if customer_score:
        return ScenarioRouteResult(
            scenario="customer_support",
            confidence=min(0.95, 0.65 + customer_score * 0.08),
            reason="Matched customer-support keywords.",
        )
    if ops_score or re.search(r"\b(p0|p1|p2)\b", text):
        return ScenarioRouteResult(
            scenario="ops_runbook",
            confidence=min(0.95, 0.7 + ops_score * 0.08),
            reason="Matched operations or incident keywords.",
        )
    return ScenarioRouteResult(
        scenario="unknown",
        confidence=0.45,
        reason="No supported scenario matched.",
    )


def classify_intent(user_input: str, scenario: str) -> IntentResult:
    text = user_input.lower()
    if is_unsafe_request(user_input) or scenario == "unsafe_request":
        return IntentResult(
            intent="unsafe_request",
            confidence=0.99,
            reason="Request hit a safety boundary.",
        )

    if scenario == "customer_support":
        if _contains_any(text, ("refund", "return", "after-sales", "退款", "退货", "售后")):
            return IntentResult(intent="refund_or_after_sales", confidence=0.9, reason="Refund or after-sales question.")
        if _contains_any(text, ("complaint", "unhappy", "投诉", "不满")):
            return IntentResult(intent="complaint", confidence=0.87, reason="Complaint detected.")
        if _contains_any(text, ("human", "handoff", "contact manager", "转人工", "人工客服", "升级客服")):
            return IntentResult(intent="handoff_to_human", confidence=0.9, reason="Human handoff requested.")
        if _contains_any(text, ("create ticket", "open ticket", "创建工单", "提交工单")):
            return IntentResult(intent="create_ticket_request", confidence=0.92, reason="Ticket creation requested.")
        if _contains_any(text, ("p1", "outage", "issue", "故障", "问题")):
            return IntentResult(intent="technical_issue", confidence=0.78, reason="Technical issue in support context.")
        return IntentResult(intent="knowledge_question", confidence=0.78, reason="Knowledge lookup in support context.")

    if scenario == "finance_research":
        if _contains_any(text, ("summary", "summarize", "overview", "变化", "总结", "摘要", "概览")):
            return IntentResult(intent="financial_summary", confidence=0.9, reason="Summary-style finance request.")
        return IntentResult(intent="financial_analysis", confidence=0.86, reason="Structured finance analysis request.")

    if scenario == "ops_runbook":
        if _contains_any(text, ("escalate", "notify", "on-call", "p0", "p1", "incident", "升级", "通知", "值班")):
            return IntentResult(intent="incident_escalation", confidence=0.9, reason="Incident escalation request.")
        if _contains_any(text, ("error", "troubleshoot", "investigate", "错误码", "处理", "排查", "runbook")):
            return IntentResult(intent="incident_troubleshooting", confidence=0.88, reason="Incident troubleshooting request.")
        return IntentResult(intent="knowledge_question", confidence=0.7, reason="Operations knowledge request.")

    return IntentResult(intent="unknown", confidence=0.4, reason="Intent could not be classified.")
