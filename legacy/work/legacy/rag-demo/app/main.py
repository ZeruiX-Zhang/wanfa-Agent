from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.routing import APIRoute

from app.api.routes import router


OPENAPI_TAGS = [
    {
        "name": "健康检查",
        "description": "检查服务存活状态、依赖就绪状态和存储可写状态。",
    },
    {
        "name": "文档管理",
        "description": "上传文档、导入本地文档、解析文本、切分 chunk 和构建索引。",
    },
    {
        "name": "RAG 问答",
        "description": "执行企业知识库问答、展示 sources、调试检索结果和路由结果。",
    },
    {
        "name": "Agent 执行",
        "description": "执行多工具 Agent，包括知识库搜索、CSV 分析、文档总结和安全计算。",
    },
    {
        "name": "评测",
        "description": "运行检索评测、命中率检查、MRR 和离线测试。",
    },
]


app = FastAPI(
    title="企业知识库 RAG 与多工具 Agent 演示系统",
    summary="面向企业知识库问答、多业务域路由和工具调用 Agent 的作品集级 Demo",
    description="""
这是一个用于求职展示和技术面试讲解的企业级 RAG + 多工具 Agent Demo。

核心能力：

- 多业务域知识库：企业制度、客户支持、运维手册、法律合同、数据分析
- Domain Router：自动识别问题所属业务场景
- Hybrid Retrieval：Dense 向量检索 + BM25 + RRF 融合
- Reranker：对候选 chunk 进行二次排序
- Contextual Retrieval：使用 contextual_text 提升检索质量
- 工具调用 Agent：支持知识库搜索、CSV 分析、文档总结和安全计算
- 安全设计：API Key、tenant_id、access_roles、工具白名单和路径限制
- 可观测性：trace_id、debug 检索结果、latency 和 agent run trace
- 评测能力：支持检索命中率、MRR 和离线测试
""",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=OPENAPI_TAGS,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:1420", "http://127.0.0.1:1420", "tauri://localhost"],
    allow_origin_regex=r"chrome-extension://.*|edge-extension://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
for route in app.routes:
    if isinstance(route, APIRoute) and not route.tags:
        route.tags = ["RAG Demo"]


@app.get(
    "/demo",
    tags=["演示入口"],
    summary="打开中文演示首页",
    description="提供中文项目简介、常用接口入口和可复制的 curl / PowerShell 调用示例。",
    response_description="返回中文 HTML 演示首页。",
    response_class=HTMLResponse,
)
def demo_home() -> HTMLResponse:
    return HTMLResponse(_demo_html())


def _demo_html() -> str:
    return """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>企业知识库 RAG 与多工具 Agent 演示系统</title>
  <style>
    :root {
      color-scheme: light;
      font-family: "Segoe UI", "Microsoft YaHei", Arial, sans-serif;
      background: #f6f8fb;
      color: #1f2937;
    }
    body { margin: 0; }
    header { background: #0f766e; color: white; padding: 42px 24px 34px; }
    main { max-width: 1080px; margin: 0 auto; padding: 28px 20px 48px; }
    h1 { margin: 0 0 12px; font-size: 34px; line-height: 1.2; letter-spacing: 0; }
    h2 { margin: 0 0 14px; font-size: 21px; letter-spacing: 0; }
    p { line-height: 1.75; }
    a { color: #0f766e; font-weight: 650; text-decoration: none; }
    .subtitle { max-width: 820px; margin: 0; font-size: 17px; line-height: 1.7; color: #dff7f4; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 18px; }
    section, .card {
      background: white;
      border: 1px solid #d9e2ec;
      border-radius: 8px;
      padding: 20px;
      box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
    }
    section { margin-bottom: 18px; }
    ul { padding-left: 20px; line-height: 1.8; }
    code, pre { font-family: Consolas, "SFMono-Regular", monospace; background: #eef2f7; border-radius: 6px; }
    code { padding: 2px 5px; }
    pre { overflow-x: auto; padding: 14px; line-height: 1.55; border: 1px solid #d9e2ec; }
    .links { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 18px; }
    .link-button {
      display: inline-flex;
      align-items: center;
      min-height: 40px;
      padding: 0 14px;
      border-radius: 6px;
      background: white;
      color: #0f766e;
      border: 1px solid #99f6e4;
    }
    .muted { color: #5b6778; }
  </style>
</head>
<body>
  <header>
    <h1>企业知识库 RAG 与多工具 Agent 演示系统</h1>
    <p class="subtitle">面向中文技术面试的作品集 Demo：展示多业务域知识库、Domain Router、Hybrid Retrieval、BM25、RRF、Reranker、权限过滤、trace_id 和离线评测。</p>
    <div class="links">
      <a class="link-button" href="/docs">Swagger UI /docs</a>
      <a class="link-button" href="/redoc">ReDoc /redoc</a>
      <a class="link-button" href="/openapi.json">OpenAPI JSON</a>
    </div>
  </header>
  <main>
    <section>
      <h2>业务场景</h2>
      <div class="grid">
        <div class="card"><strong>企业制度</strong><p class="muted">报销、政策、知识库问答。</p></div>
        <div class="card"><strong>客户支持</strong><p class="muted">P1 SLA、工单升级、客户响应。</p></div>
        <div class="card"><strong>运维手册</strong><p class="muted">故障排查、支付链路、应急流程。</p></div>
        <div class="card"><strong>法律合同</strong><p class="muted">责任上限、违约责任、终止条款。</p></div>
      </div>
    </section>
    <section>
      <h2>RAG 流程</h2>
      <ul>
        <li>Domain Router 根据问题自动选择业务域，也支持显式传入 <code>domain</code>。</li>
        <li>Hybrid Retrieval 同时使用 Dense 向量检索和 BM25，并通过 RRF 融合候选片段。</li>
        <li>Reranker 对候选 chunk 二次排序，最终返回答案、引用来源和调试信息。</li>
      </ul>
    </section>
    <section>
      <h2>Agent 流程</h2>
      <ul>
        <li>接收 <code>user_input</code> 后选择白名单工具，例如知识库搜索、CSV 分析、文档总结或安全计算。</li>
        <li>每次工具调用都会记录 trace_id、工具参数、工具结果摘要和耗时。</li>
        <li><code>GET /agent/runs/{run_id}</code> 可回放 Agent 执行轨迹。</li>
      </ul>
    </section>
    <section>
      <h2>安全设计</h2>
      <ul>
        <li>API Key 控制访问入口，tenant_id 和 access_roles 控制知识库片段可见性。</li>
        <li>Agent 工具通过白名单开放，文件读取受路径限制保护。</li>
        <li>输出会经过基础脱敏处理，避免敏感文件内容直接泄露。</li>
      </ul>
    </section>
    <section>
      <h2>评测说明</h2>
      <ul>
        <li>检索评测输出 hit_rate、MRR、average_rank 和每条样本命中明细。</li>
        <li>生成评测输出 answer_relevancy、groundedness 和 citation_coverage。</li>
        <li>对比评测用于展示 dense、hybrid、hybrid + reranker 的效果差异。</li>
      </ul>
    </section>
    <section>
      <h2>常用接口</h2>
      <ul>
        <li><code>GET /health</code>：检查服务状态。</li>
        <li><code>POST /documents/upload</code>：上传文本内容并写入知识库。</li>
        <li><code>POST /documents/ingest-local</code>：导入本地文档并构建 RAG 索引。</li>
        <li><code>POST /rag/query</code>：执行 RAG 问答并返回 sources。</li>
        <li><code>POST /rag/debug</code>：查看 Domain Router、Dense、BM25、RRF、Reranker 调试信息。</li>
        <li><code>POST /agent/run</code>：执行受控工具调用并生成 Agent trace。</li>
        <li><code>POST /eval/run</code>：按 run_type 运行检索、生成或对比评测。</li>
        <li><code>POST /eval/retrieval</code>：运行检索命中评测。</li>
      </ul>
    </section>
    <section>
      <h2>演示问题</h2>
      <ul>
        <li>企业客户 P1 响应时间是多少？</li>
        <li>合同责任上限是多少？违约责任如何约定？</li>
        <li>支付失败时运维值班同学应该先检查哪些项目？</li>
        <li>分析 data_analysis 域下 sales_report.csv 的收入均值、最大值和最小值。</li>
      </ul>
    </section>
    <section>
      <h2>PowerShell 示例</h2>
      <pre>$body = @{
  question = "企业客户 P1 响应时间是多少？"
  domain = "auto"
  top_k = 5
} | ConvertTo-Json -Compress

Invoke-RestMethod `
  -Method POST `
  -Uri "http://127.0.0.1:8765/rag/query" `
  -Headers @{"X-API-Key"="change-me"} `
  -ContentType "application/json; charset=utf-8" `
  -Body ([System.Text.Encoding]::UTF8.GetBytes($body))</pre>
    </section>
    <section>
      <h2>curl 示例</h2>
      <pre>curl -X POST "http://127.0.0.1:8765/rag/query" \
  -H "X-API-Key: change-me" \
  -H "Content-Type: application/json" \
  -d '{"question":"企业客户 P1 响应时间是多少？","domain":"auto","top_k":5}'</pre>
    </section>
  </main>
</body>
</html>
"""
