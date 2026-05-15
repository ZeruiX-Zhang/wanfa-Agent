from __future__ import annotations

from app.schemas.domain import DomainRequestValue, DomainRouteResult, SUPPORTED_DOMAINS


class DomainRouter:
    """Rule-based router for the first multi-domain RAG baseline."""

    def route(self, question: str, requested_domain: DomainRequestValue = "auto") -> DomainRouteResult:
        if requested_domain != "auto":
            return DomainRouteResult(
                domain=requested_domain,
                intent="explicit_domain",
                confidence=1.0,
                reason=f"Request explicitly selected domain: {requested_domain}",
            )

        lowered = question.lower()
        rules: list[tuple[str, str, tuple[str, ...]]] = [
            (
                "customer_support",
                "support_sla_or_ticket",
                (
                    "sla",
                    "p1",
                    "p2",
                    "\u54cd\u5e94\u65f6\u95f4",
                    "\u6545\u969c",
                    "\u5ba2\u6237",
                    "\u5de5\u5355",
                    "\u7f13\u89e3",
                ),
            ),
            (
                "finance_research",
                "financial_research",
                (
                    "\u8d22\u62a5",
                    "\u6536\u5165",
                    "\u589e\u957f",
                    "\u8425\u6536",
                    "\u6bdb\u5229",
                    "\u5229\u6da6",
                    "\u7814\u7a76",
                    "\u4f30\u503c",
                    "revenue",
                    "margin",
                    "finance",
                ),
            ),
            (
                "ops_runbook",
                "ops_incident_runbook",
                (
                    "\u8fd0\u7ef4",
                    "\u544a\u8b66",
                    "\u56de\u6eda",
                    "\u53d1\u5e03",
                    "\u6269\u5bb9",
                    "\u8fd0\u884c\u624b\u518c",
                    "runbook",
                    "deploy",
                    "rollback",
                    "incident",
                ),
            ),
            (
                "legal_contract",
                "legal_contract_review",
                (
                    "\u5408\u540c",
                    "\u6cd5\u52a1",
                    "\u5ba2\u6237\u6570\u636e",
                    "\u671f\u9650",
                    "\u8fdd\u7ea6",
                    "\u4fdd\u5bc6",
                    "\u8d54\u507f",
                    "\u6761\u6b3e",
                    "contract",
                    "legal",
                    "nda",
                ),
            ),
            (
                "data_analysis",
                "data_metric_analysis",
                (
                    "\u6570\u636e",
                    "\u8868\u683c",
                    "\u5747\u503c",
                    "\u6700\u5927\u503c",
                    "\u6700\u5c0f\u503c",
                    "\u6307\u6807",
                    "\u5206\u6bb5",
                    "csv",
                    "report",
                    "mean",
                    "metric",
                    "analysis",
                ),
            ),
            (
                "enterprise_kb",
                "enterprise_policy",
                (
                    "\u62a5\u9500",
                    "\u5236\u5ea6",
                    "\u5458\u5de5",
                    "\u5dee\u65c5",
                    "\u5ba1\u6279",
                    "\u516c\u53f8",
                    "policy",
                    "employee",
                ),
            ),
        ]

        best_domain = "enterprise_kb"
        best_intent = "general_enterprise_query"
        best_score = 0
        best_keywords: list[str] = []
        for domain, intent, keywords in rules:
            hits = [keyword for keyword in keywords if keyword in lowered or keyword in question]
            if len(hits) > best_score:
                best_domain = domain
                best_intent = intent
                best_score = len(hits)
                best_keywords = hits

        if best_score == 0:
            return DomainRouteResult(
                domain="enterprise_kb",
                intent="general_enterprise_query",
                confidence=0.35,
                reason="No strong domain keyword matched; defaulted to enterprise_kb.",
            )

        confidence = min(0.95, 0.55 + best_score * 0.12)
        return DomainRouteResult(
            domain=best_domain,  # type: ignore[arg-type]
            intent=best_intent,
            confidence=confidence,
            reason=f"Matched domain keywords: {', '.join(best_keywords)}",
        )

    def supported_domains(self) -> tuple[str, ...]:
        return SUPPORTED_DOMAINS
