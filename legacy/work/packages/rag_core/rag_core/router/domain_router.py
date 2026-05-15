from __future__ import annotations


DOMAIN_KEYWORDS: dict[str, set[str]] = {
    "customer_support": {
        "p1",
        "sla",
        "ticket",
        "support",
        "customer",
        "客户",
        "企业客户",
        "响应时间",
        "工单",
        "升级响应",
    },
    "legal_contract": {
        "agreement",
        "contract",
        "indemnity",
        "legal",
        "liability",
        "limitation of liability",
        "msa",
        "service agreement",
        "termination",
        "合同",
        "条款",
        "协议",
        "服务协议",
        "责任上限",
        "责任限制",
        "赔偿",
        "违约",
        "法务",
    },
    "enterprise_kb": {
        "enterprise",
        "semantic",
        "architecture",
        "policy",
        "knowledge",
        "strategy",
        "政策",
        "报销",
        "餐饮",
        "上限",
        "公司制度",
    },
    "finance_research": {
        "finance",
        "financial",
        "earnings",
        "revenue",
        "gross margin",
        "quarterly",
        "annual report",
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
        "来源",
        "引用",
    },
    "ops_runbook": {
        "error",
        "runbook",
        "incident",
        "deploy",
        "rollback",
        "错误码",
        "故障",
        "支付",
        "支付网关",
        "超时",
        "重试队列",
        "第三方通道",
        "备用通道",
        "处理流程",
        "值班",
        "告警",
        "升级",
        "pay-502",
    },
    "data_analysis": {
        "csv",
        "dataset",
        "table",
        "chart",
        "sql",
        "sales",
        "data analysis",
        "数据分析",
        "图表",
        "查询",
        "统计",
    },
}

HIGH_SIGNAL_KEYWORDS: dict[str, set[str]] = {
    "legal_contract": {"责任上限", "赔偿", "违约", "终止"},
    "customer_support": {"sla", "响应时间", "工单"},
    "finance_research": {"quarterly", "annual report", "财报", "营收", "毛利"},
    "ops_runbook": {"错误码", "pay-502", "升级"},
}


def select_domain(query: str, requested_domain: str | None = None) -> tuple[str | None, float]:
    if requested_domain:
        return requested_domain, 1.0

    normalized = query.lower()
    scores = {domain: _score_domain(domain, normalized) for domain in DOMAIN_KEYWORDS}
    selected_domain = max(scores, key=scores.get)
    selected_score = scores[selected_domain]
    if selected_score == 0:
        return None, 0.0
    confidence = min(0.55 + selected_score * 0.1, 0.95)
    return selected_domain, confidence


def _score_domain(domain: str, normalized_query: str) -> int:
    score = sum(1 for keyword in DOMAIN_KEYWORDS[domain] if keyword in normalized_query)
    score += sum(1 for keyword in HIGH_SIGNAL_KEYWORDS.get(domain, set()) if keyword in normalized_query)
    return score
