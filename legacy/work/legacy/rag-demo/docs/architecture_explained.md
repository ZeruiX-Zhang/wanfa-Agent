# 架构讲解

## API layer

解决什么问题：统一对外暴露 RAG、Agent、Eval、Health、Demo 和管理接口。

代码大概在哪：`app/main.py`、`app/api/routes.py`。

面试怎么讲：FastAPI 是整个 Demo 的入口，`/docs` 可以直接看到接口分层和 schema。

生产化如何增强：增加版本化 API、限流、审计、错误码规范和网关接入。

## schemas

解决什么问题：定义请求和响应结构，让 OpenAPI 可读、可验收。

代码大概在哪：`app/schemas/portfolio_api.py`、`app/models/schemas.py`。

面试怎么讲：字段名保持英文稳定，说明和示例用中文，便于展示和集成。

生产化如何增强：增加更严格的字段校验、向后兼容策略和 schema contract test。

## document ingestion

解决什么问题：把本地样例文档导入知识库，生成可检索 chunk。

代码大概在哪：`app/rag/ingestion.py`、`app/rag/ingestion_jobs.py`。

面试怎么讲：当前支持 `data/raw` 样例导入，适合面试前一键准备知识库。

生产化如何增强：接入对象存储、Confluence、SharePoint、Notion，增加异步任务和失败重试。

## chunking

解决什么问题：把文档拆成适合检索的片段。

代码大概在哪：`app/rag/ingestion.py`。

面试怎么讲：TXT / Markdown 按段落切分，CSV 作为结构化文本整体导入。

生产化如何增强：按标题层级、表格、父子 chunk、滑动窗口和语义边界切分。

## metadata

解决什么问题：为 chunk 提供 domain、tenant_id、access_roles、filename 等过滤和引用字段。

代码大概在哪：`app/rag/models.py`、`app/rag/ingestion.py`。

面试怎么讲：metadata 是企业 RAG 的关键，不只是存文本，还要保留权限和来源。

生产化如何增强：接入真实 IAM、文档 ACL、数据血缘和审计字段。

## vector store

解决什么问题：保存 chunk 和向量索引，支持检索。

代码大概在哪：`app/rag/vector_stores/faiss_store.py`、`app/rag/vector_stores/pgvector_store.py`。

面试怎么讲：当前默认 FAISS，适合本地 demo；pgvector 是预留扩展方向。

生产化如何增强：服务化向量库、索引版本、备份恢复、分片和多实例部署。

## retriever

解决什么问题：从知识库召回候选 chunk。

代码大概在哪：`app/rag/retrievers/`。

面试怎么讲：Dense 负责语义召回，BM25 负责关键词召回，Hybrid Retriever 负责组合。

生产化如何增强：多路召回、查询改写、召回缓存、动态 top_k 和召回诊断。

## domain router

解决什么问题：把问题路由到合适业务域，减少跨域误召回。

代码大概在哪：`app/router/domain_router.py`。

面试怎么讲：`domain=auto` 时先路由，显式 domain 可覆盖，适合排查误判。

生产化如何增强：训练分类器、加置信度阈值、fallback 多域召回和 router eval。

## prompt builder

解决什么问题：把检索 context 组织成可回答的问题上下文。

代码大概在哪：`app/rag/service.py`。

面试怎么讲：当前 demo 重点在 retrieval 和 sources，回答构造保持轻量，避免掩盖检索链路。

生产化如何增强：加入 prompt template、引用格式、拒答策略、上下文压缩和 prompt injection 防护。

## llm client

解决什么问题：连接 mock 或 OpenAI-compatible 模型服务。

代码大概在哪：`app/llm/`、`app/providers/`。

面试怎么讲：模型调用被抽象为 provider，方便切换 OpenAI、DeepSeek、Qwen、Ollama 等兼容服务。

生产化如何增强：超时、重试、fallback、熔断、成本统计和模型路由。

## agent

解决什么问题：根据用户任务选择受控工具并生成 trace。

代码大概在哪：`app/api/routes.py` 的 `/agent/run`、`app/agent/trace.py`。

面试怎么讲：使用 workflow-style，是为了可控、可测、可审计。

生产化如何增强：加入 planner、approval gate、human-in-the-loop 和更细的 tool policy。

## tools

解决什么问题：把 Agent 能力限制在明确工具内。

代码大概在哪：`app/agent/tools.py`。

面试怎么讲：当前有 `search_knowledge_base` 和 `analyze_csv`，危险请求不会转成 shell。

生产化如何增强：增加工单、CRM、数据库只读查询、审批系统等受控工具。

## eval

解决什么问题：用离线样本验证检索是否命中期望来源。

代码大概在哪：`app/eval/evaluator.py`、`data/eval/*.jsonl`。

面试怎么讲：Eval 输出 hit_rate、MRR、average_rank 和逐条 expected_source 命中。

生产化如何增强：RAGAS / DeepEval、人工标注、回归阈值、CI 阻断和线上反馈闭环。

## trace

解决什么问题：记录 RAG 和 Agent 的运行过程，方便排查和演示。

代码大概在哪：`app/observability/`、`app/agent/trace.py`。

面试怎么讲：`run_id` 可以读回 selected_tool、tool_args、tool_result 和 latency。

生产化如何增强：接入 OpenTelemetry、日志平台、指标系统和审计存储。

## security

解决什么问题：控制 API 访问、文件访问和敏感输出。

代码大概在哪：`app/core/auth.py`、`app/security/path_guard.py`、`app/security/output_sanitizer.py`。

面试怎么讲：API Key、工具白名单、路径限制、`.env` 拒绝和 shell 删除拒绝构成 demo 的安全边界。

生产化如何增强：OIDC / SSO、细粒度 ACL、密钥管理、DLP、审计和安全测试。
