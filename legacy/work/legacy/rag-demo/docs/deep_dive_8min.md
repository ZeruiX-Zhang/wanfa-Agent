# 8 分钟技术深挖讲解稿

## 1. 项目背景

我会怎么讲：

这个项目模拟企业内部知识库问答。企业场景和普通聊天最大的区别是：答案必须来自授权知识、要能展示来源、要能解释检索链路，还要避免 Agent 随意读文件或执行危险操作。

## 2. 总体架构

我会怎么讲：

API 层用 FastAPI 暴露 RAG、Agent、Eval、Health 和 Demo 接口。RAG 侧是 Domain Router + Hybrid Retriever + RRF + Reranker + Answer Builder。Agent 侧是 workflow-style tool runner + Tool Registry + Trace Store。Eval 侧读取 JSONL 样本，输出 hit_rate、MRR 和 expected_source 命中结果。

## 3. 文档处理与 metadata

我会怎么讲：

样例文档在 `data/raw/`，导入时会生成 chunk，并带上 domain、tenant_id、access_roles、filename、doc_type 等 metadata。这些 metadata 支持后续的业务域过滤、权限过滤和引用来源返回。生产化时可以把这些字段接到真实 IAM、组织架构和审计系统。

## 4. 多业务域 Domain Router

我会怎么讲：

项目支持 `enterprise_kb`、`customer_support`、`ops_runbook`、`legal_contract`、`data_analysis` 等业务域。用户传 `domain=auto` 时由 Router 判断业务域。这样可以减少跨域误召回，比如合同问题不要误召回运维 runbook。

Router 误判时，接口仍支持显式传 domain；生产化可以加入置信度阈值、top-2 domain fallback、人工反馈和路由 eval。

## 5. Hybrid Retrieval

我会怎么讲：

Dense Retrieval 适合语义相似表达，BM25 适合关键词、编号、错误码、SLA 这类精确匹配。企业知识库里两类问题都会出现，所以我使用 hybrid search，而不是只依赖向量检索。

## 6. RRF / Reranker

我会怎么讲：

RRF 是 Reciprocal Rank Fusion，用排名倒数来融合多路检索结果。它不强依赖不同检索器的分数尺度，适合把 Dense 和 BM25 合并。

Reranker 放在召回之后，用来对候选 chunk 做二次排序。当前是 Simple Reranker，定位是轻量 demo；生产化可以换 cross-encoder 或商业 reranker。

## 7. RAG Prompt 安全

我会怎么讲：

这个项目不会把检索结果直接当成系统指令，而是把它作为 context。输出还会做基础敏感信息清洗。生产化还需要更完整的 prompt injection 检测、引用片段隔离、敏感字段脱敏和模型输出审计。

## 8. Agent 工具调用

我会怎么讲：

Agent 使用 workflow-style 而不是 AutoGPT。因为企业场景更看重可控性：知道调用了哪个工具、参数是什么、结果是什么、是否越权。当前工具包括知识库查询和 CSV 分析，未来可以扩展工单查询、报表查询、审批查询等工具。

## 9. 安全边界

我会怎么讲：

Agent 工具必须在白名单里，CSV 工具限制在受控目录，`.env` 请求会拒绝，shell 删除请求也会拒绝。这个设计重点不是让 Agent 做所有事，而是让 Agent 在明确边界内做事。

## 10. Eval 与可观测性

我会怎么讲：

Eval 使用 `data/eval/*.jsonl`，每条样本有 question、expected_domain、expected_source。返回 hit_rate、MRR、average_rank 和逐条命中结果。

可观测性上，RAG 有 trace_id，Agent 有 run_id、steps、tool_args、tool_result、latency。面试时我会展示 `/agent/runs/{run_id}`，说明工具调用不是黑盒。

## 11. 局限性

我会怎么讲：

它不是生产集群。当前 FAISS 是本地单机索引，Simple Reranker 不是工业级 reranker，Eval 是轻量 JSONL，样例数据是模拟数据，也没有做大规模并发压测。

## 12. 后续优化

我会怎么讲：

生产化方向包括 pgvector / Milvus / OpenSearch，异步 ingestion，增量索引，cross-encoder reranker，RAGAS / DeepEval，强 ACL，审计日志，任务队列和轻量后台管理页面。
