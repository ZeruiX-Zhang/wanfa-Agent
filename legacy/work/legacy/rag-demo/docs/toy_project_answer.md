# 如果被问“这是不是玩具项目”

## 30 秒版

我会承认它不是生产集群，也没有真实企业流量。但它不是纯玩具项目，因为我不是只包了一层 ChatGPT API。这个项目包含多业务域 RAG、Hybrid Retrieval、BM25、RRF、Reranker、Eval、trace、API Key、工具白名单、安全拒绝和一键验收脚本。它更准确的定位是 production-oriented demo，用来展示我知道一个 RAG + Agent 应用从原型走向生产需要哪些工程边界。

## 1 分钟版

如果面试官问是不是玩具项目，我会说：它不是完整生产系统，但也不是随手做的 toy wrapper。生产系统需要真实数据、权限系统、稳定检索后端、监控告警、压测和上线流程，这些我不会夸大。

但这个 Demo 已经覆盖生产化前最关键的工程骨架：多业务域、metadata、hybrid search、reranker、sources、debug、eval、trace、Agent 工具白名单、`.env` 拒绝、shell 删除拒绝、Docker 和 final acceptance。它的价值是证明我理解 RAG / Agent 工程中哪些问题必须被设计出来，而不是只把问题丢给大模型。

## 技术深挖版

我会把它定位为 production-oriented demo。和普通玩具项目相比，它有几个区别：

1. 检索不是单一路径：Dense + BM25 + RRF + Reranker。
2. 不是单文档问答：有 enterprise_kb、customer_support、ops_runbook、legal_contract、data_analysis 多域。
3. 不是黑盒回答：返回 sources、debug、trace_id。
4. Agent 不是无限循环：使用 workflow-style 和工具白名单。
5. 安全不是口头说明：`.env` 和 shell 删除请求会被拒绝。
6. 质量不是主观判断：有 JSONL eval 和 final acceptance。
7. 展示不是临时拼接：有 README、Swagger、/demo、截图指南和面试脚本。

我也会主动说明生产化路线：把 FAISS 换成 pgvector / Milvus，把 Simple Reranker 换成 cross-encoder，把轻量 JSONL eval 扩展成 RAGAS / DeepEval，把 metadata ACL 接到真实 IAM，并加入异步 ingestion、审计日志、压测和监控。
