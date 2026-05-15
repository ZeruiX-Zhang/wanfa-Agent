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
        "赔偿责任",
        "违约",
        "违约责任",
        "违约金",
        "终止",
        "终止条件",
        "生效",
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
    "ops_runbook": {
        "error",
        "e503",
        "503",
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
        "支付通道",
        "备用支付通道",
        "切换",
        "处理流程",
        "值班",
        "告警",
        "升级",
        "pay-502",
    },
}

HIGH_SIGNAL_KEYWORDS: dict[str, set[str]] = {
    "legal_contract": {
        "limitation of liability",
        "service agreement",
        "责任上限",
        "责任限制",
        "赔偿责任",
        "违约责任",
        "违约金",
        "终止条件",
    },
}


def select_domain(query: str, requested_domain: str | None = None) -> tuple[str | None, float]:
    if requested_domain:
        return requested_domain, 1.0

    normalized = query.lower()
    scores = {
        domain: _score_domain(domain, normalized)
        for domain in DOMAIN_KEYWORDS
    }
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
