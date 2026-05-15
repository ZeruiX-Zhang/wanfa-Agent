from __future__ import annotations

import re

from rag_core.router.domain_router import select_domain
from workflow_core.qa.analyzer import QuestionAnalyzer
from workflow_core.qa.models import QAPlan, QAPlanStep, QuestionAnalysis


SCENARIO_DOMAIN_MAP = {
    "customer_support": "customer_support",
    "finance_research": "finance_research",
    "ops_runbook": "ops_runbook",
    "legal_contract": "legal_contract",
    "enterprise_kb": "enterprise_kb",
}

QUERY_EXPANSIONS = {
    "sla": "service level agreement response time priority support",
    "p0": "critical incident emergency approval notification",
    "p1": "priority one urgent response escalation",
    "refund": "return after-sales entitlement approval",
    "rollback": "incident commander approval change rollback",
    "502": "payment gateway upstream provider retry queue failover",
    "revenue": "quarterly revenue gross margin sales",
    "prompt injection": "untrusted context ignore previous instructions",
    "api key": "secret credential token password policy",
    "退款": "售后 订单校验 权益审核 主管审批",
    "响应": "SLA 优先级 响应时间",
    "回滚": "事故指挥官 审批 变更",
    "支付": "支付网关 第三方通道 重试队列 备用通道",
}


class QAPlanner:
    def __init__(self, analyzer: QuestionAnalyzer | None = None) -> None:
        self.analyzer = analyzer or QuestionAnalyzer()

    def build(self, user_input: str, scenario: str, intent: str, mode: str) -> tuple[QuestionAnalysis, QAPlan]:
        analysis = self.analyzer.analyze(user_input, scenario, intent, mode)
        if analysis.needs_clarification:
            return analysis, QAPlan(
                strategy="clarify_before_retrieval",
                allow_data_tool=False,
                steps=[],
                output_requirements=["ask a concise clarification question", "do not call tools that need approval"],
            )

        fragments = self._split_question(analysis.normalized_question) if analysis.is_multi_hop else [analysis.normalized_question]
        if not fragments:
            fragments = [analysis.normalized_question]

        steps = []
        for index, fragment in enumerate(fragments[:3], start=1):
            domain = self._domain_for(fragment, scenario, analysis.primary_domain)
            variants = self._query_variants(fragment)
            steps.append(
                QAPlanStep(
                    step_id=f"q{index}",
                    question=fragment,
                    domain=domain,
                    top_k=5,
                    required_evidence=1,
                    query_variants=variants,
                )
            )

        return analysis, QAPlan(
            strategy="multi_query_rag" if len(steps) > 1 else "focused_rag",
            allow_data_tool=analysis.requires_data_tool,
            steps=steps,
            output_requirements=[
                "answer only from retrieved evidence",
                "include code-generated citations",
                "state limitations when evidence is missing",
                "show audit-friendly plan and evidence metadata in trace",
            ],
        )

    def _split_question(self, question: str) -> list[str]:
        parts = re.split(r"\?|;|；|以及|并且|同时|分别|还要| and | also ", question, flags=re.IGNORECASE)
        cleaned = [part.strip(" ，,。.") for part in parts if len(part.strip()) >= 6]
        return cleaned[:3]

    def _domain_for(self, question: str, scenario: str, fallback: str | None) -> str | None:
        domain, _confidence = select_domain(question, None)
        if domain:
            return domain
        return SCENARIO_DOMAIN_MAP.get(scenario) or fallback

    def _query_variants(self, question: str) -> list[str]:
        variants = [question]
        lowered = question.lower()
        additions = [value for key, value in QUERY_EXPANSIONS.items() if key.lower() in lowered or key in question]
        if additions:
            variants.append(f"{question} {' '.join(additions)}")
        normalized = re.sub(r"\s+", " ", question).strip()
        if normalized not in variants:
            variants.append(normalized)
        deduped: list[str] = []
        for item in variants:
            if item and item not in deduped:
                deduped.append(item)
        return deduped[:3]
