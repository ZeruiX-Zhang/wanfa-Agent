# 30 个面试追问与参考答案

## 1. 为什么这不是简单 ChatGPT Wrapper？

参考答案：简单 Wrapper 通常只是把用户问题转发给模型。这个项目有文档 ingestion、chunk metadata、Domain Router、Hybrid Retrieval、BM25、RRF、Reranker、sources、debug、eval、trace、API Key 和 Agent 安全边界。模型只是最后生成答案的一环，核心价值在检索、控制和验收链路。

## 2. 为什么用 workflow-style agent？

参考答案：企业场景更重视可控性和可审计性。workflow-style agent 可以明确知道 selected_tool、tool_args、tool_result 和 latency，适合面试展示和生产化扩展。

## 3. 为什么不用 AutoGPT？

参考答案：AutoGPT 式循环适合开放探索，但企业知识库问答更需要边界清晰。无限循环会增加成本、延迟和安全风险。当前场景里工具集合明确，所以用 workflow-style 更合适。

## 4. Domain Router 如何实现？

参考答案：当前 Router 根据问题内容选择业务域，例如 customer_support、ops_runbook、legal_contract。它位于 RAG 检索前，作用是减少跨域误召回。接口也支持显式传 domain，方便纠错和测试。

## 5. Router 误判怎么办？

参考答案：当前可以显式传 domain 覆盖 auto。生产化可以加置信度阈值、top-2 domain fallback、多域召回、人工反馈和 router eval。

## 6. 为什么用 hybrid search？

参考答案：企业知识库同时存在语义问法和精确关键词。Dense 适合语义相似，BM25 适合错误码、条款名、SLA、编号等词面匹配。hybrid 能降低单一路径失败风险。

## 7. BM25 和 dense retrieval 各自解决什么问题？

参考答案：BM25 依赖关键词匹配，对专有名词、数字、错误码很有效。Dense retrieval 依赖向量语义，对同义表达、自然语言改写更有效。

## 8. RRF 是什么？

参考答案：RRF 是 Reciprocal Rank Fusion，用排名倒数融合多路检索结果。它不要求不同检索器的分数可比，适合合并 Dense 和 BM25 的排序。

## 9. Reranker 有什么作用？

参考答案：Retriever 负责召回，Reranker 负责精排。它在候选 chunk 上做二次排序，减少无关 chunk 进入最终 context。当前是 Simple Reranker，生产化可以换 cross-encoder。

## 10. Contextual Retrieval 是什么？

参考答案：它是在 chunk 上保留额外 contextual_text，让单个片段不完全脱离文档上下文。这样检索时不仅看局部文本，也能利用章节或背景信息。

## 11. 如何防 prompt injection？

参考答案：当前做了基础输出脱敏和敏感内容清洗，不把检索文本当系统指令执行。生产化还需要 prompt injection 分类、指令隔离、引用片段标注、敏感字段识别和输出审计。

## 12. 为什么 sources 很重要？

参考答案：企业知识库回答必须可追溯。sources 让用户知道答案来自哪个文件、哪个 chunk，也方便 debug 错误召回和评估命中。

## 13. 如何做权限控制？

参考答案：当前 chunk metadata 有 tenant_id 和 access_roles，检索时可以按上下文过滤。生产化应接入真实 IAM、文档 ACL 同步和审计日志。

## 14. tenant_id 和 access_roles 现在做到什么程度？

参考答案：当前主要作为 metadata 进入 chunk，并参与检索过滤，是一个 demo 级多租户 / 角色过滤骨架。它还不是完整企业权限平台。

## 15. FAISS 和 pgvector 如何取舍？

参考答案：FAISS 适合本地 demo、单机快速验证和低依赖部署。pgvector 更适合和 PostgreSQL 数据治理结合，支持服务化、备份、权限和 SQL 查询。生产化要根据规模、运维能力和一致性要求取舍。

## 16. 如何扩展到生产？

参考答案：检索后端服务化，ingestion 异步化，ACL 接 IAM，reranker 换模型，eval 纳入 CI，trace 接监控系统，敏感数据做审计和脱敏，再加压测和灰度发布。

## 17. 如何做异步 ingestion？

参考答案：当前已有同步导入接口适合 demo。生产化可以用任务队列，比如 Celery / RQ / Dramatiq，记录 job 状态，支持增量索引、失败重试和索引版本切换。

## 18. 如何处理大文档？

参考答案：需要文档解析、按标题层级 chunking、去重、表格处理、分批 embedding、增量更新和 metadata 继承。超大文档还要做章节级摘要和父子 chunk。

## 19. 如何评测 RAG？

参考答案：当前使用 JSONL，检查 expected_source 命中、hit_rate、MRR 和 average_rank。生产化可以增加 answer faithfulness、context precision、人工标注集和线上反馈。

## 20. hit_rate 和 MRR 如何解释？

参考答案：hit_rate 表示期望来源是否出现在召回结果中。MRR 是 Mean Reciprocal Rank，越靠前命中分数越高，更能反映排序质量。

## 21. Agent 工具有哪些？

参考答案：当前展示的工具包括 `search_knowledge_base` 和 `analyze_csv`，另有受控文件读取能力和安全拒绝路径。面试中重点展示知识库查询、CSV 分析和拒绝危险请求。

## 22. Agent 如何避免危险操作？

参考答案：工具必须在白名单中，路径经过 guard，`.env` 请求直接拒绝，shell 删除请求没有执行工具。trace 也不会记录 secret 内容。

## 23. CSV 工具如何限制路径？

参考答案：CSV 分析只允许访问 `data/raw/data_analysis` 下的 CSV 文件，并校验后缀和路径是否在白名单目录内。

## 24. trace 有什么价值？

参考答案：trace 能回答“为什么选这个工具、传了什么参数、结果是什么、耗时多少”。它对 debug、审计、回归测试和面试展示都很重要。

## 25. LLM 调用失败怎么办？

参考答案：当前 demo 默认可使用 mock / OpenAI-compatible 接口。生产化应加入超时、重试、fallback model、错误分类、熔断和降级回答。

## 26. 如何切换 OpenAI / DeepSeek / Qwen / Ollama？

参考答案：项目预留 OpenAI-compatible provider 思路。只要模型服务兼容 OpenAI API 风格，就可以通过 base_url、model 和 api key 配置切换。Ollama 可以走本地 provider 或兼容网关。

## 27. 如何部署 Docker？

参考答案：项目有 Dockerfile 和 docker-compose。Dockerfile 复制 app、scripts、data 和 README，暴露 8765。docker-compose 提供 API 服务，并预留 postgres / pgvector profile。

## 28. 这个项目的局限性？

参考答案：FAISS 是本地单机，Simple Reranker 不是工业级 reranker，Eval 是轻量 JSONL，样例数据是模拟数据，没有做大规模并发压测，也没有完整后台管理前端。

## 29. 如果面试官说这是玩具项目怎么办？

参考答案：我会承认它不是生产集群，但说明它不是纯玩具。它覆盖多业务域、hybrid search、reranker、eval、trace、安全边界、Docker 和验收脚本。更准确的定位是 production-oriented demo。

## 30. 后续三个月怎么优化？

参考答案：第一个月接入服务化向量库和异步 ingestion；第二个月增强 reranker、eval 和 ACL；第三个月补管理界面、监控审计、压测和 CI eval 阈值。
