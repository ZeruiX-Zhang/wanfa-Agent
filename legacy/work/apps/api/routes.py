from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, HTMLResponse

from analyst_core.service import run_analysis
from guardrails.service import GuardrailService
from platform_common.auth import require_auth
from platform_common.models import (
    AnalysisQueryRequest,
    ApprovalRequest,
    ApprovalResponse,
    AuthContext,
    HealthResponse,
    RagQueryRequest,
    RagQueryResponse,
    RunStep,
    SourceRef,
    UnifiedRunRequest,
    UnifiedRunResponse,
    UnifiedRunTrace,
)
from platform_common.settings import get_settings
from platform_common.traces import UnifiedTraceStore, new_trace_id
from rag_core.rag.service import RequestContext, rag_service
from workflow_core.unified_service import approve_unified_run, run_unified_agent


router = APIRouter()
trace_store = UnifiedTraceStore()
guardrails = GuardrailService()
settings = get_settings()


def _trace_url(run_id: str) -> str:
    return f"/api/v1/runs/{run_id}"


def _guardrail_safety(decisions: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "guardrails": decisions,
        "tool_whitelist_enabled": True,
        "write_tools_require_approval": ["create_ticket", "notify_human_agent"],
        "shell_execution_allowed": False,
    }


def _normalize_sources(items: list[dict[str, Any]]) -> list[SourceRef]:
    sources: list[SourceRef] = []
    for item in items:
        sources.append(
            SourceRef(
                title=str(item.get("title") or item.get("source") or item.get("document_id") or "source"),
                snippet=item.get("text") or item.get("snippet"),
                url=item.get("url"),
                document_id=item.get("document_id"),
                chunk_id=item.get("chunk_id"),
                score=float(item["score"]) if item.get("score") is not None else None,
                domain=item.get("domain"),
            )
        )
    return sources


@router.get(
    "/health",
    response_model=HealthResponse,
    tags=["系统"],
    summary="统一平台健康检查",
    description="返回统一平台主入口的健康状态、版本和 trace 存储位置。",
)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=settings.api_name,
        version="1.0.0",
        trace_store=str(settings.unified_trace_path),
    )


@router.get(
    "/demo",
    response_class=HTMLResponse,
    tags=["系统"],
    summary="查看统一演示页",
    description="展示统一平台的四条核心演示链路和快速访问链接。",
)
def demo() -> HTMLResponse:
    html = """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>统一 AI Workflow 平台</title>
  <style>
    body { margin: 0; font-family: "Segoe UI", Arial, sans-serif; background: #f5f7fb; color: #142033; }
    header { padding: 40px 28px 28px; background: linear-gradient(135deg, #103f91, #16726d); color: white; }
    main { max-width: 1080px; margin: 0 auto; padding: 28px; }
    section { background: white; border: 1px solid #dbe3f0; border-radius: 10px; padding: 20px; margin-bottom: 16px; }
    h1 { margin: 0 0 10px; font-size: 34px; }
    h2 { margin: 0 0 12px; font-size: 22px; }
    p, li { line-height: 1.65; }
    code, pre { background: #eef3fb; border-radius: 6px; }
    code { padding: 2px 5px; }
    pre { padding: 14px; overflow: auto; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }
    .card { border: 1px solid #dbe3f0; border-radius: 8px; padding: 14px; background: #fdfefe; }
    a { color: #0b57d0; text-decoration: none; }
  </style>
</head>
<body>
  <header>
    <h1>统一 AI Workflow 平台</h1>
    <p>一个统一的 FastAPI 公网入口，承载 RAG、工作流编排、结构化分析、审批、Guardrails 和 Trace 回放。</p>
  </header>
  <main>
    <section>
      <h2>统一公开接口</h2>
      <ul>
        <li><code>POST /api/v1/rag/query</code>：知识检索问答，返回 sources。</li>
        <li><code>POST /api/v1/rag/debug</code>：查看 Domain Router、Hybrid Retrieval、Reranker 调试细节。</li>
        <li><code>POST /api/v1/rag/documents/upload</code>：上传单篇文档并写入知识库。</li>
        <li><code>POST /api/v1/rag/eval/retrieval</code>：运行检索命中评测。</li>
        <li><code>POST /api/v1/agent/run</code>：统一多场景工作流入口。</li>
        <li><code>POST /api/v1/analysis/query</code>：直接调用结构化数据分析能力。</li>
        <li><code>GET /api/v1/runs/{run_id}</code>：统一 trace 查询。</li>
      </ul>
    </section>
    <section>
      <h2>演示链路</h2>
      <div class="grid">
        <div class="card"><strong>1. 客服 RAG</strong><p>查询 SLA、退款规则，并查看引用来源。</p></div>
        <div class="card"><strong>2. 财务 Hybrid</strong><p>把知识检索结果和结构化指标分析、图表产物合并输出。</p></div>
        <div class="card"><strong>3. 运维审批</strong><p>触发升级流程，并验证写操作需要审批。</p></div>
        <div class="card"><strong>4. 直接数据分析</strong><p>对演示数仓执行只读 Text-to-SQL 分析。</p></div>
      </div>
    </section>
    <section>
      <h2>快速入口</h2>
      <ul>
        <li><a href="/docs">Swagger 文档</a></li>
        <li><a href="/redoc">ReDoc 文档</a></li>
        <li><a href="/openapi.json">OpenAPI JSON</a></li>
      </ul>
    </section>
    <section>
      <h2>示例请求</h2>
      <pre>curl -X POST http://127.0.0.1:8000/api/v1/agent/run \\
  -H "X-API-Key: change-me" \\
  -H "Content-Type: application/json" \\
  -d '{"user_input":"请总结 2025 年季度营收趋势，并给出引用来源。","mode":"hybrid"}'</pre>
    </section>
  </main>
</body>
</html>
"""
    return HTMLResponse(html)


@router.get(
    "/artifacts/charts/{filename}",
    response_class=FileResponse,
    tags=["系统产物"],
    summary="访问分析图表产物",
    description="根据图表文件名读取结构化分析阶段生成的 PNG 图表。",
)
def get_chart(filename: str) -> FileResponse:
    if not re.fullmatch(r"[A-Za-z0-9_-]+\.png", filename):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chart not found")
    path = settings.analyst_chart_dir / filename
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chart not found")
    return FileResponse(path, media_type="image/png")


@router.post(
    "/api/v1/rag/query",
    response_model=RagQueryResponse,
    tags=["知识库问答"],
    summary="执行 RAG 问答",
    description="按业务域检索知识库片段，生成答案，并返回 citations 与调试信息。",
)
def rag_query(request: RagQueryRequest, auth: AuthContext = Depends(require_auth)) -> RagQueryResponse:
    run_id = new_trace_id("run")
    trace_id = new_trace_id("trace")
    decisions = [guardrails.check_request(request.question).model_dump()]
    if decisions[0]["decision"] == "block":
        trace = UnifiedRunTrace(
            run_id=run_id,
            trace_id=trace_id,
            user_input=request.question,
            scenario="unsafe_request",
            mode="knowledge",
            status="rejected",
            final_answer=decisions[0]["reason"],
            auth_context=auth,
            sources=[],
            guardrails=decisions,
            safety=_guardrail_safety(decisions),
        )
        trace_store.save(trace)
        return RagQueryResponse(
            run_id=run_id,
            trace_id=trace_id,
            answer=trace.final_answer,
            sources=[],
            trace_url=_trace_url(run_id) if request.include_trace else None,
            safety=trace.safety,
            debug={},
        )

    payload = rag_service.query(
        query=request.question,
        top_k=request.top_k,
        domain=None if request.domain == "auto" else request.domain,
        context=RequestContext(user_id=auth.user_id, tenant_id=auth.tenant_id, roles=auth.roles),
    )
    output_decision, answer = guardrails.check_output(str(payload.get("answer") or ""))
    decisions.append(output_decision.model_dump())
    sources = _normalize_sources(payload.get("sources", []))
    step = RunStep(
        name="rag_query",
        status="success",
        args={"domain": request.domain, "top_k": request.top_k},
        result={"source_count": len(sources)},
    )
    trace = UnifiedRunTrace(
        run_id=run_id,
        trace_id=trace_id,
        user_input=request.question,
        scenario=str(payload.get("debug", {}).get("selected_domain") or request.domain),
        mode="knowledge",
        status="completed",
        final_answer=answer,
        auth_context=auth,
        sources=sources,
        tool_steps=[step],
        guardrails=decisions,
        safety=_guardrail_safety(decisions),
        metadata={"debug": payload.get("debug", {})},
    )
    trace_store.save(trace)
    return RagQueryResponse(
        run_id=run_id,
        trace_id=trace_id,
        answer=answer,
        sources=sources,
        trace_url=_trace_url(run_id) if request.include_trace else None,
        safety=trace.safety,
        debug=payload.get("debug", {}),
    )


@router.post(
    "/api/v1/analysis/query",
    response_model=UnifiedRunResponse,
    tags=["数据分析"],
    summary="执行结构化数据分析",
    description="调用 analyst_core 完成只读 SQL 生成、执行、图表产物生成和统一 trace 记录。",
)
def analysis_query(request: AnalysisQueryRequest, auth: AuthContext = Depends(require_auth)) -> UnifiedRunResponse:
    run_id = new_trace_id("run")
    trace_id = new_trace_id("trace")
    decisions = [guardrails.check_request(request.question).model_dump()]
    if decisions[0]["decision"] == "block":
        trace = UnifiedRunTrace(
            run_id=run_id,
            trace_id=trace_id,
            user_input=request.question,
            scenario="unsafe_request",
            mode="analysis",
            status="rejected",
            final_answer=decisions[0]["reason"],
            auth_context=auth,
            sources=[],
            guardrails=decisions,
            safety=_guardrail_safety(decisions),
        )
        trace_store.save(trace)
        return UnifiedRunResponse(
            run_id=run_id,
            trace_id=trace_id,
            status="rejected",
            scenario="unsafe_request",
            mode="analysis",
            final_answer=decisions[0]["reason"],
            sources=[],
            data_artifacts=[],
            pending_action=None,
            trace_url=_trace_url(run_id) if request.include_trace else None,
            safety=trace.safety,
            tool_steps=[],
        )

    result = run_analysis(request.question, include_trace=False, enable_internal_trace=False)
    output_decision, answer = guardrails.check_output(result.final_answer)
    decisions.append(output_decision.model_dump())
    step = RunStep(
        name="run_structured_analysis",
        status="success" if result.status == "completed" else "error",
        args={"question": request.question},
        result={"row_count": result.row_count, "sql": result.sql},
    )
    response_status = "completed" if result.status == "completed" else "failed"
    trace = UnifiedRunTrace(
        run_id=run_id,
        trace_id=trace_id,
        user_input=request.question,
        scenario="data_analysis",
        mode="analysis",
        status=response_status,
        final_answer=answer,
        auth_context=auth,
        sources=[],
        data_artifacts=[artifact.model_dump() for artifact in result.data_artifacts],
        tool_steps=[step],
        guardrails=decisions,
        safety=_guardrail_safety(decisions),
        metadata={"sql": result.sql, "analysis_trace_id": result.trace_id},
    )
    trace_store.save(trace)
    return UnifiedRunResponse(
        run_id=run_id,
        trace_id=trace_id,
        status=response_status,
        scenario="data_analysis",
        mode="analysis",
        final_answer=answer,
        sources=[],
        data_artifacts=trace.data_artifacts,
        pending_action=None,
        trace_url=_trace_url(run_id) if request.include_trace else None,
        safety=trace.safety,
        tool_steps=[step],
    )


@router.post(
    "/api/v1/agent/run",
    response_model=UnifiedRunResponse,
    tags=["统一工作流"],
    summary="运行统一工作流",
    description="统一多场景入口，可自动在知识检索、结构化分析和审批流之间编排执行。",
)
def agent_run(request: UnifiedRunRequest, auth: AuthContext = Depends(require_auth)) -> UnifiedRunResponse:
    return run_unified_agent(request=request, auth_context=auth, trace_store=trace_store, guardrail_service=guardrails)


@router.post(
    "/api/v1/agent/approve/{run_id}",
    response_model=ApprovalResponse,
    tags=["统一工作流"],
    summary="审批待执行写操作",
    description="对 `waiting_approval` 状态的 run 进行批准或拒绝。",
)
def agent_approve(
    run_id: str,
    request: ApprovalRequest,
    auth: AuthContext = Depends(require_auth),
) -> ApprovalResponse:
    del auth
    result = approve_unified_run(run_id, request, trace_store=trace_store, guardrail_service=guardrails)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run_id not found")
    return result


@router.get(
    "/api/v1/runs/{run_id}",
    response_model=UnifiedRunTrace,
    tags=["运行追踪"],
    summary="查询统一运行轨迹",
    description="读取统一 trace，查看 sources、工具步骤、审批状态和安全决策。",
)
def get_run(run_id: str, auth: AuthContext = Depends(require_auth)) -> UnifiedRunTrace:
    del auth
    trace = trace_store.get(run_id)
    if trace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run_id not found")
    return trace
