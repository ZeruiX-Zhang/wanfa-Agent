# 简历 Bullet Points

## 中文版

- 设计并实现企业知识库 RAG + 多工具 Agent Demo，基于 FastAPI、FAISS、BM25、RRF、Simple Reranker 和 OpenAI-compatible API，支持多业务域知识问答、引用来源返回和检索 Debug。
- 构建多业务域 Domain Router，覆盖企业制度、客户支持、运维手册、法律合同和数据分析场景，支持 `domain=auto` 自动路由与显式 domain 过滤。
- 实现 Hybrid Retrieval 链路，将 Dense Retrieval 与 BM25 召回通过 RRF 融合，并在召回后进行 rerank，提升企业知识库问答的可解释性和可调试性。
- 实现 workflow-style Agent 工具调用，支持知识库查询、CSV 数据分析、安全拒绝和 run trace 查询，避免 AutoGPT 式不可控循环。
- 建立轻量 Eval 与验收体系，基于 JSONL 测试集输出 hit_rate、MRR、average_rank 和 expected_source 命中，并提供 pytest、OpenAPI 中文化检查和 final acceptance 一键验收脚本。

## English Version

- Designed and implemented a production-oriented RAG + multi-tool Agent demo with FastAPI, FAISS, BM25, RRF, Simple Reranker, and OpenAI-compatible APIs for multi-domain enterprise knowledge QA.
- Built a domain routing layer for enterprise policy, customer support, ops runbook, legal contract, and data analysis scenarios, supporting both automatic routing and explicit domain filtering.
- Implemented a hybrid retrieval pipeline combining dense vector search and BM25 with RRF fusion and reranking, returning debuggable sources and retrieval traces.
- Developed a workflow-style Agent with controlled tool invocation for knowledge-base search, CSV analysis, safety refusal, and run trace inspection.
- Added lightweight RAG evaluation and acceptance checks using JSONL datasets, hit_rate, MRR, average_rank, expected_source matching, pytest, OpenAPI localization checks, and an end-to-end acceptance script.

## 偏 RAG 工程师

- 重点强调 Hybrid Retrieval、BM25、RRF、Reranker、Contextual Retrieval、sources、debug 和 eval。

## 偏 Agent 工程师

- 重点强调 workflow-style agent、工具白名单、tool_args、tool_result、run_id、steps、latency 和安全拒绝。

## 偏大模型应用开发工程师

- 重点强调 FastAPI 工程分层、中文 Swagger、API Key、Docker、验收脚本、trace 和面试可展示闭环。
