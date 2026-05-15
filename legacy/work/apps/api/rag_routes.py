from __future__ import annotations

import json
import re
from pathlib import Path
from time import perf_counter
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, ValidationError

from platform_common.auth import require_auth
from platform_common.models import AuthContext, HealthResponse
from platform_common.settings import get_settings
from rag_core.agent.tools import tool_registry
from rag_core.agent.trace import record_agent_run
from rag_core.eval.evaluator import (
    compare_retrieval_modes,
    load_eval_run,
    run_generation_eval,
    run_retrieval_eval,
)
from rag_core.observability.tracing import trace_root
from rag_core.rag.ingestion_jobs import ingestion_jobs
from rag_core.rag.models import Chunk
from rag_core.rag.embedding import tokenize
from rag_core.rag.service import RequestContext, rag_service
from rag_core.rag.settings import env_str, rag_storage_dir
from rag_core.security.path_guard import PathGuardError


router = APIRouter()
settings = get_settings()


class RagHealthReadyResponse(BaseModel):
    status: str = Field(description="依赖状态。`ok` 表示 RAG 存储目录已经可用。")
    vector_backend: str = Field(description="当前检索后端，例如 `faiss` 或 `pgvector`。")
    rag_storage: str = Field(description="RAG 本地索引目录。")
    writable: bool = Field(description="索引目录是否存在且可写。")


class RagDebugRequest(BaseModel):
    question: str = Field(description="待检索问题。")
    domain: str = Field(default="auto", description="业务域；`auto` 表示自动路由。")
    top_k: int = Field(default=5, ge=1, le=20, description="最终返回的候选片段数量。")


class RagDebugResponse(BaseModel):
    query_id: str | None = None
    trace_id: str | None = None
    selected_domain: str | None = None
    router_confidence: float = 0.0
    retrieval_mode: str | None = None
    requested_top_k: int | None = None
    candidate_k: int | None = None
    before_filter_count: int | None = None
    after_filter_count: int | None = None
    dense_latency_ms: float = 0.0
    bm25_latency_ms: float = 0.0
    fusion_latency_ms: float = 0.0
    reranker_latency_ms: float = 0.0
    total_latency_ms: float = 0.0
    contextual_text_used: bool = False
    dense_results: list[dict[str, Any]] = Field(default_factory=list)
    bm25_results: list[dict[str, Any]] = Field(default_factory=list)
    fused_results: list[dict[str, Any]] = Field(default_factory=list)
    reranked_results: list[dict[str, Any]] = Field(default_factory=list)
    results: list[dict[str, Any]] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(default_factory=list)


class RagDocumentUploadRequest(BaseModel):
    filename: str = Field(description="上传的文件名，不能带目录。")
    content: str = Field(description="文档正文。支持 Markdown、TXT 或 CSV 文本。")
    domain: str | None = Field(default=None, description="文档所属业务域；为空时自动推断。")
    build_index: bool = Field(default=True, description="是否立刻写入 RAG 索引。")
    replace: bool = Field(default=False, description="是否替换同 document_id 的既有 chunk。")
    doc_type: str = Field(default="kb", description="文档类型，默认 `kb`。")


class RagDocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    domain: str
    chunks_created: int
    embeddings_created: int
    indexed: bool


class RagIngestLocalRequest(BaseModel):
    domain: str | None = Field(default=None, description="导入文档所属业务域。")
    directory: str | None = Field(default=None, description="待导入目录，例如 `data/raw/customer_support`。")
    path: str | None = Field(default=None, description="兼容字段，等价于 `directory`。")
    glob_pattern: str = Field(default="**/*", description="文件匹配模式。")
    replace: bool = Field(default=False, description="是否覆盖现有索引。")
    doc_type: str = Field(default="kb", description="文档类型，默认 `kb`。")


class RagIngestionJobResponse(BaseModel):
    id: str
    status: str
    documents_loaded: int = 0
    chunks_created: int = 0
    embeddings_created: int = 0
    error_message: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    request: dict[str, Any] = Field(default_factory=dict)


class RagAgentRunRequest(BaseModel):
    user_input: str | None = Field(default=None, description="用户任务描述。")
    tool: str | None = Field(default=None, description="显式指定工具名。")
    name: str | None = Field(default=None, description="兼容字段，等价于 `tool`。")
    args: dict[str, Any] | None = Field(default=None, description="工具参数。")
    question: str | None = Field(default=None, description="兼容的检索问题字段。")
    query: str | None = Field(default=None, description="兼容的检索 query 字段。")
    domain: str | None = Field(default=None, description="业务域。")
    top_k: int | None = Field(default=None, description="知识检索返回片段数。")
    path: str | None = Field(default=None, description="文件读取工具的目标路径。")
    max_steps: int = Field(default=4, ge=1, le=20, description="当前保留字段，用于兼容旧版 Agent。")


class RagAgentRunResponse(BaseModel):
    run_id: str
    trace_id: str
    tool: str
    selected_tool: str
    selected_tools: list[str] = Field(default_factory=list)
    tool_call: dict[str, Any] = Field(default_factory=dict)
    tool_args: dict[str, Any] = Field(default_factory=dict)
    tool_result: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    final_answer: str
    steps: list[dict[str, Any]] = Field(default_factory=list)
    trace: dict[str, Any] = Field(default_factory=dict)
    latency_ms: float = 0.0
    answer: str | None = None
    content: str | None = None
    sources: list[dict[str, Any]] = Field(default_factory=list)


class RagAgentTraceResponse(BaseModel):
    run_id: str | None = None
    trace_id: str
    user_input: str | None = None
    created_at: str | None = None
    finished_at: str | None = None
    selected_workflow: str | None = None
    selected_tool: str | None = None
    selected_tools: list[str] = Field(default_factory=list)
    steps: list[dict[str, Any]] = Field(default_factory=list)
    tool_args: dict[str, Any] = Field(default_factory=dict)
    tool_result: dict[str, Any] = Field(default_factory=dict)
    tool_result_summary: str | None = None
    tool_latency_ms: float | None = None
    latency_ms: float | None = None
    final_answer: str | None = None


class RagEvalCase(BaseModel):
    query: str | None = None
    question: str | None = None
    domain: str | None = None
    top_k: int = 5
    expected_chunk_id: str | None = None
    expected_domain: str | None = None
    expected_source: str | None = None
    expected_filename: str | None = None
    keywords: list[str] = Field(default_factory=list)
    answer: str | None = None
    expected_keywords: list[str] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(default_factory=list)


class RagEvalRunRequest(BaseModel):
    cases: list[RagEvalCase] = Field(default_factory=list, description="评测样本列表。")
    run_type: str = Field(default="retrieval", description="可选 `retrieval`、`generation`、`compare`。")
    eval_file: str | None = Field(default=None, description="`data/eval/` 下的 JSONL 文件名。")
    domain: str | None = Field(default=None, description="整批评测默认业务域。")


class RagEvalRunResponse(BaseModel):
    eval_run_id: str
    run_type: str
    domain: str | None = None
    total: int | None = None
    total_questions: int | None = None
    hit_rate: float | None = None
    mrr: float | None = None
    average_rank: float | None = None
    results: list[dict[str, Any]] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    details: dict[str, Any] = Field(default_factory=dict)


def _to_rag_context(auth: AuthContext) -> RequestContext:
    return RequestContext(user_id=auth.user_id, tenant_id=auth.tenant_id, roles=auth.roles)


def _rag_query_text(question: str | None, query: str | None) -> str:
    return (query or question or "").strip()


def _rag_domain(domain: str | None) -> str | None:
    if domain is None:
        return None
    cleaned = domain.strip()
    if not cleaned or cleaned.lower() == "auto":
        return None
    return cleaned


def _agent_result_summary(result: dict[str, Any]) -> str:
    summary = result.get("answer") or result.get("content") or result
    return str(summary)[:500]


def _unsafe_agent_reason(user_input: str, payload: RagAgentRunRequest) -> str | None:
    lowered = user_input.lower()
    tool_name = str(payload.tool or payload.name or "").lower()
    explicit_path = str(payload.path or (payload.args or {}).get("path") or "").lower() if payload.args else str(payload.path or "").lower()
    if ".env" in lowered or ".env" in explicit_path:
        return "敏感文件访问已被拒绝"
    asks_for_shell = any(keyword in lowered for keyword in ("shell", "powershell", "cmd", "命令", "执行"))
    asks_to_delete = any(keyword in lowered for keyword in ("删除", "delete", "remove", "erase", "rm "))
    if asks_for_shell and asks_to_delete:
        return "危险命令执行已被拒绝"
    if tool_name in {"shell", "exec", "execute_shell", "run_shell"}:
        return "Shell 工具不在白名单中"
    return None


def _select_agent_tool(payload: RagAgentRunRequest) -> tuple[str, dict[str, Any], str]:
    user_input = (payload.user_input or "").strip()
    tool_name = (payload.tool or payload.name or "").strip()
    raw_args = payload.args
    if not tool_name:
        lowered = user_input.lower()
        if any(keyword in lowered for keyword in ("csv", "sales_report", "data_analysis", "收入", "营收")):
            tool_name = "analyze_csv"
            raw_args = {"path": "data/raw/data_analysis/sales_report.csv", "column": "revenue"}
        else:
            tool_name = "search_knowledge_base"
    if raw_args is None:
        raw_args = {}
        if payload.query or payload.question or user_input:
            raw_args["query"] = _rag_query_text(payload.question, payload.query) or user_input
        if payload.domain is not None:
            raw_args["domain"] = payload.domain
        if payload.top_k is not None:
            raw_args["top_k"] = payload.top_k
        if payload.path is not None:
            raw_args["path"] = payload.path
    if not isinstance(raw_args, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="args 必须是 JSON object")
    args = dict(raw_args)
    if "question" in args and "query" not in args:
        args["query"] = args.pop("question")
    if tool_name in {"search_knowledge", "search_knowledge_base"} and "query" not in args and user_input:
        args["query"] = user_input
    if str(args.get("domain", "")).strip().lower() == "auto":
        args["domain"] = None
    return tool_name, args, user_input


def _agent_refusal_response(user_input: str, reason: str) -> RagAgentRunResponse:
    final_answer = f"已拒绝该请求：{reason}。"
    tool_result = {"refused": True, "reason": reason}
    step = {
        "index": 1,
        "selected_tool": "refuse",
        "tool_args": {"reason": reason},
        "tool_result": tool_result,
        "latency_ms": 0.0,
    }
    trace_id = record_agent_run(
        selected_workflow="safety_refusal",
        selected_tools=["refuse"],
        tool_args={"reason": reason},
        tool_result_summary=final_answer,
        tool_latency_ms=0.0,
        final_answer=final_answer,
        user_input=user_input[:200],
        tool_result=tool_result,
        steps=[step],
    )
    return RagAgentRunResponse(
        run_id=trace_id,
        trace_id=trace_id,
        tool="refuse",
        selected_tool="refuse",
        selected_tools=["refuse"],
        tool_call={"tool_name": "refuse", "args": {"reason": reason}},
        tool_args={"reason": reason},
        tool_result=tool_result,
        result=tool_result,
        final_answer=final_answer,
        steps=[step],
        trace={
            "run_id": trace_id,
            "trace_id": trace_id,
            "selected_tool": "refuse",
            "steps": [step],
            "latency_ms": 0.0,
        },
        latency_ms=0.0,
        answer=final_answer,
        sources=[],
    )


def _infer_upload_domain(filename: str) -> str:
    name = filename.lower()
    if any(keyword in name for keyword in ("support", "customer", "sla")):
        return "customer_support"
    if any(keyword in name for keyword in ("ops", "runbook")):
        return "ops_runbook"
    if any(keyword in name for keyword in ("legal", "contract", "msa")):
        return "legal_contract"
    if any(keyword in name for keyword in ("finance", "quarter", "revenue", "report")):
        return "finance_research"
    if "sales" in name or name.endswith(".csv"):
        return "data_analysis"
    return "enterprise_kb"


def _upload_chunk(
    *,
    document_id: str,
    filename: str,
    index: int,
    text: str,
    domain: str,
    tenant_id: str,
    access_roles: list[str],
    doc_type: str,
) -> Chunk:
    chunk_id = f"{document_id}:{index}"
    return Chunk(
        id=chunk_id,
        document_id=document_id,
        chunk_id=chunk_id,
        domain=domain,
        tenant_id=tenant_id,
        doc_type=doc_type,
        access_roles=access_roles,
        section_path=f"upload-paragraph-{index}",
        filename=filename,
        page=index,
        text=text,
        metadata={
            "tenant_id": tenant_id,
            "domain": domain,
            "access_roles": access_roles,
            "doc_id": document_id,
            "filename": filename,
            "page": index,
            "section": f"upload-paragraph-{index}",
            "chunk_index": index,
            "token_count": len(tokenize(text)),
            "source_path": filename,
            "status": "indexed",
        },
    )


@router.get(
    "/api/v1/rag/health/live",
    tags=["系统"],
    summary="RAG 进程存活检查",
    description="只检查 RAG 相关进程是否可响应请求，适合部署时作为 liveness probe。",
    response_model=HealthResponse,
)
def rag_health_live() -> HealthResponse:
    return HealthResponse(status="ok", service="RAG 子系统", version="1.0.0", trace_store=str(settings.trace_storage_dir))


@router.get(
    "/api/v1/rag/health/ready",
    tags=["系统"],
    summary="RAG 依赖就绪检查",
    description="检查索引目录是否可用，并返回当前启用的检索后端。",
    response_model=RagHealthReadyResponse,
)
def rag_health_ready() -> RagHealthReadyResponse:
    storage = rag_storage_dir()
    storage.mkdir(parents=True, exist_ok=True)
    return RagHealthReadyResponse(
        status="ok",
        vector_backend=env_str("VECTOR_BACKEND", "faiss"),
        rag_storage=str(storage),
        writable=storage.exists(),
    )


@router.post(
    "/api/v1/rag/debug",
    tags=["知识库问答"],
    summary="查看 RAG 检索调试信息",
    description="返回 Domain Router、Dense/BM25/Hybrid/Reranker 的候选结果与耗时信息，不额外包装为统一 workflow 响应。",
    response_model=RagDebugResponse,
)
def rag_debug(request: RagDebugRequest, auth: AuthContext = Depends(require_auth)) -> dict[str, Any]:
    return rag_service.debug_query(
        query=request.question,
        top_k=request.top_k,
        domain=_rag_domain(request.domain),
        context=_to_rag_context(auth),
    )


@router.post(
    "/api/v1/rag/agent/run",
    tags=["RAG Agent"],
    summary="运行轻量 RAG Agent",
    description="保留原 RAG demo 的轻量工具型 Agent 能力，用于知识检索、CSV 分析和安全拒答演示。",
    response_model=RagAgentRunResponse,
)
def rag_agent_run(request: RagAgentRunRequest, auth: AuthContext = Depends(require_auth)) -> RagAgentRunResponse:
    tool_name, args, user_input = _select_agent_tool(request)
    refusal_reason = _unsafe_agent_reason(user_input, request)
    if refusal_reason:
        return _agent_refusal_response(user_input, refusal_reason)
    try:
        start = perf_counter()
        result = tool_registry.run(tool_name, args, _to_rag_context(auth))
        latency_ms = round((perf_counter() - start) * 1000, 3)
        final_answer = _agent_result_summary(result)
        step = {
            "index": 1,
            "selected_tool": tool_name,
            "tool_args": args,
            "tool_result": result,
            "latency_ms": latency_ms,
        }
        trace_id = record_agent_run(
            selected_workflow="tool_call",
            selected_tools=[tool_name],
            tool_args=args,
            tool_result_summary=final_answer,
            tool_latency_ms=latency_ms,
            final_answer=final_answer,
            user_input=user_input,
            tool_result=result,
            steps=[step],
        )
        return RagAgentRunResponse(
            run_id=trace_id,
            trace_id=trace_id,
            tool=tool_name,
            selected_tool=tool_name,
            selected_tools=[tool_name],
            tool_call={"tool_name": tool_name, "args": args},
            tool_args=args,
            tool_result=result,
            result=result,
            final_answer=final_answer,
            steps=[step],
            trace={
                "run_id": trace_id,
                "trace_id": trace_id,
                "selected_tool": tool_name,
                "tool_args": args,
                "tool_result": result,
                "final_answer": final_answer,
                "steps": [step],
                "latency_ms": latency_ms,
            },
            latency_ms=latency_ms,
            answer=result.get("answer"),
            content=result.get("content"),
            sources=result.get("sources", []),
        )
    except PathGuardError:
        return _agent_refusal_response(user_input, "未授权路径访问")
    except (FileNotFoundError, ValueError, ValidationError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get(
    "/api/v1/rag/agent/runs/{run_id}",
    tags=["RAG Agent"],
    summary="查看轻量 RAG Agent 轨迹",
    description="读取 `storage/traces/agent/` 下保存的轻量 Agent 轨迹。",
    response_model=RagAgentTraceResponse,
)
def get_rag_agent_run(run_id: str, auth: AuthContext = Depends(require_auth)) -> dict[str, Any]:
    del auth
    path = trace_root() / "agent" / f"{run_id}.json"
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent run not found")
    return json.loads(path.read_text(encoding="utf-8"))


@router.post(
    "/api/v1/rag/documents/upload",
    tags=["文档入库"],
    summary="上传单篇文档并写入知识库",
    description="适合快速补一篇文档到当前 RAG 索引。系统会自动切段并写入统一存储。",
    response_model=RagDocumentUploadResponse,
)
def upload_document(
    request: RagDocumentUploadRequest,
    auth: AuthContext = Depends(require_auth),
) -> RagDocumentUploadResponse:
    filename = request.filename.strip()
    if not filename or Path(filename).name != filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="filename 必须是不带目录的文件名")
    content = request.content.strip()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="content 不能为空")
    context = _to_rag_context(auth)
    document_id = Path(filename).stem
    domain = request.domain or _infer_upload_domain(filename)
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", content) if part.strip()]
    chunks = [
        _upload_chunk(
            document_id=document_id,
            filename=filename,
            index=index,
            text=paragraph,
            domain=domain,
            tenant_id=context.tenant_id,
            access_roles=context.roles,
            doc_type=request.doc_type,
        )
        for index, paragraph in enumerate(paragraphs, start=1)
    ]
    stats = {"chunks_created": len(chunks), "embeddings_created": 0}
    if request.build_index:
        stats = rag_service.ingest_chunks(chunks, replace=request.replace)
    return RagDocumentUploadResponse(
        document_id=document_id,
        filename=filename,
        domain=domain,
        chunks_created=stats["chunks_created"],
        embeddings_created=stats["embeddings_created"],
        indexed=request.build_index,
    )


@router.post(
    "/api/v1/rag/documents/ingest-local",
    tags=["文档入库"],
    summary="导入本地目录到知识库",
    description="从本地目录批量导入文档；可同步执行，也可先创建后台任务再轮询状态。",
    response_model=RagIngestionJobResponse,
)
def ingest_local_documents(
    request: RagIngestLocalRequest,
    background_tasks: BackgroundTasks,
    sync: bool = Query(default=False, description="是否同步执行。true 适合本地调试。"),
    auth: AuthContext = Depends(require_auth),
) -> dict[str, Any]:
    job = ingestion_jobs.create(request.model_dump(exclude_none=True))
    if sync:
        job = ingestion_jobs.run_local(job.id, _to_rag_context(auth))
    else:
        background_tasks.add_task(ingestion_jobs.run_local, job.id, _to_rag_context(auth))
    return job.model_dump()


@router.get(
    "/api/v1/rag/documents/jobs/{job_id}",
    tags=["文档入库"],
    summary="查看导入任务状态",
    description="根据 job_id 查看目录导入任务的执行状态与统计信息。",
    response_model=RagIngestionJobResponse,
)
def get_ingestion_job(job_id: str, auth: AuthContext = Depends(require_auth)) -> dict[str, Any]:
    del auth
    job = ingestion_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingestion job not found")
    return job.model_dump()


@router.post(
    "/api/v1/rag/documents/jobs/{job_id}/cancel",
    tags=["文档入库"],
    summary="取消导入任务",
    description="取消尚未完成的本地导入任务。已经完成的任务会保留原状态。",
    response_model=RagIngestionJobResponse,
)
def cancel_ingestion_job(job_id: str, auth: AuthContext = Depends(require_auth)) -> dict[str, Any]:
    del auth
    job = ingestion_jobs.cancel(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingestion job not found")
    return job.model_dump()


@router.post(
    "/api/v1/rag/eval/run",
    tags=["RAG 评测"],
    summary="运行统一 RAG 评测",
    description="根据 `run_type` 选择执行 retrieval、generation 或 compare 三类评测。",
    response_model=RagEvalRunResponse,
)
def eval_run(request: RagEvalRunRequest, auth: AuthContext = Depends(require_auth)) -> dict[str, Any]:
    payload = request.model_dump(exclude_none=True)
    run_type = str(payload.get("run_type") or "retrieval").strip().lower()
    if run_type == "retrieval":
        return run_retrieval_eval(payload, context=_to_rag_context(auth))
    if run_type == "generation":
        return run_generation_eval(payload)
    if run_type == "compare":
        return compare_retrieval_modes(payload, context=_to_rag_context(auth))
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="run_type 必须是 retrieval、generation 或 compare")


@router.post(
    "/api/v1/rag/eval/retrieval",
    tags=["RAG 评测"],
    summary="运行检索命中评测",
    description="计算 hit_rate、MRR、average_rank，并返回每条样本的命中情况。",
    response_model=RagEvalRunResponse,
)
def eval_retrieval(request: RagEvalRunRequest, auth: AuthContext = Depends(require_auth)) -> dict[str, Any]:
    return run_retrieval_eval(request.model_dump(exclude_none=True), context=_to_rag_context(auth))


@router.post(
    "/api/v1/rag/eval/generation",
    tags=["RAG 评测"],
    summary="运行生成质量评测",
    description="计算 answer_relevancy、groundedness 和 citation_coverage 等轻量指标。",
    response_model=RagEvalRunResponse,
)
def eval_generation(request: RagEvalRunRequest, auth: AuthContext = Depends(require_auth)) -> dict[str, Any]:
    del auth
    return run_generation_eval(request.model_dump(exclude_none=True))


@router.post(
    "/api/v1/rag/eval/compare",
    tags=["RAG 评测"],
    summary="比较不同检索策略",
    description="对比 dense、hybrid、hybrid+rereanker 三类策略的检索效果。",
    response_model=RagEvalRunResponse,
)
def eval_compare(request: RagEvalRunRequest, auth: AuthContext = Depends(require_auth)) -> dict[str, Any]:
    return compare_retrieval_modes(request.model_dump(exclude_none=True), context=_to_rag_context(auth))


@router.get(
    "/api/v1/rag/eval/runs/{eval_run_id}",
    tags=["RAG 评测"],
    summary="查看历史评测结果",
    description="读取 `storage/eval_runs/` 下保存的离线评测结果。",
    response_model=RagEvalRunResponse,
)
def get_eval_run_result(eval_run_id: str, auth: AuthContext = Depends(require_auth)) -> dict[str, Any]:
    del auth
    run = load_eval_run(eval_run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Eval run not found")
    return run
