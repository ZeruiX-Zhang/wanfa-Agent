from __future__ import annotations

import re
from typing import Any

from guardrails.service import GuardrailService
from platform_common.models import GuardrailDecision
from workflow_core.qa.models import EvidenceItem, EvidenceReport, QAPlan, SubquestionEvidence
from workflow_core.schemas.agent import RAGSearchResult, Source
from workflow_core.tools.rag_tool import search_knowledge_base


PROMPT_INJECTION_MARKERS = (
    "ignore previous instructions",
    "ignore all previous instructions",
    "system prompt",
    "developer message",
    "execute shell",
    "reveal api key",
    "reveal token",
    "泄露密钥",
    "忽略之前",
)


class EvidenceCollector:
    def __init__(
        self,
        guardrail_service: GuardrailService | None = None,
        guardrail_decisions: list[dict[str, Any]] | None = None,
    ) -> None:
        self.guardrails = guardrail_service or GuardrailService()
        self.guardrail_decisions = guardrail_decisions

    def collect(self, plan: QAPlan, scenario: str) -> EvidenceReport:
        subquestions: list[SubquestionEvidence] = []
        total_sources = 0
        blocked_count = 0
        injection_count = 0
        saw_non_allow_guardrail = False

        for step in plan.steps:
            seen: set[str] = set()
            items: list[EvidenceItem] = []
            blocked_items: list[EvidenceItem] = []
            answers: list[str] = []
            notes: list[str] = []
            queries = step.query_variants or [step.question]

            for query in queries:
                result = search_knowledge_base(query, scenario=scenario, top_k=step.top_k, domain=step.domain)
                answers.append(result.answer)
                accepted, blocked, had_non_allow = self._items_from_result(result, query, seen)
                saw_non_allow_guardrail = saw_non_allow_guardrail or had_non_allow
                items.extend(accepted)
                blocked_items.extend(blocked)

            if not items and step.domain:
                fallback = search_knowledge_base(step.question, scenario=scenario, top_k=step.top_k, domain="auto")
                answers.append(fallback.answer)
                accepted, blocked, had_non_allow = self._items_from_result(fallback, step.question, seen)
                saw_non_allow_guardrail = saw_non_allow_guardrail or had_non_allow
                items.extend(accepted)
                blocked_items.extend(blocked)
                notes.append("domain fallback used")

            total_sources += len(items) + len(blocked_items)
            blocked_count += len(blocked_items)
            injection_count += sum(1 for item in items + blocked_items if item.prompt_injection_flags)
            subquestions.append(
                SubquestionEvidence(
                    step_id=step.step_id,
                    question=step.question,
                    domain=step.domain,
                    queries=queries,
                    answer=self._best_answer(answers),
                    items=items,
                    blocked_items=blocked_items,
                    notes=notes,
                )
            )

        if total_sources and self.guardrail_decisions is not None and not saw_non_allow_guardrail:
            self.guardrail_decisions.append(
                GuardrailDecision(
                    stage="retrieval_precheck",
                    decision="allow",
                    reason="retrieved evidence accepted",
                    policy_ids=["retrieval_allow"],
                ).model_dump()
            )

        supported = sum(1 for item in subquestions if item.items)
        return EvidenceReport(
            subquestions=subquestions,
            usable_evidence_count=sum(len(item.items) for item in subquestions),
            total_sources=total_sources,
            blocked_source_count=blocked_count,
            prompt_injection_count=injection_count,
            coverage=round(supported / max(len(subquestions), 1), 4) if subquestions else 0.0,
        )

    def to_sources(self, report: EvidenceReport) -> list[Source]:
        sources: list[Source] = []
        seen: set[str] = set()
        for subquestion in report.subquestions:
            for item in subquestion.items:
                key = item.chunk_id or item.document_id or item.title
                if key in seen:
                    continue
                seen.add(key)
                sources.append(
                    Source(
                        title=item.title,
                        document_id=item.document_id,
                        chunk_id=item.chunk_id,
                        score=item.score,
                        snippet=item.snippet,
                    )
                )
        return sources

    def _items_from_result(
        self,
        result: RAGSearchResult,
        query: str,
        seen: set[str],
    ) -> tuple[list[EvidenceItem], list[EvidenceItem], bool]:
        accepted: list[EvidenceItem] = []
        blocked: list[EvidenceItem] = []
        had_non_allow = False
        for source in result.sources:
            item = self._evidence_item(source, query, result.domain)
            key = item.chunk_id or item.document_id or self._fingerprint(item.snippet or item.title)
            if key in seen:
                continue
            seen.add(key)
            decision = self.guardrails.check_retrieval_context(
                {
                    "title": item.title,
                    "snippet": item.snippet,
                    "document_id": item.document_id,
                    "chunk_id": item.chunk_id,
                }
            )
            if decision.decision != "allow":
                had_non_allow = True
                if self.guardrail_decisions is not None:
                    self.guardrail_decisions.append(decision.model_dump())
            if decision.decision == "block":
                item.blocked = True
                blocked.append(item)
            else:
                accepted.append(item)
        return accepted, blocked, had_non_allow

    def _evidence_item(self, source: Source, query: str, domain: str | None) -> EvidenceItem:
        snippet = source.snippet or ""
        return EvidenceItem(
            title=source.title,
            snippet=snippet,
            document_id=source.document_id,
            chunk_id=source.chunk_id,
            score=source.score,
            domain=domain,
            query=query,
            prompt_injection_flags=self._prompt_injection_flags(snippet),
        )

    def _prompt_injection_flags(self, text: str) -> list[str]:
        lowered = text.lower()
        return [marker for marker in PROMPT_INJECTION_MARKERS if marker in lowered or marker in text]

    def _fingerprint(self, value: str) -> str:
        return re.sub(r"\W+", "", value.lower())[:80]

    def _best_answer(self, answers: list[str]) -> str:
        cleaned = [answer.strip() for answer in answers if answer and answer.strip()]
        if not cleaned:
            return ""
        return max(cleaned, key=len)
