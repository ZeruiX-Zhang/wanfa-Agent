# 3 分钟项目讲解稿

## 0:00-0:30 背景和问题

我这个项目是一个面向 RAG 工程师、Agent 工程师和大模型应用开发岗位的作品集 Demo。它模拟企业内部知识库场景，比如企业制度、客户 SLA、运维 runbook、合同条款和 CSV 报表分析。

我想展示的不是一个简单 ChatGPT Wrapper，而是一个 production-oriented demo：有工程分层、有多业务域路由、有混合检索、有 Agent 工具调用、有安全边界、有 eval 和 trace。

## 0:30-1:10 架构

整体架构是 FastAPI API 层对外提供 `/rag/query`、`/rag/debug`、`/agent/run`、`/eval/retrieval` 等接口。RAG 侧先经过 Domain Router 判断业务域，再走 Hybrid Retrieval，把 Dense Retrieval 和 BM25 结果用 RRF 融合，然后用 Simple Reranker 排序，最后返回答案和 sources。

Agent 侧我没有做 AutoGPT 式无限循环，而是 workflow-style agent。它根据任务选择白名单工具，比如 `search_knowledge_base` 和 `analyze_csv`，每一步都记录 run trace。

## 1:10-2:00 RAG 能力

RAG 部分重点是可解释和可验收。`/rag/debug` 可以看到 selected_domain、Dense 结果、BM25 结果、RRF 融合结果、reranked results、sources 和 trace_id。

Dense 解决语义相似问题，BM25 解决关键词、错误码、条款名称这类精确匹配问题。RRF 的作用是融合两路结果，降低单一路召回不稳定。Reranker 则把候选 chunk 再排一次，减少不相关 context 进入回答。

我还加了 JSONL eval，能看 hit_rate、MRR、average_rank，以及 expected_source 是否命中。

## 2:00-2:40 Agent 能力

Agent 主要展示企业场景里更可控的工具调用。比如用户说“分析 sales_report.csv 的收入均值、最大值和最小值”，Agent 会选择 `analyze_csv`，返回列名、行数和统计指标。

如果用户问“企业客户 P1 响应时间是多少，请查询知识库并给出来源”，Agent 会选择 `search_knowledge_base`，返回答案和 `enterprise_sla.txt` 来源。

安全方面，如果用户要求读取 `.env` 或执行 shell 删除项目文件，Agent 会拒绝，不会把 secret 写到 final answer 或 trace 里。

## 2:40-3:00 工程化与总结

工程化部分我做了 API Key、tenant_id、access_roles metadata、OpenAPI 中文化、`/demo` 中文演示页、Dockerfile、pytest、OpenAPI 检查和 final acceptance 一键验收。

所以这个项目的定位是：不是完整生产系统，但它是面向生产化设计的 RAG + Agent 工程骨架，适合展示我对检索、工具调用、安全、eval 和可观测性的理解。
