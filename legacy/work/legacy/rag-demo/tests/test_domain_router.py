from __future__ import annotations

import pytest

from app.router.domain_router import select_domain


@pytest.mark.parametrize(
    "query",
    [
        "支付错误码如何处理？",
        "支付错误码 PAY-502 是什么意思？",
        "支付网关超时怎么办？",
        "故障处理流程是什么？",
        "如何切换备用支付通道？",
        "支付故障如何升级？",
        "告警后值班人员应该怎么处理？",
    ],
)
def test_ops_queries_route_to_ops_runbook(query: str) -> None:
    selected_domain, confidence = select_domain(query)

    assert selected_domain == "ops_runbook"
    assert confidence >= 0.75


@pytest.mark.parametrize(
    "query",
    [
        "合同责任上限是多少？",
        "违约责任如何约定？",
        "合同责任上限是多少？违约责任如何约定？",
        "MSA 条款中的责任限制是什么？",
        "赔偿责任和违约金怎么约定？",
        "合同终止条件是什么？",
        "服务协议的责任限制是什么？",
    ],
)
def test_contract_queries_route_to_legal_contract(query: str) -> None:
    selected_domain, confidence = select_domain(query)

    assert selected_domain == "legal_contract"
    assert confidence >= 0.75


def test_customer_support_query_still_routes_to_customer_support() -> None:
    selected_domain, confidence = select_domain("企业客户 P1 响应时间是多少？")

    assert selected_domain == "customer_support"
    assert confidence >= 0.75


def test_enterprise_kb_query_still_routes_to_enterprise_kb() -> None:
    selected_domain, confidence = select_domain("单次餐饮报销上限是多少？")

    assert selected_domain == "enterprise_kb"
    assert confidence >= 0.75
