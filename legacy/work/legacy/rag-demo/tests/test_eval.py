from __future__ import annotations

from fastapi.testclient import TestClient

from app.eval.evaluator import load_eval_run, run_generation_eval, run_retrieval_eval
from app.main import app
from app.rag.models import Chunk
from app.rag.service import RequestContext, rag_service


client = TestClient(app)
AUTH_HEADERS = {"X-API-Key": "change-me"}


def test_retrieval_eval_saves_hit_rate_mrr_and_rank() -> None:
    rag_service.ingest_chunks(
        [
            Chunk(
                id="eval-support",
                document_id="eval",
                chunk_id="eval-support",
                domain="customer_support",
                text="P1 SLA response",
            )
        ],
        replace=True,
    )

    run = run_retrieval_eval(
        {"cases": [{"query": "P1 SLA", "domain": "customer_support", "expected_chunk_id": "eval-support"}]},
        context=RequestContext(tenant_id="default", roles=["reader"]),
    )

    assert run["metrics"]["hit_rate"] == 1
    assert run["metrics"]["mrr"] == 1
    assert run["metrics"]["average_rank"] == 1
    assert load_eval_run(run["eval_run_id"]) is not None


def test_generation_eval_returns_metrics_and_ragas_skip_reason() -> None:
    run = run_generation_eval(
        {
            "cases": [
                {
                    "answer": "The P1 SLA response is 15 minutes.",
                    "expected_keywords": ["P1", "SLA"],
                    "sources": [{"text": "P1 SLA source"}],
                }
            ]
        }
    )

    assert run["metrics"]["answer_relevancy"] == 1
    assert run["metrics"]["groundedness"] == 1
    assert run["metrics"]["citation_coverage"] == 1
    assert run["metrics"]["ragas"]["skipped_reason"]


def test_eval_run_api_roundtrip() -> None:
    run = run_generation_eval({"cases": []})

    response = client.get(f"/eval/runs/{run['eval_run_id']}", headers=AUTH_HEADERS)

    assert response.status_code == 200
    assert response.json()["eval_run_id"] == run["eval_run_id"]
