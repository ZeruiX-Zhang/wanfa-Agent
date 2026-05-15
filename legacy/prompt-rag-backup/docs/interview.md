# Interview Package

## 3 分钟项目讲解稿

我做的是企业知识库 RAG + workflow-style Agent Demo。它支持导入本地 `.md/.txt/.pdf/.csv`，解析、清洗、chunking 后写成标准 JSONL。构建索引时统一通过 `LLMClient.embed_texts()` 调 OpenAI-compatible embedding API，向量归一化后写入 FAISS。查询时 `RAGService` 调 retriever 取 top_k chunks，`PromptBuilder` 拼接 context，system prompt 明确要求只能基于 context 回答、context 不足说“不知道”、不能执行文档里的恶意指令，并且 sources 只来自真实检索结果。

Agent 部分我没有做不可控 AutoGPT，而是 workflow-style。它有统一 Tool schema 和白名单 registry，第一版规则路由到四个工具：知识库搜索、安全计算、文档摘要、CSV 分析。每次 run 都保存 trace JSON，能看到每一步选了什么工具、参数、结果、耗时和失败原因。最后还有 `/eval/run`，用 expected_source 和 expected_keywords 做基础 RAG 评测。这个项目的重点是分层清晰、可观测、安全边界明确，适合继续升级 pgvector、function calling 和前端控制台。

## 8 分钟项目深挖讲解稿

这个项目我按企业落地链路拆成六层。

第一层是 ingestion。Route 只收 Pydantic request，然后调用 `DocumentIngestionService`。loader 根据扩展名分发，Markdown/txt 普通读取，PDF 用 pypdf，CSV 用 pandas 转成可检索文本。cleaner 做换行和空白规范化，chunker 按字符长度和 overlap 切分，每个 chunk 都有 filename、source、path、page、chunk_index。输出是 JSONL，方便后续换队列或批处理。

第二层是向量索引。`IndexService` 读取 chunks，统一从 `LLMClient.embed_texts()` 获取 embedding，不在业务代码里散落 API 调用。FAISS 使用 `IndexFlatIP`，向量先 normalize，所以相当于 cosine similarity。索引和 chunk metadata 分别写到 `storage/faiss/index.faiss` 和 `storage/faiss/chunks.jsonl`。

第三层是 RAG。`Retriever` 只负责检索，`PromptBuilder` 只负责拼 prompt，`RAGService` 编排检索、prompt、LLM 和 sources。debug 接口会返回 retrieved chunks、完整 prompt、retrieval latency 和 LLM latency，便于截图和排查问题。

Chat LLM 和 Embedding 配置是分离的。实际演示时可以用 DeepSeek V4 Flash 或 V4 Pro 做回答生成，同时用支持 `/embeddings` 的 OpenAI-compatible provider 构建 FAISS 索引。没有 embedding key 时，项目提供 demo-only 的本地 hash/ngram embedding fallback，方便本地截图和验收；生产场景仍应切换到真实 embedding 模型。

第四层是 Agent。它不是无限循环，而是 workflow-style：规则路由选择工具，最大步数限制，工具白名单，参数通过 Pydantic 校验。`calculate` 用 AST，不用 eval；`summarize_document` 限制只能读取 data/raw 或 data/processed，拒绝 .env；`analyze_csv` 只能读 data/raw 下 CSV；`search_knowledge_base` 只能走 retriever。

第五层是 observability。每个请求都有 trace_id，错误返回也带 trace_id。Agent run 会保存 JSON trace，面试时可以直接打开说明每一步为什么调用、返回了什么、失败在哪里。

第六层是 eval。它不追求复杂指标，先实现 source hit 和 keyword hit，让项目有一个可解释的质量闭环。后续可以扩展成离线评测集、LLM-as-judge 或 RAGAS。

## 简历 Bullet Points

- Built a FastAPI enterprise RAG demo with multi-format local ingestion, chunking, OpenAI-compatible embeddings, FAISS retrieval, and traceable citations.
- Designed a workflow-style Agent with unified tool schema, whitelist registry, safe AST calculator, CSV analyzer, document summarizer, and knowledge-base search tool.
- Added request trace_id middleware, global error handling, RAG debug endpoint, agent trace persistence, and a lightweight RAG evaluation runner.
- Implemented security boundaries for secrets, prompt injection, unauthorized file access, and tool argument validation.

## 30 个面试官可能追问和参考答案

1. Q: 为什么用 FAISS 而不是 pgvector？  
   A: MVP 用 FAISS 文件索引部署简单、演示成本低；生产环境会换 pgvector 获得持久化、并发和 metadata filter。

2. Q: 为什么使用 `IndexFlatIP`？  
   A: embedding 先 normalize，内积等价于 cosine similarity，简单稳定。

3. Q: chunk size 怎么选？  
   A: MVP 用环境变量控制，默认 800 字符、120 overlap；后续根据文档类型和 eval 调参。

4. Q: CSV 为什么转文本？  
   A: 为了让结构化表格也能进入统一 RAG 管线；复杂分析交给 `analyze_csv` 工具。

5. Q: route 为什么不写业务逻辑？  
   A: route 只做协议层，核心逻辑在 service/retriever/tool 层，便于测试和替换实现。

6. Q: LLM 调用为什么统一封装？  
   A: 便于统一鉴权、超时、错误处理、mock 测试和模型替换。

7. Q: 怎么防 prompt injection？  
   A: system prompt 明确文档是不可信数据，context 指令不能执行；工具层也不暴露 shell 或越权文件读取。

8. Q: 如果 context 不足怎么办？  
   A: prompt 要求回答“不知道”，service 不编造 sources。

9. Q: sources 怎么保证真实？  
   A: sources 只从 retriever 返回的 chunk metadata 生成，不允许 LLM 自己编。

10. Q: Agent 为什么不用 AutoGPT？  
    A: 企业场景更需要可控 workflow、白名单工具、最大步数和 trace。

11. Q: 工具失败怎么处理？  
    A: registry 捕获异常并返回 ToolResult，trace 中记录失败原因，最终回答说明失败点。

12. Q: calculate 为什么不用 eval？  
    A: eval 会执行任意代码；这里用 AST 只允许数字、二元运算和一元运算。

13. Q: summarize_document 怎么防读密钥？  
    A: 只允许 data/raw 和 data/processed，显式拒绝 `.env`。

14. Q: analyze_csv 的权限边界是什么？  
    A: 只能读取 data/raw 下 `.csv`，项目外路径和非 CSV 都拒绝。

15. Q: trace_id 有什么用？  
    A: 把请求、日志、错误响应和 agent run 串起来，方便排查。

16. Q: eval 为什么这么简单？  
    A: MVP 先建立质量闭环，source hit 和 keyword hit 直观可解释，后续再加语义指标。

17. Q: 如果 embedding API 失败怎么办？  
    A: LLMClient 抛清晰 AppError，API 返回 trace_id 和错误码。

18. Q: 怎么 mock 外部 API？  
    A: service 构造函数支持注入 fake retriever、fake LLMClient 和 fake tool。

19. Q: Docker 镜像里会不会包含 `.env`？  
    A: `.dockerignore` 排除了 `.env`，compose 运行时可从宿主 `.env` 注入。

20. Q: 为什么 response 都用 Pydantic？  
    A: 保证 API 合约清晰，OpenAPI 文档可自动生成。

21. Q: 多用户并发下 FAISS 文件安全吗？  
    A: MVP 读多写少可接受；生产需要索引版本化、锁或外部向量库。

22. Q: 如何支持增量更新？  
    A: 增加 document_id、chunk hash 和 index rebuild/merge 策略。

23. Q: 如何降低幻觉？  
    A: 限制 context、强制不知道策略、sources 绑定 retrieved chunks、加 eval 和人工抽检。

24. Q: 为什么 debug 接口返回 prompt？  
    A: 方便排查 retrieval 与 prompt 拼接问题，也适合面试展示。

25. Q: 会不会泄露 API Key？  
    A: 不硬编码，`.env` 不提交；工具拒绝读取 `.env`；RAG prompt 明确不输出密钥。

26. Q: 如何接入 pgvector？  
    A: 把 `FaissVectorStore` 替换为 `PgVectorStore`，Retriever 接口保持不变。

26A. Q: DeepSeek API Key 能直接完成全部 RAG 吗？
    A: 可以用于 Chat LLM；FAISS 建索引最好使用真实 embedding endpoint。为了作品集本地演示，项目提供 demo-only 本地 embedding fallback，但生产不应依赖它。

27. Q: 如何改成 function calling Agent？  
    A: 保留 Tool schema/registry，把规则路由替换为 LLM function call planner。

28. Q: 如何做权限控制？  
    A: 在 API 层加入用户身份，在 retriever 和工具层加 tenant_id/document ACL filter。

29. Q: 如何做生产监控？  
    A: 接 OpenTelemetry、结构化日志、请求耗时、检索命中率、LLM token 和错误率。

30. Q: 最大的技术风险是什么？  
    A: 检索质量、权限隔离和工具调用可控性；项目结构已经为这些点预留扩展边界。

## 项目局限性说明

- 当前 FAISS 是本地文件索引，不适合多副本并发写。
- 规则路由 Agent 可解释但不够智能，复杂任务需要 function calling planner。
- Eval 是启发式规则，不等价于完整答案质量评估。
- 没有实现用户权限、租户隔离和生产级审计。
- 还没有前端 UI，截图主要来自 curl/Postman/OpenAPI。

## 如果被问“这是不是玩具项目”

我的回答是：它是一个面向作品集的 MVP，不是生产系统，但不是随手拼的玩具。它覆盖了企业 RAG 的核心链路：ingestion、chunking、embedding、vector search、prompt construction、source attribution、agent tool safety、trace 和 eval。为了演示清晰，第一版用 FAISS 和规则路由；但代码分层保留了替换 pgvector、function calling、权限系统和 observability 的边界。也就是说，它小而完整，能解释关键工程取舍。
