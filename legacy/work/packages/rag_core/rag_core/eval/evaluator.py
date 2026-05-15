from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

from rag_core.core.config import AGENT_CORE_ROOT
from rag_core.rag.service import RequestContext, rag_service
from rag_core.security.path_guard import ensure_within_allowed_path


def eval_runs_dir() -> Path:
    directory = AGENT_CORE_ROOT / "storage" / "eval_runs"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def save_eval_run(
    run_type: str,
    metrics: dict[str, Any],
    details: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    run_id = str(uuid.uuid4())
    payload = {"eval_run_id": run_id, "run_type": run_type, "metrics": metrics, "details": details or {}}
    if extra:
        payload.update(extra)
    (eval_runs_dir() / f"{run_id}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def load_eval_run(run_id: str) -> dict[str, Any] | None:
    path = eval_runs_dir() / f"{run_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def run_retrieval_eval(request: dict[str, Any], context: RequestContext | None = None) -> dict[str, Any]:
    context = context or RequestContext()
    cases = _load_eval_cases(request)
    hits = 0
    reciprocal_ranks: list[float] = []
    ranks: list[int] = []
    details: list[dict[str, Any]] = []
    public_results: list[dict[str, Any]] = []
    for case in cases:
        question = str(case.get("query") or case.get("question") or "")
        expected_source = case.get("expected_source") or case.get("expected_filename")
        debug = rag_service.debug_query(
            question,
            top_k=int(case.get("top_k", 5) or 5),
            domain=case.get("domain") or request.get("domain") or case.get("expected_domain"),
            context=context,
        )
        expected_chunk_id = case.get("expected_chunk_id")
        expected_domain = case.get("expected_domain")
        rank = 0
        retrieved_sources: list[str] = []
        for index, result in enumerate(debug["results"], start=1):
            filename = str(result.get("filename") or result.get("source") or result.get("document_id") or "")
            if filename:
                retrieved_sources.append(filename)
            if expected_chunk_id and result["chunk_id"] == expected_chunk_id:
                rank = index
                break
            if expected_source and filename == expected_source:
                rank = index
                break
            if not expected_source and expected_domain and result["domain"] == expected_domain:
                rank = index
                break
        hit = rank > 0
        hits += int(hit)
        if hit:
            ranks.append(rank)
            reciprocal_ranks.append(1 / rank)
        detail = {
            "question": question,
            "query": question,
            "expected_source": expected_source,
            "expected_filename": expected_source,
            "expected_domain": expected_domain,
            "retrieved_sources": retrieved_sources,
            "hit": hit,
            "rank": rank,
            "results": debug["results"],
        }
        details.append(detail)
        public_results.append(
            {
                "question": question,
                "expected_source": expected_source,
                "expected_filename": expected_source,
                "retrieved_sources": retrieved_sources,
                "hit": hit,
                "rank": rank,
            }
        )
    count = max(len(cases), 1)
    metrics = {
        "source_hit": hits / count,
        "keyword_hit": _keyword_hit_rate(cases, details),
        "hit_rate": hits / count,
        "mrr": sum(reciprocal_ranks) / count,
        "average_rank": sum(ranks) / len(ranks) if ranks else 0,
    }
    domain = request.get("domain") or _infer_eval_domain(cases)
    return save_eval_run(
        "retrieval",
        metrics,
        {"cases": details},
        {
            "domain": domain,
            "total": len(cases),
            "total_questions": len(cases),
            "hit_rate": metrics["hit_rate"],
            "mrr": metrics["mrr"],
            "average_rank": metrics["average_rank"],
            "results": public_results,
        },
    )


def run_generation_eval(request: dict[str, Any]) -> dict[str, Any]:
    cases = request.get("cases") or []
    relevancy_scores: list[float] = []
    grounded_scores: list[float] = []
    citation_scores: list[float] = []
    details: list[dict[str, Any]] = []
    for case in cases:
        answer = str(case.get("answer", ""))
        expected_keywords = [str(keyword).lower() for keyword in case.get("expected_keywords", [])]
        sources = case.get("sources") or []
        answer_lower = answer.lower()
        relevancy = sum(1 for keyword in expected_keywords if keyword in answer_lower) / max(len(expected_keywords), 1)
        source_text = " ".join(str(source.get("text", "")) for source in sources).lower()
        grounded = sum(1 for keyword in expected_keywords if keyword in source_text) / max(len(expected_keywords), 1)
        citation_coverage = min(len(sources), 1)
        relevancy_scores.append(relevancy)
        grounded_scores.append(grounded)
        citation_scores.append(float(citation_coverage))
        details.append({"answer_relevancy": relevancy, "groundedness": grounded, "citation_coverage": citation_coverage})
    count = max(len(cases), 1)
    metrics = {
        "answer_relevancy": sum(relevancy_scores) / count,
        "groundedness": sum(grounded_scores) / count,
        "citation_coverage": sum(citation_scores) / count,
        "ragas": {"skipped_reason": "RAGAS model is not configured"},
    }
    return save_eval_run("generation", metrics, {"cases": details})


def compare_retrieval_modes(request: dict[str, Any], context: RequestContext | None = None) -> dict[str, Any]:
    original_mode = os.getenv("RETRIEVAL_MODE")
    original_reranker = os.getenv("RERANKER_ENABLED")
    comparisons: dict[str, dict[str, Any]] = {}
    try:
        for label, mode, reranker in [
            ("dense", "dense", "false"),
            ("hybrid", "hybrid", "false"),
            ("hybrid_reranker", "hybrid", "true"),
        ]:
            os.environ["RETRIEVAL_MODE"] = mode
            os.environ["RERANKER_ENABLED"] = reranker
            comparisons[label] = run_retrieval_eval(request, context)["metrics"]
    finally:
        _restore_env("RETRIEVAL_MODE", original_mode)
        _restore_env("RERANKER_ENABLED", original_reranker)
    return save_eval_run("compare", {"comparisons": comparisons}, {})


def _load_eval_cases(request: dict[str, Any]) -> list[dict[str, Any]]:
    cases = [dict(case) for case in (request.get("cases") or [])]
    eval_file = request.get("eval_file") or request.get("file") or request.get("path")
    if not eval_file and not cases and request.get("domain"):
        eval_file = f"{request['domain']}_eval.jsonl"
    if eval_file:
        eval_dir = (AGENT_CORE_ROOT / "data" / "eval").resolve()
        raw_path = Path(str(eval_file))
        candidate = raw_path if raw_path.is_absolute() else eval_dir / raw_path.name
        path = ensure_within_allowed_path(candidate, [eval_dir])
        loaded: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if line:
                loaded.append(json.loads(line))
        cases.extend(loaded)
    normalized: list[dict[str, Any]] = []
    for case in cases:
        item = dict(case)
        if "query" not in item and item.get("question"):
            item["query"] = item["question"]
        if "expected_source" not in item and item.get("expected_filename"):
            item["expected_source"] = item["expected_filename"]
        if "domain" not in item and item.get("expected_domain"):
            item["domain"] = item["expected_domain"]
        normalized.append(item)
    return normalized


def _infer_eval_domain(cases: list[dict[str, Any]]) -> str | None:
    domains = {str(case.get("domain") or case.get("expected_domain")) for case in cases if case.get("domain") or case.get("expected_domain")}
    if len(domains) == 1:
        return next(iter(domains))
    return None


def _keyword_hit_rate(cases: list[dict[str, Any]], details: list[dict[str, Any]]) -> float:
    hits = 0
    for case, detail in zip(cases, details, strict=False):
        keywords = [str(keyword).lower() for keyword in case.get("keywords", [])]
        rendered = json.dumps(detail.get("results", []), ensure_ascii=False).lower()
        hits += int(all(keyword in rendered for keyword in keywords)) if keywords else int(detail["hit"])
    return hits / max(len(cases), 1)


def _restore_env(name: str, value: str | None) -> None:
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value

