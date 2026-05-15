from __future__ import annotations

import json

from app.rag.eval_service import EvalService
from app.schemas.rag import RAGQueryResponse, RAGSource


class FakeRAGService:
    def query(self, question: str, domain: str, top_k: int, trace_id: str) -> RAGQueryResponse:
        if "SLA" in question or "P1" in question:
            return RAGQueryResponse(
                success=True,
                answer="P1 SLA \u662f 15 \u5206\u949f\u54cd\u5e94\u3002\n\nsources: enterprise_sla.txt::0",
                sources=[
                    RAGSource(
                        domain="customer_support",
                        filename="enterprise_sla.txt",
                        page=None,
                        chunk_id="customer_support/enterprise_sla.txt::0",
                        score=0.9,
                    )
                ],
                selected_domain="customer_support",
                router_confidence=1.0,
                router_reason="test",
                latency_ms=1.0,
                trace_id=trace_id,
            )
        return RAGQueryResponse(
            success=True,
            answer="\u4e0d\u77e5\u9053\n\nsources: []",
            sources=[],
            selected_domain="enterprise_kb",
            router_confidence=1.0,
            router_reason="test",
            latency_ms=1.0,
            trace_id=trace_id,
        )


def test_eval_service_scores_source_and_keyword_hits(tmp_path):
    eval_dir = tmp_path / "data" / "eval"
    eval_dir.mkdir(parents=True)
    items = [
        {
            "question": "\u4f01\u4e1a\u5ba2\u6237 P1 SLA \u662f\u4ec0\u4e48\uff1f",
            "expected_source": "enterprise_sla.txt",
            "expected_keywords": ["15 \u5206\u949f"],
        },
        {
            "question": "\u4e0d\u5b58\u5728\u7684\u95ee\u9898\uff1f",
            "expected_source": "missing.md",
            "expected_keywords": ["\u4e0d\u5b58\u5728\u5173\u952e\u8bcd"],
        },
    ]
    with (eval_dir / "customer_support_eval.jsonl").open("w", encoding="utf-8") as file:
        for item in items:
            file.write(json.dumps(item, ensure_ascii=False) + "\n")

    service = EvalService(project_root=tmp_path, rag_service=FakeRAGService())
    response = service.run("data/eval/customer_support_eval.jsonl", domain="auto", top_k=5, trace_id="trace")

    assert response.success is True
    assert response.total == 2
    assert response.results[0].source_hit is True
    assert response.results[0].keyword_hit is True
    assert response.results[0].score == 1.0
    assert response.results[1].score == 0.0
    assert response.average_score == 0.5
