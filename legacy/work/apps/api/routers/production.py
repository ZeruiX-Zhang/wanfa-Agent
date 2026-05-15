from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from analyst_core.agent.pipeline import DataAnalystAgent
from analyst_core.core.config import get_settings as get_analyst_settings
from analyst_core.db.schema import retrieve_schema
from analyst_core.schemas.data_agent import DataAgentQueryRequest, SQLValidationRequest
from analyst_core.sql.safety import SQLSafetyChecker
from analyst_core.trace.store import TraceStore
from evaluation.runner import run_evaluation, write_reports
from llm_gateway.config import model_config, resolve_model
from platform_common.auth import require_auth
from platform_common.events import list_events
from platform_common.models import AuthContext, ApprovalRequest, PendingAction, RagQueryRequest, UnifiedRunRequest
from platform_common.settings import ROOT_DIR, get_settings
from platform_common.traces import UnifiedTraceStore
from rag_core.rag.ingestion_jobs import ingestion_jobs
from rag_core.rag.service import RequestContext, rag_service
from tool_registry import get_default_registry
from workflow_core.unified_service import approve_unified_run, run_unified_agent
from ..workbench import recent_trace_summaries, trace_detail


router = APIRouter(tags=["Enterprise Workbench"])
trace_store = UnifiedTraceStore()
tool_registry = get_default_registry()


class WorkbenchRagResponse(BaseModel):
    answer: str
    citations: list[dict[str, Any]] = Field(default_factory=list)
    retrieved_chunks: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = 0.0
    evidence_score: float = 0.0
    trace_id: str
    debug: dict[str, Any] = Field(default_factory=dict)


class AgentRunCreateResponse(BaseModel):
    run_id: str
    trace_id: str
    status: str
    final_response: str
    answer_type: str | None = None
    confidence: float | None = None
    qa_plan: dict[str, Any] = Field(default_factory=dict)
    evidence_report: dict[str, Any] = Field(default_factory=dict)
    verification: dict[str, Any] = Field(default_factory=dict)
    pending_confirmation: PendingAction | None = None
    called_tools: list[str] = Field(default_factory=list)
    trace_url: str


class DataAgentAPIResponse(BaseModel):
    run_id: str
    trace_id: str
    status: str
    answer: str
    generated_sql: str | None = None
    safe_sql: str | None = None
    table_preview: list[dict[str, Any]] = Field(default_factory=list)
    chart_spec: dict[str, Any] | None = None
    chart_file: str | None = None
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    row_count: int = 0


class EvalRunRequest(BaseModel):
    target: str = Field(default="all", pattern="^(rag|agent|data-agent|all)$")


@router.get("/api/health")
def api_health() -> dict[str, Any]:
    settings = get_settings()
    analyst_settings = get_analyst_settings()
    _, _, chat_provider = resolve_model(None, "chat")
    _, _, embedding_provider = resolve_model(None, "embedding")
    chunks_path = settings.rag_storage_dir / "chunks.jsonl"
    return {
        "status": "ok" if chunks_path.exists() and analyst_settings.database_path.exists() else "degraded",
        "service": "Enterprise AI Workbench",
        "components": {
            "db": {"status": "ok" if analyst_settings.database_path.exists() else "missing", "path": str(analyst_settings.database_path)},
            "vector_store": {"status": "ok" if chunks_path.exists() else "empty", "path": str(chunks_path)},
            "llm": {"status": "degraded" if chat_provider["name"] == "mock" else "ok", "provider": chat_provider["name"]},
            "embedding": {"status": "degraded" if embedding_provider["name"] == "mock" else "ok", "provider": embedding_provider["name"]},
            "storage": {"status": "ok", "trace_store": str(settings.unified_trace_path)},
        },
    }


@router.post("/api/rag/query", response_model=WorkbenchRagResponse)
def api_rag_query(request: RagQueryRequest, auth: AuthContext = Depends(require_auth)) -> WorkbenchRagResponse:
    context = RequestContext(user_id=auth.user_id, tenant_id=auth.tenant_id, roles=auth.roles)
    payload = rag_service.query(
        query=request.question,
        top_k=request.top_k,
        domain=None if request.domain == "auto" else request.domain,
        context=context,
    )
    debug = payload.get("debug", {})
    return WorkbenchRagResponse(
        answer=payload["answer"],
        citations=payload.get("citations", []),
        retrieved_chunks=payload.get("sources", []),
        confidence=float(payload.get("confidence") or 0.0),
        evidence_score=float(payload.get("evidence_score") or 0.0),
        trace_id=str(debug.get("trace_id") or ""),
        debug=debug,
    )


@router.post("/api/rag/query/debug")
def api_rag_debug(request: RagQueryRequest, auth: AuthContext = Depends(require_auth)) -> dict[str, Any]:
    context = RequestContext(user_id=auth.user_id, tenant_id=auth.tenant_id, roles=auth.roles)
    return rag_service.debug_query(
        query=request.question,
        top_k=request.top_k,
        domain=None if request.domain == "auto" else request.domain,
        context=context,
    )


@router.post("/api/rag/documents/ingest-local")
def api_rag_ingest_local(payload: dict[str, Any], sync: bool = True, auth: AuthContext = Depends(require_auth)) -> dict[str, Any]:
    job = ingestion_jobs.create(payload)
    context = RequestContext(user_id=auth.user_id, tenant_id=auth.tenant_id, roles=auth.roles)
    if sync:
        job = ingestion_jobs.run_local(job.id, context)
    return job.model_dump()


@router.get("/api/tools")
def api_tools(auth: AuthContext = Depends(require_auth)) -> dict[str, Any]:
    del auth
    return {"tools": tool_registry.list_specs()}


@router.post("/api/agent/runs", response_model=AgentRunCreateResponse)
def api_agent_runs(request: UnifiedRunRequest, auth: AuthContext = Depends(require_auth)) -> AgentRunCreateResponse:
    response = run_unified_agent(request, auth, trace_store=trace_store)
    return AgentRunCreateResponse(
        run_id=response.run_id,
        trace_id=response.trace_id,
        status=response.status,
        final_response=response.final_answer,
        answer_type=response.answer_type,
        confidence=response.confidence,
        qa_plan=response.qa_plan,
        evidence_report=response.evidence_report,
        verification=response.verification,
        pending_confirmation=response.pending_action,
        called_tools=[step.name for step in response.tool_steps],
        trace_url=f"/api/agent/runs/{response.run_id}/trace",
    )


@router.get("/api/agent/runs/{run_id}")
def api_agent_run(run_id: str) -> dict[str, Any]:
    trace = trace_store.get(run_id)
    if trace is None:
        raise HTTPException(status_code=404, detail={"message": "run_id not found"})
    return trace.model_dump(mode="json")


@router.get("/api/agent/runs/{run_id}/trace")
def api_agent_run_trace(run_id: str) -> dict[str, Any]:
    return api_agent_run(run_id)


@router.post("/api/agent/runs/{run_id}/confirm")
def api_agent_confirm(run_id: str, request: ApprovalRequest, auth: AuthContext = Depends(require_auth)) -> dict[str, Any]:
    del auth
    response = approve_unified_run(run_id, request, trace_store=trace_store)
    if response is None:
        raise HTTPException(status_code=404, detail={"message": "run_id not found"})
    return response.model_dump(mode="json")


@router.post("/api/agent/runs/{run_id}/cancel")
def api_agent_cancel(run_id: str, auth: AuthContext = Depends(require_auth)) -> dict[str, Any]:
    del auth
    trace = trace_store.get(run_id)
    if trace is None:
        raise HTTPException(status_code=404, detail={"message": "run_id not found"})
    trace.status = "rejected"
    trace.final_answer = "Run cancelled before confirmation."
    trace.pending_action = None
    trace_store.save(trace)
    return {"run_id": run_id, "status": trace.status, "final_answer": trace.final_answer}


@router.post("/api/data-agent/query", response_model=DataAgentAPIResponse)
def api_data_agent_query(request: DataAgentQueryRequest, auth: AuthContext = Depends(require_auth)) -> DataAgentAPIResponse:
    del auth
    agent = DataAnalystAgent(enable_trace=True)
    response = agent.run(request)
    chart_spec = None
    if response.sql_plan:
        chart_spec = {"chart_type": response.sql_plan.chart_type, "title": response.sql_plan.analysis_type}
    return DataAgentAPIResponse(
        run_id=response.run_id,
        trace_id=response.trace_id,
        status=response.status,
        answer=response.final_answer,
        generated_sql=response.sql_plan.sql if response.sql_plan else None,
        safe_sql=response.sql,
        table_preview=response.table_rows[:10],
        chart_spec=chart_spec,
        chart_file=response.chart.chart_path if response.chart else None,
        assumptions=["Demo SQLite warehouse; generated SQL is schema-grounded and read-only."],
        limitations=["Heuristic correctness evaluator and rule fallback are used when no LLM key is configured."],
        row_count=response.row_count,
    )


@router.get("/api/data-agent/schema")
def api_data_agent_schema(auth: AuthContext = Depends(require_auth)) -> dict[str, Any]:
    del auth
    return retrieve_schema().model_dump(mode="json")


@router.post("/api/data-agent/sql/check")
def api_data_agent_sql_check(request: SQLValidationRequest, auth: AuthContext = Depends(require_auth)) -> dict[str, Any]:
    del auth
    return SQLSafetyChecker().validate(request.sql).model_dump()


@router.get("/api/data-agent/runs/{run_id}")
def api_data_agent_run(run_id: str) -> dict[str, Any]:
    trace = TraceStore().get(run_id)
    if trace is None:
        raise HTTPException(status_code=404, detail={"message": "data agent run not found"})
    return trace.model_dump(mode="json")


@router.post("/api/evaluation/run")
def api_eval_run(request: EvalRunRequest, auth: AuthContext = Depends(require_auth)) -> dict[str, Any]:
    del auth
    report = run_evaluation(request.target)
    write_reports(report)
    return report


@router.get("/api/traces")
def api_traces(limit: int = Query(default=20, ge=1, le=100)) -> dict[str, Any]:
    runs = trace_store.list_runs()[-limit:][::-1]
    return {
        "runs": [run.model_dump(mode="json") for run in runs],
        "traces": recent_trace_summaries(limit),
        "events": list_events(limit=limit),
    }


@router.get("/api/traces/{trace_id}")
def api_trace(trace_id: str) -> dict[str, Any]:
    detail = trace_detail(trace_id)
    matched_runs = [run for run in trace_store.list_runs() if run.trace_id == trace_id or run.run_id == trace_id]
    llm_calls = _load_jsonl(ROOT_DIR / "storage" / "traces" / "llm_calls.jsonl", trace_id)
    events = [event for event in list_events(limit=200) if event.get("trace_id") == trace_id]
    if detail is not None:
        detail["llm_calls"] = llm_calls
        detail["events"] = detail.get("events") or events
        return detail
    if not matched_runs and not llm_calls and not events:
        raise HTTPException(status_code=404, detail={"message": "trace not found"})
    return {
        "trace_id": trace_id,
        "runs": [run.model_dump(mode="json") for run in matched_runs],
        "llm_calls": llm_calls,
        "events": events,
    }


@router.get("/debug", response_class=HTMLResponse)
def debug_dashboard(auth: AuthContext = Depends(require_auth)) -> HTMLResponse:
    del auth
    runs = trace_store.list_runs()[-20:][::-1]
    report_path = ROOT_DIR / "reports" / "eval_report.md"
    report = report_path.read_text(encoding="utf-8") if report_path.exists() else "No eval report generated yet."
    rows = "\n".join(
        f"<tr><td>{run.run_id}</td><td>{run.status}</td><td>{run.mode}</td><td>{run.scenario}</td><td>{run.trace_id}</td></tr>"
        for run in runs
    )
    html = f"""
<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Enterprise AI Workbench Debug</title>
<style>body{{font-family:Segoe UI,Arial,sans-serif;margin:24px;color:#172033}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #d7dde8;padding:8px;text-align:left}}pre{{background:#f6f8fb;padding:12px;overflow:auto}}</style></head>
<body>
<h1>Debug Center</h1>
<h2>Recent Runs</h2>
<table><thead><tr><th>Run</th><th>Status</th><th>Mode</th><th>Scenario</th><th>Trace</th></tr></thead><tbody>{rows}</tbody></table>
<h2>Eval Report</h2>
<pre>{report}</pre>
</body></html>
"""
    return HTMLResponse(html)


def _load_jsonl(path: Path, trace_id: str) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if payload.get("trace_id") == trace_id:
            rows.append(payload)
    return rows
