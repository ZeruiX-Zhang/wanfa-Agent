from __future__ import annotations

from typing import Any

from rag_core.rag.service import RequestContext, rag_service
from workflow_core.runtime_context import get_auth_context
from workflow_core.schemas.agent import RAGSearchResult, Source
from workflow_core.security.policies import redact_secrets


SCENARIO_DOMAIN_MAP = {
    "customer_support": "customer_support",
    "finance_research": "finance_research",
    "ops_runbook": "ops_runbook",
}


def _normalize_source(item: Any, index: int) -> Source:
    if not isinstance(item, dict):
        return Source(title=f"source-{index}", snippet=str(item))
    return Source(
        title=str(item.get("title") or item.get("source") or item.get("document_title") or f"source-{index}"),
        url=item.get("url"),
        document_id=str(item.get("document_id") or item.get("doc_id") or item.get("id") or "") or None,
        chunk_id=str(item.get("chunk_id") or item.get("chunk") or "") or None,
        score=float(item["score"]) if item.get("score") is not None else None,
        snippet=item.get("snippet") or item.get("content") or item.get("text"),
    )


def search_knowledge_base(
    question: str,
    scenario: str,
    top_k: int = 5,
    domain: str | None = None,
) -> RAGSearchResult:
    actual_domain = domain or SCENARIO_DOMAIN_MAP.get(scenario, "auto")
    auth_context = get_auth_context()
    request_context = RequestContext(
        user_id=auth_context.user_id,
        tenant_id=auth_context.tenant_id,
        roles=auth_context.roles,
    )
    payload = rag_service.query(
        query=question,
        top_k=top_k,
        domain=None if actual_domain == "auto" else actual_domain,
        context=request_context,
    )
    sources = [_normalize_source(item, index + 1) for index, item in enumerate(payload.get("sources", []))]
    return RAGSearchResult(
        answer=str(payload.get("answer") or ""),
        sources=sources,
        domain=str(payload.get("debug", {}).get("selected_domain") or actual_domain),
        raw=redact_secrets(payload.get("debug", {})),
    )
