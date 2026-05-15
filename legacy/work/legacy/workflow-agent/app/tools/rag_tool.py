from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings
from app.schemas.agent import RAGSearchResult, Source
from app.security.policies import redact_secrets


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


def _extract_sources(payload: dict[str, Any]) -> list[Source]:
    candidates = (
        payload.get("sources"),
        payload.get("citations"),
        payload.get("source_documents"),
        payload.get("documents"),
    )
    for candidate in candidates:
        if isinstance(candidate, list):
            return [_normalize_source(item, index + 1) for index, item in enumerate(candidate)]
    data = payload.get("data")
    if isinstance(data, dict):
        return _extract_sources(data)
    return []


def _extract_answer(payload: dict[str, Any]) -> str:
    for key in ("answer", "final_answer", "response", "result"):
        value = payload.get(key)
        if isinstance(value, str):
            return value
    data = payload.get("data")
    if isinstance(data, dict):
        return _extract_answer(data)
    return ""


def search_knowledge_base(
    question: str,
    scenario: str,
    top_k: int = 5,
    domain: str | None = None,
) -> RAGSearchResult:
    actual_domain = domain or SCENARIO_DOMAIN_MAP.get(scenario, "auto")
    base_url = settings.rag_base_url.rstrip("/")
    url = f"{base_url}/rag/query"
    request_body = {"question": question, "domain": actual_domain, "top_k": top_k}
    try:
        with httpx.Client(timeout=settings.request_timeout_seconds, trust_env=False) as client:
            response = client.post(
                url,
                headers={"X-API-Key": settings.rag_api_key, "Content-Type": "application/json"},
                json=request_body,
            )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            return RAGSearchResult(
                domain=actual_domain,
                error="RAG 返回格式不是 JSON object",
                raw={"type": type(payload).__name__},
            )
        return RAGSearchResult(
            answer=_extract_answer(payload),
            sources=_extract_sources(payload),
            domain=actual_domain,
            raw=redact_secrets(payload),
        )
    except Exception as exc:
        return RAGSearchResult(
            domain=actual_domain,
            error=f"RAG 服务不可用或调用失败: {exc}",
            raw={"request": redact_secrets(request_body), "url": base_url},
        )

