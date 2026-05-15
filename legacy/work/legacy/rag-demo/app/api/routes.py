from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from time import perf_counter

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import ValidationError

from app.agent.trace import record_agent_run
from app.agent.tools import tool_registry
from app.core.auth import require_auth
from app.rag.models import Chunk
from app.rag.service import rag_service
from app.rag.ingestion_jobs import ingestion_jobs
from app.security.output_sanitizer import sanitize_output
from app.security.path_guard import PathGuardError
from app.eval.evaluator import compare_retrieval_modes, load_eval_run, run_generation_eval, run_retrieval_eval
from app.observability.tracing import trace_root
from app.schemas.auth import AuthContext
from app.schemas.portfolio_api import (
    AgentRunRequest,
    AgentRunResponse,
    AgentRunTrace,
    DocumentUploadRequest,
    DocumentUploadResponse,
    EvalRunRequest,
    EvalRunResponse,
    HealthReadyResponse,
    HealthResponse,
    IngestLocalRequest,
    IngestLocalResponse,
    RagDebugResponse,
    RagQueryRequest,
    RagQueryResponse,
)


router = APIRouter()


def _rag_query_text(request: dict[str, object]) -> str:
    return str(request.get("query") or request.get("question") or "")


def _rag_domain(request: dict[str, object]) -> str | None:
    raw = request.get("domain")
    if raw is None:
        return None
    domain = str(raw).strip()
    if not domain or domain.lower() == "auto":
        return None
    return domain


def _model_payload(request: object) -> dict[str, object]:
    if isinstance(request, dict):
        return dict(request)
    if hasattr(request, "model_dump"):
        return request.model_dump(exclude_none=True)  # type: ignore[no-any-return]
    return {}


def _agent_result_summary(result: dict[str, object]) -> str:
    summary = result.get("answer") or result.get("content") or result
    return str(summary)[:500]


def _unsafe_agent_reason(user_input: str, payload: dict[str, object]) -> str | None:
    text = user_input.lower()
    tool_name = str(payload.get("tool") or payload.get("name") or "").lower()
    args = payload.get("args") if isinstance(payload.get("args"), dict) else {}
    explicit_path = str(payload.get("path") or args.get("path") or "").lower() if isinstance(args, dict) else ""
    if ".env" in text or ".env" in explicit_path:
        return "sensitive_file_access"
    asks_for_shell = any(keyword in text for keyword in ("shell", "powershell", "cmd", "命令", "执行"))
    asks_to_delete = any(keyword in text for keyword in ("删除", "delete", "remove", "del ", "rm ", "erase"))
    if asks_for_shell and asks_to_delete:
        return "shell_execution_not_allowed"
    if tool_name in {"shell", "exec", "execute_shell", "run_shell"}:
        return "shell_execution_not_allowed"
    return None


def _select_agent_tool(user_input: str, payload: dict[str, object]) -> tuple[str, dict[str, object]]:
    tool_name = str(payload.get("tool") or payload.get("name") or "").strip()
    raw_args = payload.get("args")
    if not tool_name:
        lowered = user_input.lower()
        if "csv" in lowered or "sales_report" in lowered or "data_analysis" in lowered or "收入" in user_input:
            tool_name = "analyze_csv"
            raw_args = {
                "path": "data/raw/data_analysis/sales_report.csv",
                "column": "revenue",
            }
        elif "知识库" in user_input or "来源" in user_input or "查询" in user_input:
            tool_name = "search_knowledge_base"
        else:
            tool_name = "search_knowledge_base"
    if raw_args is None:
        raw_args = {key: payload[key] for key in ("query", "question", "domain", "top_k", "path") if key in payload}
        if not raw_args and user_input:
            raw_args = {"query": user_input, "domain": payload.get("domain"), "top_k": payload.get("top_k", 5)}
    if not isinstance(raw_args, dict):
        raise HTTPException(status_code=400, detail="Agent args 必须是 JSON object。")
    args = dict(raw_args)
    if "question" in args and "query" not in args:
        args["query"] = args.pop("question")
    if tool_name in {"search_knowledge", "search_knowledge_base"} and "query" not in args and user_input:
        args["query"] = user_input
    if str(args.get("domain", "")).strip().lower() == "auto":
        args["domain"] = None
    return tool_name, args


def _agent_refusal_response(user_input: str, reason: str) -> dict[str, object]:
    final_answer = "已拒绝该请求：涉及危险操作或未授权访问。"
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
        user_input="sensitive or dangerous request redacted" if reason else sanitize_output(user_input),
        tool_result=tool_result,
        steps=[step],
    )
    return {
        "run_id": trace_id,
        "trace_id": trace_id,
        "tool": "refuse",
        "selected_tool": "refuse",
        "selected_tools": ["refuse"],
        "tool_call": {"tool_name": "refuse", "args": {"reason": reason}},
        "tool_args": {"reason": reason},
        "tool_result": tool_result,
        "result": tool_result,
        "final_answer": final_answer,
        "answer": final_answer,
        "steps": [step],
        "trace": {"run_id": trace_id, "trace_id": trace_id, "selected_tool": "refuse", "steps": [step], "latency_ms": 0.0},
        "latency_ms": 0.0,
    }


def _infer_upload_domain(filename: str) -> str:
    name = filename.lower()
    if "support" in name or "customer" in name or "sla" in name:
        return "customer_support"
    if "ops" in name or "runbook" in name:
        return "ops_runbook"
    if "legal" in name or "contract" in name or "msa" in name:
        return "legal_contract"
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
        metadata={"tenant_id": tenant_id, "domain": domain, "access_roles": access_roles},
    )


@router.get(
    "/health",
    tags=["健康检查"],
    summary="检查服务健康状态",
    description="返回服务是否存活。该接口不依赖 RAG 索引，适合用于本地演示或基础健康检查。",
    response_description="返回服务状态和服务名称。",
    response_model=HealthResponse,
    response_model_exclude_none=True,
)
def health() -> dict[str, str]:
    return {"status": "ok", "service": "rag-demo-core"}


@router.get(
    "/health/live",
    tags=["健康检查"],
    summary="检查进程存活",
    description="用于容器或部署平台的 liveness probe，只检查 FastAPI 进程是否可响应请求。",
    response_description="返回进程存活状态。",
    response_model=HealthResponse,
    response_model_exclude_none=True,
)
def health_live() -> dict[str, str]:
    return {"status": "ok"}


@router.get(
    "/health/ready",
    tags=["健康检查"],
    summary="检查依赖就绪状态",
    description="检查 RAG 存储目录是否可创建，并返回当前向量后端配置，适合 readiness probe。",
    response_description="返回依赖就绪状态、向量后端和存储目录信息。",
    response_model=HealthReadyResponse,
)
def health_ready() -> dict[str, object]:
    from app.rag.settings import env_str, rag_storage_dir

    storage = rag_storage_dir()
    storage.mkdir(parents=True, exist_ok=True)
    return {
        "status": "ok",
        "vector_backend": env_str("VECTOR_BACKEND", "faiss"),
        "rag_storage": str(storage),
        "writable": storage.exists(),
    }


@router.post(
    "/rag/debug",
    tags=["RAG 问答"],
    summary="查看 RAG 检索调试信息",
    description="""
执行一次 RAG 检索链路并返回详细调试信息，但不生成最终回答。

典型用途：

1. 查看 Domain Router 选择的 `selected_domain` 和 `router_confidence`。
2. 对比 Dense 向量检索、BM25、RRF 融合和 Reranker 的候选结果。
3. 检查 tenant_id、access_roles、domain 等过滤条件是否生效。
4. 获取 trace_id、latency 和 sources，便于面试讲解检索链路。
""",
    response_description="返回检索结果、路由结果、RRF/Reranker 调试信息和 trace_id。",
    response_model=RagDebugResponse,
    response_model_exclude_none=True,
)
def rag_debug(request: RagQueryRequest, auth: AuthContext = Depends(require_auth)) -> dict[str, object]:
    payload = _model_payload(request)
    return rag_service.debug_query(
        query=_rag_query_text(payload),
        top_k=int(payload.get("top_k", 5) or 5),
        domain=_rag_domain(payload),
        context=auth.to_rag_context(),
    )


@router.post(
    "/rag/query",
    tags=["RAG 问答"],
    summary="执行 RAG 问答",
    description="""
根据用户问题自动或显式选择业务域，执行混合检索、重排序和大模型回答。

典型流程：

1. 根据 `domain` 参数决定是否启用 Domain Router。
2. 从 FAISS / BM25 中召回候选 chunks。
3. 使用 RRF 融合 dense 和 BM25 结果。
4. 使用 Reranker 进行二次排序。
5. 拼接 context 调用 LLM 或本地 mock 回答器。
6. 返回答案、引用来源 sources 和调试信息。
""",
    response_description="返回答案、引用来源、业务域路由结果和调试信息。",
    response_model=RagQueryResponse,
    response_model_exclude_none=True,
)
def rag_query(request: RagQueryRequest, auth: AuthContext = Depends(require_auth)) -> dict[str, object]:
    payload = _model_payload(request)
    return rag_service.query(
        query=_rag_query_text(payload),
        top_k=int(payload.get("top_k", 5) or 5),
        domain=_rag_domain(payload),
        context=auth.to_rag_context(),
    )


@router.post(
    "/agent/run",
    tags=["Agent 执行"],
    summary="运行多工具 Agent",
    description="根据用户任务选择白名单工具执行，例如知识库搜索、CSV 分析、文档总结和安全计算。",
    response_description="返回 Agent 最终答案、工具调用步骤、trace_id 和耗时信息。",
    response_model=AgentRunResponse,
    response_model_exclude_none=True,
)
def agent_run(request: AgentRunRequest, auth: AuthContext = Depends(require_auth)) -> dict[str, object]:
    payload = _model_payload(request)
    user_input = str(payload.get("user_input") or "")
    refusal_reason = _unsafe_agent_reason(user_input, payload)
    if refusal_reason:
        return _agent_refusal_response(user_input, refusal_reason)
    tool_name, args = _select_agent_tool(user_input, payload)
    try:
        start = perf_counter()
        result = tool_registry.run(tool_name, args, auth.to_rag_context())
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
            user_input=sanitize_output(user_input),
            tool_result=result,
            steps=[step],
        )
        return {
            "run_id": trace_id,
            "trace_id": trace_id,
            "tool": tool_name,
            "selected_tool": tool_name,
            "selected_tools": [tool_name],
            "tool_call": {"tool_name": tool_name, "args": args},
            "tool_args": args,
            "tool_result": result,
            "result": result,
            "final_answer": final_answer,
            "steps": [step],
            "trace": {
                "run_id": trace_id,
                "trace_id": trace_id,
                "selected_tool": tool_name,
                "tool_args": args,
                "tool_result": result,
                "final_answer": final_answer,
                "steps": [step],
                "latency_ms": latency_ms,
            },
            "latency_ms": latency_ms,
            **result,
        }
    except PathGuardError:
        return _agent_refusal_response(user_input, "unauthorized_path")
    except (FileNotFoundError, ValueError, ValidationError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
@router.get(
    "/agent/runs/{run_id}",
    tags=["Agent 执行"],
    summary="查看 Agent 执行轨迹",
    description="根据 run_id 读取 Agent trace，展示工具选择、工具参数、执行耗时和最终输出摘要。",
    response_description="返回 Agent 执行轨迹。",
    response_model=AgentRunTrace,
    response_model_exclude_none=True,
)
def get_agent_run(run_id: str, auth: AuthContext = Depends(require_auth)) -> dict[str, object]:
    del auth
    path = trace_root() / "agent" / f"{run_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Agent run not found")
    return json.loads(path.read_text(encoding="utf-8"))


@router.post(
    "/documents/upload",
    tags=["文档管理"],
    summary="上传文档并写入知识库",
    description="接收文档文件名和文本内容，切分为 chunk，并按租户、角色和业务域写入当前 RAG 索引。",
    response_description="返回上传文档的业务域、chunk 数量和索引写入结果。",
    response_model=DocumentUploadResponse,
)
def upload_document(request: DocumentUploadRequest, auth: AuthContext = Depends(require_auth)) -> dict[str, object]:
    filename = request.filename.strip()
    if not filename or Path(filename).name != filename:
        raise HTTPException(status_code=400, detail="filename 必须是不包含路径的文件名。")
    content = request.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="content 不能为空。")
    context = auth.to_rag_context()
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
    return {
        "document_id": document_id,
        "filename": filename,
        "domain": domain,
        "chunks_created": stats["chunks_created"],
        "embeddings_created": stats["embeddings_created"],
        "indexed": request.build_index,
    }


@router.post(
    "/documents/ingest-local",
    tags=["文档管理"],
    summary="导入本地文档并构建索引",
    description="""
从本地目录导入文档，解析文本、切分 chunks，并写入当前 RAG 向量索引。

该接口适合面试演示前准备业务域知识库，例如客户支持 SLA、企业制度、运维手册、合同条款和数据分析资料。
使用 `sync=true` 时会同步执行并直接返回导入结果；默认异步创建后台任务。
""",
    response_description="返回文档导入任务状态、载入文档数、chunk 数和 embedding 数。",
    response_model=IngestLocalResponse,
)
def ingest_local_documents(
    request: IngestLocalRequest,
    background_tasks: BackgroundTasks,
    sync: bool = Query(default=False, description="是否同步执行导入任务。true 适合本地演示和测试。"),
    auth: AuthContext = Depends(require_auth),
) -> dict[str, object]:
    payload = _model_payload(request)
    job = ingestion_jobs.create(payload)
    context = auth.to_rag_context()
    if sync:
        job = ingestion_jobs.run_local(job.id, context)
    else:
        background_tasks.add_task(ingestion_jobs.run_local, job.id, context)
    return job.model_dump()


@router.get(
    "/documents/jobs/{job_id}",
    tags=["文档管理"],
    summary="查询文档导入任务",
    description="根据 job_id 查询本地文档导入任务的状态和统计信息。",
    response_description="返回文档导入任务详情。",
    response_model=IngestLocalResponse,
)
def get_ingestion_job(job_id: str, auth: AuthContext = Depends(require_auth)) -> dict[str, object]:
    del auth
    job = ingestion_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Ingestion job not found")
    return job.model_dump()


@router.post(
    "/documents/jobs/{job_id}/cancel",
    tags=["文档管理"],
    summary="取消文档导入任务",
    description="取消尚未完成的本地文档导入任务。已完成任务会保持原状态。",
    response_description="返回取消后的任务状态。",
    response_model=IngestLocalResponse,
)
def cancel_ingestion_job(job_id: str, auth: AuthContext = Depends(require_auth)) -> dict[str, object]:
    del auth
    job = ingestion_jobs.cancel(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Ingestion job not found")
    return job.model_dump()


@router.post(
    "/eval/run",
    tags=["评测"],
    summary="运行评测",
    description="根据 run_type 运行检索评测、生成评测或不同检索策略对比，返回评测指标和样本明细。",
    response_description="返回评测 run_id、评测类型、指标和样本明细。",
    response_model=EvalRunResponse,
)
def eval_run(request: EvalRunRequest, auth: AuthContext = Depends(require_auth)) -> dict[str, object]:
    payload = _model_payload(request)
    run_type = str(payload.get("run_type") or payload.get("type") or "retrieval").strip().lower()
    if run_type == "retrieval":
        return run_retrieval_eval(payload, context=auth.to_rag_context())
    if run_type == "generation":
        return run_generation_eval(payload)
    if run_type == "compare":
        return compare_retrieval_modes(payload, context=auth.to_rag_context())
    raise HTTPException(status_code=400, detail="run_type 必须是 retrieval、generation 或 compare。")


@router.post(
    "/eval/retrieval",
    tags=["评测"],
    summary="运行检索命中评测",
    description="""
批量执行检索评测，输出 hit_rate、MRR、average_rank、命中来源和每条样本结果。

评测样本可以直接通过 `cases` 传入；项目内置样例数据位于 `data/eval/*.jsonl`，便于面试时说明离线评测方法。
""",
    response_description="返回检索评测 run_id、指标和样本明细。",
    response_model=EvalRunResponse,
)
def eval_retrieval(request: EvalRunRequest, auth: AuthContext = Depends(require_auth)) -> dict[str, object]:
    return run_retrieval_eval(_model_payload(request), context=auth.to_rag_context())


@router.post(
    "/eval/generation",
    tags=["评测"],
    summary="运行 RAG 生成评测",
    description="""
批量评估 RAG 答案质量，计算 answer_relevancy、groundedness、citation_coverage 等指标。

当前实现支持轻量离线评测；RAGAS 未配置时会在返回结果中给出 skipped_reason。
""",
    response_description="返回生成评测 run_id、指标和样本明细。",
    response_model=EvalRunResponse,
)
def eval_generation(request: EvalRunRequest, auth: AuthContext = Depends(require_auth)) -> dict[str, object]:
    del auth
    return run_generation_eval(_model_payload(request))


@router.post(
    "/eval/compare",
    tags=["评测"],
    summary="比较不同检索策略效果",
    description="""
使用同一组评测样本比较 dense、hybrid、hybrid + Reranker 等检索策略。

返回结果会列出各策略的 hit_rate、MRR、average_rank 等指标，适合展示 Hybrid Retrieval、BM25、RRF 和 Reranker 的收益。
""",
    response_description="返回不同检索策略的对比指标。",
    response_model=EvalRunResponse,
)
def eval_compare(request: EvalRunRequest, auth: AuthContext = Depends(require_auth)) -> dict[str, object]:
    return compare_retrieval_modes(_model_payload(request), context=auth.to_rag_context())


@router.get(
    "/eval/runs/{eval_run_id}",
    tags=["评测"],
    summary="查看评测运行结果",
    description="根据 eval_run_id 读取保存在 storage/eval_runs/ 下的离线评测结果。",
    response_description="返回评测运行结果。",
    response_model=EvalRunResponse,
)
def get_eval_run(eval_run_id: str, auth: AuthContext = Depends(require_auth)) -> dict[str, object]:
    del auth
    run = load_eval_run(eval_run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Eval run not found")
    return run
