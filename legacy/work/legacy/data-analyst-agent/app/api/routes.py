from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, HTMLResponse

from app.agent.pipeline import DataAnalystAgent
from app.core.auth import require_api_key
from app.core.config import get_settings
from app.db.schema import retrieve_schema
from app.schemas.data_agent import (
    DataAgentQueryRequest,
    DataAgentQueryResponse,
    DataAgentTrace,
    ErrorResponse,
    HealthResponse,
    SQLValidationRequest,
    SQLValidationResult,
    SchemaInfo,
)
from app.sql.safety import SQLSafetyChecker
from app.trace.store import TraceStore


data_agent_router = APIRouter(
    prefix="/data-agent",
    tags=["数据分析 Agent"],
    dependencies=[Depends(require_api_key)],
    responses={401: {"model": ErrorResponse, "description": "API Key 缺失或无效"}},
)

public_router = APIRouter(tags=["公开页面"])


@public_router.get(
    "/health",
    response_model=HealthResponse,
    summary="健康检查",
    description="检查 AI 数据分析 Agent 服务和 SQLite 数据库文件状态。",
)
async def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service="AI 数据分析 Agent 演示系统",
        database_exists=settings.database_path.exists(),
        app_env=settings.app_env,
    )


@public_router.get(
    "/demo",
    response_class=HTMLResponse,
    summary="中文 Demo 页面",
    description="展示项目介绍、流程图、安全策略、Trace 和可复制 Demo 问题。",
)
async def demo() -> HTMLResponse:
    return HTMLResponse(DEMO_HTML)


@data_agent_router.get(
    "/schema",
    response_model=SchemaInfo,
    summary="获取业务数据库 Schema",
    description="返回表名、字段名、字段类型、样例值、行数和中文字段说明，用于 Schema Grounding。",
)
async def get_schema() -> SchemaInfo:
    return retrieve_schema(get_settings())


@data_agent_router.post(
    "/query",
    response_model=DataAgentQueryResponse,
    summary="提交自然语言数据分析问题",
    description="执行 User Question 到 SQL Safety Checker、只读 SQL、图表和 Trace 的完整 Data Analyst Agent pipeline。",
)
async def query_data_agent(request: DataAgentQueryRequest) -> DataAgentQueryResponse:
    agent = DataAnalystAgent(get_settings())
    return agent.run(request)


@data_agent_router.post(
    "/validate-sql",
    response_model=SQLValidationResult,
    summary="校验 SQL 是否安全",
    description="只允许 SELECT，禁止 DDL/DML、多语句、SQLite 系统表、本地文件和敏感密钥读取，并强制 LIMIT。",
)
async def validate_sql(request: SQLValidationRequest) -> SQLValidationResult:
    settings = get_settings()
    checker = SQLSafetyChecker(max_result_rows=settings.max_result_rows)
    return checker.validate(request.sql)


@data_agent_router.get(
    "/runs/{run_id}",
    response_model=DataAgentTrace,
    summary="查询审计 Trace",
    description="根据 run_id 从 data/traces/runs.jsonl 查回一次数据分析运行记录。",
)
async def get_run(run_id: str) -> DataAgentTrace:
    trace = TraceStore(get_settings()).get(run_id)
    if not trace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到该 run_id 的 trace。")
    return trace


@public_router.get(
    "/data-agent/charts/{filename}",
    response_class=FileResponse,
    summary="读取图表文件",
    description="读取 data/charts/{run_id}.png 图表文件，文件名会做路径穿越防护。",
)
async def get_chart(filename: str) -> FileResponse:
    if not re.fullmatch(r"[A-Za-z0-9_\-]+\.png", filename):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="图表文件不存在。")
    path = get_settings().chart_dir / filename
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="图表文件不存在。")
    return FileResponse(path, media_type="image/png")


DEMO_QUESTIONS = [
    "2025 年各季度营收变化趋势是什么？",
    "哪个区域营收增长最快？",
    "哪个渠道转化率最低？",
    "各产品线毛利率排名如何？",
    "华东地区哪个产品线收入最高？",
    "P1 工单平均解决时间是多少？",
    "哪类客服问题满意度最低？",
    "哪个行业客户贡献收入最高？",
    "市场投放 ROI 最高的渠道是什么？",
    "上个月新增客户主要来自哪些区域？",
]

DEMO_HTML = f"""
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>AI 数据分析 Agent 演示系统</title>
  <style>
    body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #172033; background: #f7f8fb; }}
    header {{ padding: 36px 28px 20px; background: #ffffff; border-bottom: 1px solid #dfe4ee; }}
    main {{ max-width: 1080px; margin: 0 auto; padding: 28px; }}
    h1 {{ margin: 0 0 10px; font-size: 32px; }}
    h2 {{ margin: 30px 0 12px; font-size: 21px; }}
    p, li {{ line-height: 1.7; }}
    code {{ background: #eef2f7; padding: 2px 6px; border-radius: 4px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 12px; }}
    .card {{ background: #fff; border: 1px solid #dfe4ee; border-radius: 8px; padding: 16px; }}
    .flow {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    .step {{ background: #1f5f8b; color: white; padding: 9px 12px; border-radius: 6px; }}
    .arrow {{ align-self: center; color: #607086; }}
    a {{ color: #155f95; }}
  </style>
</head>
<body>
  <header>
    <h1>AI 数据分析 Agent 演示系统</h1>
    <p>面向业务分析场景的 Text-to-SQL Agent，重点展示 Schema Grounding、SQL Safety Checker、只读 SQL 执行、图表生成、结构化输出和审计日志。</p>
  </header>
  <main>
    <h2>数据表说明</h2>
    <div class="grid">
      <div class="card"><strong>orders</strong><p>订单收入、成本、区域、渠道、产品线和状态。</p></div>
      <div class="card"><strong>customers</strong><p>客户名称、行业、区域、客户等级和创建时间。</p></div>
      <div class="card"><strong>tickets</strong><p>客服工单类别、优先级、解决时长和满意度。</p></div>
      <div class="card"><strong>marketing_spend</strong><p>市场花费、线索、转化、渠道和区域。</p></div>
    </div>

    <h2>Text-to-SQL 流程图</h2>
    <div class="flow">
      <span class="step">User Question</span><span class="arrow">→</span>
      <span class="step">Intent Parser</span><span class="arrow">→</span>
      <span class="step">Schema Retriever</span><span class="arrow">→</span>
      <span class="step">SQL Generator</span><span class="arrow">→</span>
      <span class="step">SQL Safety Checker</span><span class="arrow">→</span>
      <span class="step">Read-only SQL</span><span class="arrow">→</span>
      <span class="step">Chart + Trace</span>
    </div>

    <h2>SQL Safety Checker</h2>
    <p>系统只允许 <code>SELECT</code>，拒绝 DROP、DELETE、UPDATE、INSERT、ALTER、CREATE、PRAGMA、多语句、SQLite 系统表、本地文件和密钥读取，并强制追加最大 LIMIT。</p>

    <h2>图表生成</h2>
    <p>支持 line、bar、pie 和 none。图表保存到 <code>data/charts/{{run_id}}.png</code>，接口返回 <code>chart_url</code>。</p>

    <h2>Trace / 审计日志</h2>
    <p>每次查询记录 run_id、trace_id、问题、schema_used、SQL 计划、安全校验、执行 SQL、行数、图表、中文结论和耗时，保存到 <code>data/traces/runs.jsonl</code>。</p>

    <h2>Demo 问题</h2>
    <ol>
      {''.join(f'<li>{question}</li>' for question in DEMO_QUESTIONS)}
    </ol>

    <h2>Swagger</h2>
    <p><a href="/docs">打开中文 Swagger 文档</a></p>
  </main>
</body>
</html>
"""

