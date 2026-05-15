from __future__ import annotations

from app.router.domain_router import DomainRouter


def test_domain_router_routes_customer_support_sla_question():
    result = DomainRouter().route("\u4f01\u4e1a\u5ba2\u6237 P1 \u54cd\u5e94\u65f6\u95f4\u662f\u591a\u5c11\uff1f")

    assert result.domain == "customer_support"
    assert result.intent == "support_sla_or_ticket"
    assert result.confidence > 0.5
    assert "P1" in result.reason or "\u54cd\u5e94\u65f6\u95f4" in result.reason


def test_domain_router_respects_explicit_domain():
    result = DomainRouter().route("\u4efb\u610f\u95ee\u9898", requested_domain="legal_contract")

    assert result.domain == "legal_contract"
    assert result.intent == "explicit_domain"
    assert result.confidence == 1.0
