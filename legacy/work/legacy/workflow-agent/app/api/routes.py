from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse

from app.core.config import settings
from app.schemas.agent import (
    AgentApproveRequest,
    AgentApproveResponse,
    AgentRunRequest,
    AgentRunResponse,
    AgentTrace,
    HealthResponse,
    Ticket,
)
from app.security.auth import require_api_key
from app.tools.ticket_tool import get_ticket, list_tickets
from app.trace.store import TraceStore
from app.workflows.orchestrator import approve_run, run_agent


router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    tags=["健康检查"],
    summary="健康检查",
    description="返回服务状态和外部 RAG 配置地址，不泄露任何密钥。",
)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        name="多业务场景 Workflow Agent 演示系统",
        rag_base_url=settings.rag_base_url,
    )


@router.post(
    "/agent/run",
    response_model=AgentRunResponse,
    tags=["Workflow Agent"],
    summary="运行多业务场景 Workflow Agent",
    description="根据用户输入自动识别业务场景、选择 workflow、执行白名单工具，并在需要写操作时返回待审批动作。",
)
def run_agent_endpoint(
    request: AgentRunRequest,
    _: str = Depends(require_api_key),
) -> AgentRunResponse:
    return run_agent(request)


@router.post(
    "/agent/approve/{run_id}",
    response_model=AgentApproveResponse,
    tags=["Human Approval"],
    summary="审批并执行待确认动作",
    description="审批 create_ticket 或 notify_human_agent 等写操作。未审批前不会落盘或通知。",
)
def approve_agent_action(
    run_id: str,
    request: AgentApproveRequest,
    _: str = Depends(require_api_key),
) -> AgentApproveResponse:
    result = approve_run(run_id, request)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run_id 不存在")
    return result


@router.get(
    "/agent/runs/{run_id}",
    response_model=AgentTrace,
    tags=["Trace"],
    summary="查询 Agent Trace",
    description="按 run_id 查询已脱敏的工具轨迹、来源、审批状态和安全检查信息。",
)
def get_agent_run(run_id: str, _: str = Depends(require_api_key)) -> AgentTrace:
    trace = TraceStore().get(run_id)
    if trace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run_id 不存在")
    return trace


@router.get(
    "/tickets",
    response_model=list[Ticket],
    tags=["工单与通知"],
    summary="查询所有 mock 工单和通知",
    description="返回客服工单、运维 incident 和人工通知记录。",
)
def get_tickets(_: str = Depends(require_api_key)) -> list[Ticket]:
    return list_tickets()


@router.get(
    "/tickets/{ticket_id}",
    response_model=Ticket,
    tags=["工单与通知"],
    summary="查询单个工单或通知",
    description="根据 ticket_id 查询 mock 工单、incident 或通知记录。",
)
def get_ticket_endpoint(ticket_id: str, _: str = Depends(require_api_key)) -> Ticket:
    ticket = get_ticket(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ticket_id 不存在")
    return ticket


@router.get(
    "/demo",
    response_class=HTMLResponse,
    tags=["Demo 页面"],
    summary="中文 Demo 页面",
    description="展示项目介绍、三类业务场景、workflow 架构、工具、安全设计和示例请求。",
)
def demo_page() -> HTMLResponse:
    html = """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>多业务场景 Workflow Agent 演示系统</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 0; color: #1f2937; background: #f8fafc; }
    main { max-width: 1080px; margin: 0 auto; padding: 40px 20px 64px; }
    section { background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 22px; margin: 18px 0; }
    h1 { font-size: 34px; margin: 0 0 12px; }
    h2 { font-size: 22px; margin: 0 0 12px; }
    code, pre { background: #f3f4f6; border-radius: 6px; }
    pre { padding: 14px; overflow: auto; }
    a { color: #0f766e; }
    li { margin: 6px 0; }
  </style>
</head>
<body>
<main>
  <h1>多业务场景 Workflow Agent 演示系统</h1>
  <p>该项目展示 workflow-style orchestration、tool/function calling、Structured Outputs、Human Approval、安全边界和 Trace。</p>

  <section>
    <h2>三个业务场景</h2>
    <ul>
      <li>企业客服知识库：SLA、退款政策、FAQ、合规评审、客服工单草稿。</li>
      <li>金融投研：外部 RAG 检索财报/研报，结合本地 CSV 指标做聚合和增长率计算。</li>
      <li>内部运维：错误码、runbook、SOP、P0/P1 升级和 mock 值班通知。</li>
    </ul>
  </section>

  <section>
    <h2>工作流架构图</h2>
    <pre>user_input
  -> Scenario Router
  -> Intent Classifier
  -> Workflow Selector
  -> Tool Planner
  -> Tool Execution
  -> Human Approval if needed
  -> Final Answer
  -> Trace Store</pre>
  </section>

  <section>
    <h2>工具列表</h2>
    <ul>
      <li>classify_scenario</li>
      <li>classify_intent</li>
      <li>search_knowledge_base：调用 <code>/rag/query</code></li>
      <li>analyze_csv：仅允许访问 <code>data/finance/</code></li>
      <li>create_ticket：需人工审批</li>
      <li>notify_human_agent：需人工审批</li>
      <li>summarize_workflow_result</li>
    </ul>
  </section>

  <section>
    <h2>Human Approval</h2>
    <p>任何写操作都先返回 <code>waiting_approval</code> 和 <code>pending_action</code>，只有调用 <code>POST /agent/approve/{run_id}</code> 后才会创建 mock 工单或通知。</p>
  </section>

  <section>
    <h2>安全设计与 Trace</h2>
    <p>系统启用 API Key 鉴权、工具白名单、max_steps、参数校验、敏感字段脱敏、禁止 shell、禁止读取 .env、CSV 路径限制和 RAG Base URL 固定化。</p>
    <p>Trace 可通过 <code>GET /agent/runs/{run_id}</code> 查询，内容包含工具步骤、sources、审批状态和安全检查信息。</p>
  </section>

  <section>
    <h2>Demo 请求示例</h2>
    <pre>curl -X POST http://127.0.0.1:8770/agent/run \\
  -H "X-API-Key: change-me" \\
  -H "Content-Type: application/json" \\
  -d "{\"user_input\":\"P0 故障升级流程是什么？请通知值班人员。\"}"</pre>
    <p><a href="/docs">打开 Swagger 文档</a></p>
  </section>
</main>
</body>
</html>
"""
    return HTMLResponse(content=html)

