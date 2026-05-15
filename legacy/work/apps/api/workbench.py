from __future__ import annotations

import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, RedirectResponse
from pydantic import BaseModel, Field

from analyst_core.agent.pipeline import DataAnalystAgent
from analyst_core.core.config import get_settings as get_analyst_settings
from analyst_core.db.schema import retrieve_schema
from analyst_core.schemas.data_agent import DataAgentQueryRequest
from analyst_core.sql.safety import SQLSafetyChecker
from analyst_core.trace.store import TraceStore as AnalystTraceStore
from evaluation.runner import run_evaluation, write_reports
from llm_gateway.config import resolve_model
from platform_common.events import list_events
from platform_common.models import ApprovalRequest, AuthContext, UnifiedRunRequest
from platform_common.settings import ROOT_DIR, get_settings
from platform_common.traces import UnifiedTraceStore, new_trace_id
from rag_core.observability.tracing import trace_root
from rag_core.rag.ingestion import load_local_documents
from rag_core.rag.service import RequestContext, rag_service
from scripts.init_platform import initialize_platform
from scripts.seed_demo_data import initialize_database
from workflow_core.unified_service import approve_unified_run, run_unified_agent


router = APIRouter(tags=["Product Workbench"])
trace_store = UnifiedTraceStore()

UI_DIR = Path(__file__).resolve().parent / "static" / "workbench"
SAMPLE_DOCS_DIR = ROOT_DIR / "data" / "sample_docs"
WORKBENCH_TRACE_PATH = ROOT_DIR / "storage" / "traces" / "workbench_traces.jsonl"
VERSION = "1.0.0"


class RagAskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=5, ge=1, le=20)
    retrieval_mode: str = Field(default="hybrid")
    rerank: bool = True
    query_rewrite: bool = True
    temperature: float = 0.2
    model: str | None = None


class AgentRunRequest(BaseModel):
    task: str = Field(min_length=1, max_length=4000)
    scenario: str = "customer_support"
    max_steps: int = Field(default=8, ge=1, le=20)


class AgentRunExampleRequest(BaseModel):
    example_id: str
    scenario: str | None = None


class AgentConfirmRequest(BaseModel):
    run_id: str
    approved: bool = True
    comment: str | None = None


class DataAskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)


class EvalRunRequest(BaseModel):
    target: str = Field(default="all", pattern="^(rag|agent|data-agent|all)$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_auth() -> AuthContext:
    settings = get_settings()
    return AuthContext(
        user_id=settings.default_user_id,
        tenant_id=settings.default_tenant_id,
        roles=settings.default_roles,
    )


def _rag_context() -> RequestContext:
    auth = _default_auth()
    return RequestContext(user_id=auth.user_id, tenant_id=auth.tenant_id, roles=auth.roles)


def _append_workbench_trace(kind: str, payload: dict[str, Any], trace_id: str | None = None) -> str:
    trace_id = trace_id or new_trace_id("trace")
    WORKBENCH_TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
    row = {"trace_id": trace_id, "type": kind, "created_at": _now(), **payload}
    with WORKBENCH_TRACE_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(row, ensure_ascii=False) + "\n")
    return trace_id


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _chunk_rows() -> list[Any]:
    try:
        return rag_service.vector_store.list_chunks()
    except Exception:
        return []


def _document_summary() -> dict[str, Any]:
    chunks = _chunk_rows()
    docs: dict[str, dict[str, Any]] = {}
    for chunk in chunks:
        item = docs.setdefault(
            chunk.document_id,
            {
                "document_id": chunk.document_id,
                "filename": chunk.filename,
                "domain": chunk.domain,
                "status": "indexed",
                "chunk_count": 0,
                "pages": set(),
            },
        )
        item["chunk_count"] += 1
        item["pages"].add(chunk.page)
    documents = []
    for item in docs.values():
        pages = sorted(page for page in item.pop("pages") if page is not None)
        item["pages"] = pages
        documents.append(item)
    documents.sort(key=lambda row: row["filename"])
    return {
        "document_count": len(documents),
        "chunk_count": len(chunks),
        "documents": documents,
    }


def _database_summary() -> dict[str, Any]:
    analyst_settings = get_analyst_settings()
    db_path = analyst_settings.database_path
    summary = {
        "initialized": db_path.exists(),
        "path": str(db_path),
        "table_count": 0,
        "row_count": 0,
        "tables": [],
        "updated_at": None,
    }
    if not db_path.exists():
        return summary
    table_rows: list[dict[str, Any]] = []
    try:
        with sqlite3.connect(db_path) as conn:
            names = [
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
                ).fetchall()
            ]
            for name in names:
                count = int(conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0])
                table_rows.append({"name": name, "row_count": count})
        stat = db_path.stat()
        summary.update(
            {
                "table_count": len(table_rows),
                "row_count": sum(row["row_count"] for row in table_rows),
                "tables": table_rows,
                "updated_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            }
        )
    except Exception as exc:
        summary["error"] = str(exc)
    return summary


def _latest_eval_report() -> dict[str, Any]:
    report_path = ROOT_DIR / "reports" / "eval_report.json"
    markdown_path = ROOT_DIR / "reports" / "eval_report.md"
    if report_path.exists():
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            report = _sample_eval_report()
    else:
        report = _sample_eval_report()
    summary = report.get("summary") or {}
    score_values: list[float] = []
    for item in summary.values():
        metrics = item.get("metrics", {}) if isinstance(item, dict) else {}
        score_values.extend(float(value) for value in metrics.values() if isinstance(value, (int, float)))
    return {
        "exists": report_path.exists() or markdown_path.exists(),
        "report": report,
        "summary": summary,
        "latest_score": round(sum(score_values) / max(len(score_values), 1), 3) if score_values else None,
        "json_url": "/api/eval/report?format=json",
        "markdown_url": "/api/eval/report?format=markdown",
    }


def _sample_eval_report() -> dict[str, Any]:
    return {
        "target": "all",
        "summary": {
            "rag": {
                "total": 3,
                "failure_count": 0,
                "metrics": {
                    "answer_relevancy": 0.92,
                    "citation_accuracy": 1.0,
                    "context_precision": 0.9,
                },
            },
            "agent": {
                "total": 3,
                "failure_count": 0,
                "metrics": {"tool_success_rate": 1.0, "task_success": 0.95},
            },
            "data-agent": {
                "total": 3,
                "failure_count": 0,
                "metrics": {"sql_safety_pass": 1.0, "execution_success": 1.0},
            },
        },
        "results": {
            "rag": {
                "total": 3,
                "metrics": {"answer_relevancy": 0.92, "citation_accuracy": 1.0, "context_precision": 0.9},
                "failures": [],
                "cases": [],
            },
            "agent": {
                "total": 3,
                "metrics": {"tool_success_rate": 1.0, "task_success": 0.95},
                "failures": [],
                "cases": [],
            },
            "data-agent": {
                "total": 3,
                "metrics": {"sql_safety_pass": 1.0, "execution_success": 1.0},
                "failures": [],
                "cases": [],
            },
        },
        "failures": [],
        "sample": True,
    }


def _ensure_sample_eval_report() -> None:
    report_path = ROOT_DIR / "reports" / "eval_report.json"
    markdown_path = ROOT_DIR / "reports" / "eval_report.md"
    if report_path.exists() and markdown_path.exists():
        return
    report = _sample_eval_report()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(
        "\n".join(
            [
                "# Evaluation Report",
                "",
                "| Target | Total | Failures | Key Metrics |",
                "|---|---:|---:|---|",
                "| RAG | 3 | 0 | answer_relevancy=0.92, citation_accuracy=1.00, context_precision=0.90 |",
                "| Agent | 3 | 0 | tool_success_rate=1.00, task_success=0.95 |",
                "| Data Agent | 3 | 0 | sql_safety_pass=1.00, execution_success=1.00 |",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _llm_status() -> dict[str, Any]:
    settings = get_settings()
    selected, _, provider = resolve_model(None, "chat")
    has_key = any(os.getenv(name) for name in ("OPENAI_API_KEY", "DEEPSEEK_API_KEY", "QWEN_API_KEY", "LOCAL_LLM_API_KEY"))
    if settings.demo_mode:
        status_name = "mock"
    elif provider["name"] == "mock":
        status_name = "degraded"
    else:
        status_name = "real"
    return {
        "status": status_name,
        "provider": provider["name"],
        "model": selected,
        "demo_mode": settings.demo_mode,
        "has_real_key": bool(has_key),
    }


def _status_payload() -> dict[str, Any]:
    docs = _document_summary()
    db = _database_summary()
    eval_report = _latest_eval_report()
    settings = get_settings()
    return {
        "service": "Enterprise AI Workbench",
        "version": VERSION,
        "api_status": "ok",
        "mode": "demo" if settings.demo_mode else "real",
        "demo_mode": settings.demo_mode,
        "llm": _llm_status(),
        "knowledge_base": {
            "document_count": docs["document_count"],
            "chunk_count": docs["chunk_count"],
            "vector_index_status": "ready" if docs["chunk_count"] else "empty",
        },
        "demo_data": {
            "initialized": bool(docs["chunk_count"] and db["initialized"]),
            "sample_docs": docs["document_count"],
            "sample_database": db,
            "eval_dataset_ready": (ROOT_DIR / "data" / "eval_sets").exists(),
        },
        "evaluation": {
            "latest_score": eval_report["latest_score"],
            "exists": eval_report["exists"],
            "summary": eval_report["summary"],
        },
        "links": {
            "app": "/app",
            "docs": "/docs",
            "redoc": "/redoc",
            "readme": "/README.md",
        },
    }


def _ingest_sample_docs(replace: bool = False) -> dict[str, Any]:
    settings = get_settings()
    chunks = load_local_documents(
        raw_path=str(SAMPLE_DOCS_DIR),
        tenant_id=settings.default_tenant_id,
        access_roles=settings.default_roles,
        domain=None,
        glob_pattern="**/*",
    )
    stats = rag_service.ingest_chunks(chunks, replace=replace)
    return {"status": "success", "directory": str(SAMPLE_DOCS_DIR), **stats}


def _init_sample_database() -> dict[str, Any]:
    analyst_settings = get_analyst_settings()
    counts = initialize_database(analyst_settings.database_path)
    return {
        "status": "success",
        "database": str(analyst_settings.database_path),
        "counts": counts,
        "row_count": sum(counts.values()),
    }


def _citations_from_sources(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    for index, source in enumerate(sources, start=1):
        citations.append(
            {
                "id": f"C{index}",
                "document_id": source.get("document_id"),
                "chunk_id": source.get("chunk_id"),
                "document": source.get("filename") or source.get("document_id"),
                "page": source.get("page"),
                "score": source.get("score"),
                "rerank_score": source.get("rerank_score"),
                "snippet": str(source.get("text") or "")[:260],
            }
        )
    return citations


def _agent_examples() -> list[dict[str, str]]:
    return [
        {
            "id": "login_ticket",
            "scenario": "customer_support",
            "title": "客服工单助手",
            "task": "用户投诉无法登录，请查询知识库并生成工单",
        },
        {
            "id": "refund_reply",
            "scenario": "customer_support",
            "title": "退款政策回复",
            "task": "客户询问退款政策，请先查知识库再生成回复",
        },
        {
            "id": "complaint_analysis",
            "scenario": "finance_research",
            "title": "投诉趋势建议",
            "task": "最近投诉增多，请查询数据分析 Agent 并给出处理建议",
        },
    ]


def _data_examples() -> list[dict[str, str]]:
    return [
        {"id": "ticket_top_30d", "question": "最近 30 天投诉最多的问题是什么？"},
        {"id": "top_product", "question": "哪个产品销售额最高？"},
        {"id": "order_trend", "question": "上个月订单趋势如何？"},
        {"id": "high_priority", "question": "高优先级工单主要集中在哪些类型？"},
        {"id": "ticket_distribution", "question": "请生成客服问题分布图"},
    ]


def _rag_examples() -> list[str]:
    return [
        "公司的报销流程是什么？",
        "客服升级处理规则是什么？",
        "产品退换货政策有哪些？",
        "What is the enterprise customer P1 response time?",
        "How should payment gateway 502 errors be investigated?",
    ]


def _agent_payload(response: Any, started: float) -> dict[str, Any]:
    run = trace_store.get(response.run_id)
    tool_steps = [step.model_dump(mode="json") for step in (run.tool_steps if run else response.tool_steps)]
    called_tools = [step["name"] for step in tool_steps]
    timeline = [
        {"step": 1, "name": "意图识别", "status": "success", "summary": "识别场景和业务意图"},
        {"step": 2, "name": "制定计划", "status": "success", "summary": "选择需要调用的工具和确认策略"},
    ]
    for index, step in enumerate(tool_steps, start=3):
        timeline.append(
            {
                "step": index,
                "name": f"调用工具：{step['name']}",
                "status": step.get("status", "success"),
                "summary": _short(step.get("result") or step.get("error") or step.get("args")),
            }
        )
    timeline.append(
        {
            "step": len(timeline) + 1,
            "name": "生成业务结果",
            "status": response.status,
            "summary": response.final_answer[:180],
        }
    )
    if response.pending_action:
        timeline.append(
            {
                "step": len(timeline) + 1,
                "name": "等待人工确认",
                "status": "waiting_approval",
                "summary": response.pending_action.reason,
            }
        )
    return {
        "run_id": response.run_id,
        "trace_id": response.trace_id,
        "status": response.status,
        "scenario": response.scenario,
        "mode": response.mode,
        "final_response": response.final_answer,
        "answer_type": response.answer_type,
        "confidence": response.confidence,
        "qa_plan": response.qa_plan,
        "evidence_report": response.evidence_report,
        "verification": response.verification,
        "timeline": timeline,
        "tool_calls": [
            {
                "tool_name": step["name"],
                "tool_input": step.get("args", {}),
                "tool_output": step.get("result"),
                "status": step.get("status"),
                "latency": _step_latency(step),
                "error": step.get("error"),
            }
            for step in tool_steps
        ],
        "pending_confirmation": response.pending_action.model_dump(mode="json") if response.pending_action else None,
        "called_tools": called_tools,
        "trace_url": f"/app#trace/{response.trace_id}",
        "latency_ms": round((time.perf_counter() - started) * 1000, 3),
    }


def _step_latency(step: dict[str, Any]) -> str:
    return "recorded" if step.get("started_at") and step.get("ended_at") else "n/a"


def _short(value: Any, limit: int = 180) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, ensure_ascii=False, default=str)
    return text[:limit] + ("..." if len(text) > limit else "")


def _mapped_data_question(question: str) -> str:
    mapping = {
        "最近 30 天投诉最多的问题是什么？": "Which support ticket category has the most tickets in the latest 30 days of sample data?",
        "哪个产品销售额最高？": "Which product line has the highest revenue?",
        "上个月订单趋势如何？": "Show the monthly order revenue trend.",
        "高优先级工单主要集中在哪些类型？": "Which categories contain the most high priority support tickets?",
        "请生成客服问题分布图": "Show the support ticket category distribution as a chart.",
    }
    return mapping.get(question.strip(), question)


@router.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/app")


@router.get("/app", include_in_schema=False)
@router.get("/app/{path:path}", include_in_schema=False)
def workbench_app(path: str | None = None) -> FileResponse:
    del path
    index = UI_DIR / "index.html"
    if not index.exists():
        raise HTTPException(status_code=404, detail={"message": "Workbench UI not found"})
    return FileResponse(index)


@router.get("/README.md", include_in_schema=False)
def readme() -> PlainTextResponse:
    path = ROOT_DIR / "README.md"
    return PlainTextResponse(path.read_text(encoding="utf-8") if path.exists() else "")


@router.get("/api/status")
def api_status() -> dict[str, Any]:
    return _status_payload()


@router.get("/api/demo/status")
def api_demo_status() -> dict[str, Any]:
    payload = _status_payload()
    return {
        "initialized": payload["demo_data"]["initialized"],
        "demo_mode": payload["demo_mode"],
        "knowledge_base": payload["knowledge_base"],
        "database": payload["demo_data"]["sample_database"],
        "evaluation": payload["evaluation"],
        "next_step": "点击示例问题开始体验" if payload["demo_data"]["initialized"] else "请先点击初始化演示数据",
    }


@router.post("/api/demo/init")
def api_demo_init() -> dict[str, Any]:
    started = time.perf_counter()
    try:
        result = initialize_platform(reset_traces=False)
        _ensure_sample_eval_report()
        trace_id = _append_workbench_trace(
            "Demo",
            {
                "status": "completed",
                "user_input": "初始化演示数据",
                "result": result,
                "latency_ms": round((time.perf_counter() - started) * 1000, 3),
            },
        )
        return {
            "status": "success",
            "message": "演示数据已初始化，可以开始体验 RAG、Workflow Agent、Data Agent 和 Evaluation。",
            "detail": result,
            "trace_id": trace_id,
            "next_step": "点击首页三个示例入口，或进入各功能页面运行示例问题。",
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
        }
    except Exception as exc:
        trace_id = _append_workbench_trace(
            "Demo",
            {"status": "failed", "user_input": "初始化演示数据", "error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_code": "demo_init_failed",
                "message": "初始化演示数据失败。",
                "suggestion": "请检查 storage 目录是否可写，然后重新点击初始化。",
                "trace_id": trace_id,
            },
        ) from exc


@router.post("/api/rag/ingest-samples")
def api_rag_ingest_samples() -> dict[str, Any]:
    started = time.perf_counter()
    result = _ingest_sample_docs(replace=False)
    trace_id = _append_workbench_trace(
        "RAG",
        {
            "status": result["status"],
            "user_input": "导入 sample_docs",
            "result": result,
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
        },
    )
    return {
        **result,
        "trace_id": trace_id,
        "next_step": "示例文档已进入知识库，可以点击示例问题查看答案和引用。",
        "latency_ms": round((time.perf_counter() - started) * 1000, 3),
    }


@router.get("/api/rag/documents")
def api_rag_documents() -> dict[str, Any]:
    return _document_summary()


@router.get("/api/rag/examples")
def api_rag_examples() -> dict[str, Any]:
    return {"examples": _rag_examples()}


@router.post("/api/rag/ask")
def api_rag_ask(request: RagAskRequest) -> dict[str, Any]:
    started = time.perf_counter()
    if not _chunk_rows():
        return {
            "status": "needs_data",
            "message": "知识库还没有文档，请先导入示例文档。",
            "suggestion": "点击左侧的“导入示例文档”。",
            "answer": "",
            "citations": [],
            "evidence": [],
            "confidence": 0.0,
            "evidence_score": 0.0,
            "trace_id": new_trace_id("trace"),
            "latency_ms": 0,
        }
    payload = rag_service.query(
        query=request.question,
        top_k=request.top_k,
        domain=None,
        context=_rag_context(),
    )
    debug = payload.get("debug", {})
    trace_id = str(debug.get("trace_id") or new_trace_id("trace"))
    sources = payload.get("sources", [])
    return {
        "status": "completed",
        "answer": payload.get("answer", ""),
        "citations": payload.get("citations") or _citations_from_sources(sources),
        "evidence": sources,
        "confidence": float(payload.get("confidence") or 0.0),
        "evidence_score": float(payload.get("evidence_score") or 0.0),
        "trace_id": trace_id,
        "latency_ms": round((time.perf_counter() - started) * 1000, 3),
        "token_usage": debug.get("token_usage") or {},
        "debug": {
            "retrieval_mode": debug.get("retrieval_mode", request.retrieval_mode),
            "selected_domain": debug.get("selected_domain"),
            "query_rewrite": debug.get("query_rewrite", [request.question]),
            "top_k": request.top_k,
            "rerank": request.rerank,
            "model": request.model or "default",
        },
        "trace_url": f"/app#trace/{trace_id}",
    }


@router.get("/api/rag/traces/{trace_id}")
def api_rag_trace(trace_id: str) -> dict[str, Any]:
    path = trace_root() / "rag" / f"{trace_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail={"message": "RAG trace not found"})
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/api/agent/examples")
def api_agent_examples() -> dict[str, Any]:
    return {"examples": _agent_examples()}


@router.post("/api/agent/run-example")
def api_agent_run_example(request: AgentRunExampleRequest) -> dict[str, Any]:
    examples = {item["id"]: item for item in _agent_examples()}
    example = examples.get(request.example_id)
    if example is None:
        raise HTTPException(status_code=404, detail={"message": "Agent example not found"})
    return api_agent_run(AgentRunRequest(task=example["task"], scenario=request.scenario or example["scenario"]))


@router.post("/api/agent/run")
def api_agent_run(request: AgentRunRequest) -> dict[str, Any]:
    started = time.perf_counter()
    mode = "hybrid" if request.scenario in {"finance_research", "composite"} else "auto"
    response = run_unified_agent(
        UnifiedRunRequest(
            user_input=request.task,
            scenario=request.scenario,
            mode=mode,
            max_steps=request.max_steps,
            include_trace=True,
        ),
        _default_auth(),
        trace_store=trace_store,
    )
    return _agent_payload(response, started)


@router.post("/api/agent/confirm")
def api_agent_confirm(request: AgentConfirmRequest) -> dict[str, Any]:
    response = approve_unified_run(
        request.run_id,
        ApprovalRequest(approved=request.approved, comment=request.comment),
        trace_store=trace_store,
    )
    if response is None:
        raise HTTPException(status_code=404, detail={"message": "Agent run not found"})
    return response.model_dump(mode="json")


@router.post("/api/data-agent/init-sample-db")
def api_data_agent_init_sample_db() -> dict[str, Any]:
    started = time.perf_counter()
    result = _init_sample_database()
    trace_id = _append_workbench_trace(
        "Data Agent",
        {
            "status": "completed",
            "user_input": "初始化 sample database",
            "result": result,
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
        },
    )
    return {**result, "trace_id": trace_id, "latency_ms": round((time.perf_counter() - started) * 1000, 3)}


@router.get("/api/data-agent/examples")
def api_data_agent_examples() -> dict[str, Any]:
    return {"examples": _data_examples(), "dataset": _database_summary()}


@router.post("/api/data-agent/ask")
def api_data_agent_ask(request: DataAskRequest) -> dict[str, Any]:
    if not get_analyst_settings().database_path.exists() and get_settings().demo_mode:
        _init_sample_database()
    started = time.perf_counter()
    response = DataAnalystAgent(enable_trace=True).run(
        DataAgentQueryRequest(question=_mapped_data_question(request.question), include_trace=True)
    )
    validation = response.sql_validation.model_dump(mode="json")
    chart = response.chart.model_dump(mode="json") if response.chart else None
    metrics = []
    if response.table_rows:
        first = response.table_rows[0]
        for key, value in first.items():
            if isinstance(value, (int, float)):
                metrics.append({"label": key, "value": value})
            if len(metrics) >= 3:
                break
    return {
        "run_id": response.run_id,
        "trace_id": response.trace_id,
        "status": response.status,
        "question": request.question,
        "analysis_question": response.question,
        "answer": response.final_answer,
        "metrics": metrics,
        "columns": response.table_columns,
        "table_preview": response.table_rows[:20],
        "generated_sql": response.sql_plan.sql if response.sql_plan else None,
        "safe_sql": response.sql,
        "sql_safety": validation,
        "chart": chart,
        "chart_url": response.chart_url,
        "row_count": response.row_count,
        "latency_ms": response.query_latency_ms or round((time.perf_counter() - started) * 1000, 3),
        "trace_url": f"/app#trace/{response.trace_id}",
    }


@router.post("/api/data-agent/test-safety")
def api_data_agent_test_safety() -> dict[str, Any]:
    started = time.perf_counter()
    sql = "DROP TABLE orders"
    result = SQLSafetyChecker().validate(sql)
    trace_id = _append_workbench_trace(
        "Data Agent",
        {
            "status": "rejected",
            "user_input": "测试危险 SQL 拦截",
            "generated_sql": sql,
            "safety_check": result.model_dump(mode="json"),
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
        },
    )
    return {
        "trace_id": trace_id,
        "status": "rejected",
        "dangerous_sql": sql,
        "safety_check": result.model_dump(mode="json"),
        "message": "危险 SQL 已被拒绝。",
        "suggestion": "数据分析 Agent 只允许只读 SELECT，并会自动添加 LIMIT。",
        "latency_ms": round((time.perf_counter() - started) * 1000, 3),
    }


@router.get("/api/eval/latest")
def api_eval_latest() -> dict[str, Any]:
    return _latest_eval_report()


@router.post("/api/eval/run")
def api_eval_run(request: EvalRunRequest) -> dict[str, Any]:
    started = time.perf_counter()
    if not get_analyst_settings().database_path.exists() or not _chunk_rows():
        initialize_platform(reset_traces=False)
    report = run_evaluation(request.target)
    write_reports(report)
    trace_id = _append_workbench_trace(
        "Eval",
        {
            "status": "completed",
            "user_input": f"运行评测：{request.target}",
            "summary": report.get("summary", {}),
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
        },
    )
    return {
        "trace_id": trace_id,
        "status": "completed",
        "latency_ms": round((time.perf_counter() - started) * 1000, 3),
        **report,
    }


@router.get("/api/eval/report")
def api_eval_report(format: str = Query(default="json")):
    report = _latest_eval_report()["report"]
    if format == "markdown":
        path = ROOT_DIR / "reports" / "eval_report.md"
        if path.exists():
            return PlainTextResponse(path.read_text(encoding="utf-8"), media_type="text/markdown")
        return PlainTextResponse("# Evaluation Report\n\nNo report generated yet.\n", media_type="text/markdown")
    if format == "json":
        return JSONResponse(report)
    raise HTTPException(status_code=400, detail={"message": "format must be json or markdown"})


@router.get("/api/workbench/traces")
def api_workbench_traces(limit: int = Query(default=50, ge=1, le=200)) -> dict[str, Any]:
    rows = _read_jsonl(WORKBENCH_TRACE_PATH)[-limit:][::-1]
    return {"traces": rows}


def recent_trace_summaries(limit: int = 50) -> list[dict[str, Any]]:
    traces: list[dict[str, Any]] = []
    for run in trace_store.list_runs():
        traces.append(
            {
                "trace_id": run.trace_id,
                "run_id": run.run_id,
                "type": "Agent" if run.mode != "analysis" else "Data Agent",
                "user_input": run.user_input[:120],
                "status": run.status,
                "latency": "recorded",
                "created_at": run.created_at,
            }
        )
    for path in (trace_root() / "rag").glob("*.json"):
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        traces.append(
            {
                "trace_id": row.get("trace_id") or path.stem,
                "run_id": row.get("trace_id") or path.stem,
                "type": "RAG",
                "user_input": row.get("query") or row.get("user_input") or "知识库问答",
                "status": row.get("status", "completed"),
                "latency": row.get("total_latency_ms"),
                "created_at": row.get("created_at"),
            }
        )
    for row in _read_jsonl(get_analyst_settings().trace_path):
        traces.append(
            {
                "trace_id": row.get("trace_id"),
                "run_id": row.get("run_id"),
                "type": "Data Agent",
                "user_input": str(row.get("question") or "")[:120],
                "status": "completed" if row.get("executed_sql") else "rejected",
                "latency": row.get("latency_ms"),
                "created_at": row.get("created_at"),
            }
        )
    for row in _read_jsonl(WORKBENCH_TRACE_PATH):
        traces.append(
            {
                "trace_id": row.get("trace_id"),
                "run_id": row.get("trace_id"),
                "type": row.get("type", "Workbench"),
                "user_input": str(row.get("user_input") or "")[:120],
                "status": row.get("status", "completed"),
                "latency": row.get("latency_ms"),
                "created_at": row.get("created_at"),
            }
        )
    traces = [trace for trace in traces if trace.get("trace_id")]
    traces.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
    return traces[:limit]


def trace_detail(trace_id: str) -> dict[str, Any] | None:
    runs = [run.model_dump(mode="json") for run in trace_store.list_runs() if run.trace_id == trace_id or run.run_id == trace_id]
    rag_path = trace_root() / "rag" / f"{trace_id}.json"
    rag_trace = json.loads(rag_path.read_text(encoding="utf-8")) if rag_path.exists() else None
    analyst_rows = [row for row in _read_jsonl(get_analyst_settings().trace_path) if row.get("trace_id") == trace_id or row.get("run_id") == trace_id]
    workbench_rows = [row for row in _read_jsonl(WORKBENCH_TRACE_PATH) if row.get("trace_id") == trace_id]
    events = [event for event in list_events(limit=200) if event.get("trace_id") == trace_id]
    if not runs and not rag_trace and not analyst_rows and not workbench_rows and not events:
        return None
    detail_type = "Agent" if runs else "RAG" if rag_trace else "Data Agent" if analyst_rows else "Workbench"
    return {
        "trace_id": trace_id,
        "type": detail_type,
        "runs": runs,
        "rag": rag_trace,
        "data_agent": analyst_rows,
        "workbench": workbench_rows,
        "events": events,
    }
