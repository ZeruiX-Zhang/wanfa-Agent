from __future__ import annotations

import re

from rag_core.router.domain_router import DOMAIN_KEYWORDS, select_domain
from workflow_core.qa.models import QuestionAnalysis


DATA_PERMISSION_KEYWORDS = (
    "sql",
    "database",
    "dataset",
    "table",
    "chart",
    "csv",
    "warehouse",
    "local data",
    "本地数据",
    "数据库",
    "数据表",
    "图表",
    "生成图",
)

MULTI_HOP_HINTS = (
    " and ",
    " both ",
    " compare",
    " vs ",
    " versus",
    "difference between",
    "以及",
    "并且",
    "同时",
    "分别",
    "对比",
    "比较",
    "还要",
)

AMBIGUOUS_HINTS = ("这个", "那个", "它", "it", "this", "that")


class QuestionAnalyzer:
    def analyze(self, user_input: str, scenario: str, intent: str, mode: str) -> QuestionAnalysis:
        normalized = " ".join(user_input.strip().split())
        requested_domain = None if scenario in {"auto", "unknown", "unsafe_request"} else scenario
        selected_domain, confidence = select_domain(normalized, requested_domain)
        domains = self._candidate_domains(normalized)
        if selected_domain and selected_domain not in domains:
            domains.insert(0, selected_domain)

        explicit_data = self._contains_any(normalized, DATA_PERMISSION_KEYWORDS)
        requires_data_tool = mode == "analysis" or (mode == "hybrid" and explicit_data)
        needs_data_permission = mode == "auto" and explicit_data and selected_domain == "data_analysis"
        is_multi_hop = self._is_multi_hop(normalized, domains)
        needs_clarification = self._needs_clarification(normalized, selected_domain, needs_data_permission)
        question_type = self._question_type(
            is_multi_hop=is_multi_hop,
            needs_clarification=needs_clarification,
            requires_data_tool=requires_data_tool,
            scenario=scenario,
        )
        risk_flags = []
        if needs_data_permission:
            risk_flags.append("data_tool_requires_explicit_mode")
        if scenario == "unsafe_request" or intent == "unsafe_request":
            risk_flags.append("unsafe_request")

        clarification = None
        if needs_data_permission:
            clarification = "请确认是否允许调用数据分析 Agent，并使用 mode=analysis 或 mode=hybrid 重新提交。"
        elif needs_clarification:
            clarification = "请补充业务域、对象或希望查询的具体政策。"

        return QuestionAnalysis(
            original_question=user_input,
            normalized_question=normalized,
            question_type=question_type,
            primary_domain=selected_domain,
            domains=domains,
            is_multi_hop=is_multi_hop,
            needs_clarification=needs_clarification,
            clarification_question=clarification,
            requires_data_tool=requires_data_tool,
            data_tool_reason="explicit analysis mode or hybrid data request" if requires_data_tool else None,
            risk_flags=risk_flags,
            route_reason=f"scenario={scenario}; intent={intent}; domain_confidence={confidence:.2f}",
        )

    def _candidate_domains(self, text: str) -> list[str]:
        lowered = text.lower()
        scored: list[tuple[str, int]] = []
        for domain, keywords in DOMAIN_KEYWORDS.items():
            score = sum(1 for keyword in keywords if keyword.lower() in lowered)
            if score:
                scored.append((domain, score))
        return [domain for domain, _score in sorted(scored, key=lambda item: item[1], reverse=True)]

    def _is_multi_hop(self, text: str, domains: list[str]) -> bool:
        lowered = text.lower()
        if len(domains) > 1:
            return True
        if sum(1 for hint in MULTI_HOP_HINTS if hint in lowered) > 0:
            return True
        return len(re.findall(r"\?", text)) > 1

    def _needs_clarification(self, text: str, selected_domain: str | None, needs_data_permission: bool) -> bool:
        if needs_data_permission:
            return True
        stripped = text.strip()
        if not stripped:
            return True
        if selected_domain is None and len(stripped) < 14:
            return True
        lowered = stripped.lower()
        return len(stripped) < 18 and any(hint in lowered for hint in AMBIGUOUS_HINTS)

    def _question_type(
        self,
        *,
        is_multi_hop: bool,
        needs_clarification: bool,
        requires_data_tool: bool,
        scenario: str,
    ) -> str:
        if scenario == "unsafe_request":
            return "safety"
        if needs_clarification:
            return "ambiguous"
        if requires_data_tool:
            return "data"
        if is_multi_hop:
            return "multi_hop"
        return "direct"

    def _contains_any(self, text: str, keywords: tuple[str, ...]) -> bool:
        lowered = text.lower()
        return any(keyword.lower() in lowered for keyword in keywords)
