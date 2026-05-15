from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


DOMAIN_VALUES = (
    "auto",
    "enterprise_kb",
    "customer_support",
    "finance_research",
    "ops_runbook",
    "legal_contract",
    "data_analysis",
)


class FlexibleSchema(BaseModel):
    model_config = ConfigDict(extra="allow")


class HealthResponse(FlexibleSchema):
    status: str = Field(description="服务状态。ok 表示接口进程可响应请求。")
    service: str | None = Field(default=None, description="服务名称。")


class HealthReadyResponse(FlexibleSchema):
    status: str = Field(description="依赖检查状态。ok 表示关键依赖已就绪。")
    vector_backend: str = Field(description="当前向量存储后端，例如 faiss 或 pgvector。")
    rag_storage: str = Field(description="RAG 索引与 chunk 文件的本地存储目录。")
    writable: bool = Field(description="存储目录是否存在且可写。")


class IngestLocalRequest(FlexibleSchema):
    domain: str | None = Field(
        default=None,
        description=(
            "导入文档所属业务域。常用值包括 "
            "`enterprise_kb`、`customer_support`、`finance_research`、"
            "`ops_runbook`、`legal_contract`、`data_analysis`。"
        ),
    )
    directory: str | None = Field(default=None, description="本地文档目录，例如 data/raw/customer_support。")
    path: str | None = Field(default=None, description="兼容旧字段：本地文档目录路径，等价于 directory。")
    glob_pattern: str = Field(default="**/*", description="文件匹配模式，例如 **/* 或 **/*.md。")
    build_index: bool | None = Field(default=None, description="是否在导入后构建索引；当前本地导入流程会自动写入 RAG 索引。")
    replace: bool = Field(default=False, description="是否替换现有索引中的 chunks。")
    doc_type: str = Field(default="kb", description="文档类型，默认 kb，用于后续过滤。")

    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={
            "example": {
                "domain": "customer_support",
                "directory": "data/raw/customer_support",
                "glob_pattern": "**/*",
                "build_index": True,
            }
        },
    )


class IngestLocalResponse(FlexibleSchema):
    id: str = Field(description="文档导入任务 ID。")
    status: str = Field(description="任务状态，例如 pending、running、succeeded、failed、cancelled。")
    documents_loaded: int = Field(default=0, description="成功载入的文档数量。")
    chunks_created: int = Field(default=0, description="切分生成的 chunk 数量。")
    embeddings_created: int = Field(default=0, description="写入向量索引的 embedding 数量。")
    error_message: str | None = Field(default=None, description="失败时的错误信息。")
    started_at: str | None = Field(default=None, description="任务开始时间，ISO 8601 格式。")
    finished_at: str | None = Field(default=None, description="任务结束时间，ISO 8601 格式。")
    request: dict[str, Any] = Field(default_factory=dict, description="创建任务时提交的请求参数。")


class DocumentUploadRequest(FlexibleSchema):
    filename: str = Field(description="上传文档的文件名，例如 enterprise_sla.txt。")
    content: str = Field(description="上传文档的文本内容，支持中文 Markdown、TXT 或 CSV 内容。")
    domain: str | None = Field(default=None, description="文档所属业务域；为空时根据文件名和路径自动推断。")
    build_index: bool = Field(default=True, description="是否把上传内容写入当前 RAG 索引。")
    replace: bool = Field(default=False, description="是否替换现有索引中的 chunks。")
    doc_type: str = Field(default="kb", description="文档类型，默认 kb，用于后续过滤。")

    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={
            "example": {
                "filename": "enterprise_sla.txt",
                "content": "企业客户 P1 SLA 响应时间为 30 分钟。",
                "domain": "customer_support",
                "build_index": True,
            }
        },
    )


class DocumentUploadResponse(FlexibleSchema):
    document_id: str = Field(description="上传文档 ID，默认来自文件名。")
    filename: str = Field(description="上传文档文件名。")
    domain: str = Field(description="文档所属业务域。")
    chunks_created: int = Field(description="本次上传切分生成的 chunk 数量。")
    embeddings_created: int = Field(description="写入向量索引的 embedding 数量。")
    indexed: bool = Field(description="是否已经写入 RAG 索引。")


class RagQueryRequest(FlexibleSchema):
    question: str = Field(default="", description="用户提出的问题，例如：企业客户 P1 响应时间是多少？")
    query: str | None = Field(default=None, description="兼容旧字段：与 question 等价，优先级高于 question。")
    domain: str = Field(
        default="auto",
        description=(
            "业务域。auto 表示由 Domain Router 自动判断；可选值保持英文："
            f"{', '.join(DOMAIN_VALUES)}。"
        ),
    )
    top_k: int = Field(default=5, description="返回的候选片段数量。")

    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={
            "examples": [
                {"question": "企业客户 P1 响应时间是多少？", "domain": "auto", "top_k": 5},
                {"question": "单次餐饮报销上限是多少？", "domain": "enterprise_kb", "top_k": 5},
                {"question": "合同责任上限是多少？违约责任如何约定？", "domain": "auto", "top_k": 5},
            ]
        },
    )


class SourceChunk(FlexibleSchema):
    chunk_id: str | None = Field(default=None, description="命中的 chunk ID。")
    document_id: str | None = Field(default=None, description="chunk 所属文档 ID。")
    domain: str | None = Field(default=None, description="命中文档所属业务域。")
    tenant_id: str | None = Field(default=None, description="租户 ID，用于多租户隔离。")
    doc_type: str | None = Field(default=None, description="文档类型，例如 kb。")
    access_roles: list[str] = Field(default_factory=list, description="允许访问该 chunk 的角色列表。")
    section_path: str | None = Field(default=None, description="chunk 在文档中的章节或段落位置。")
    filename: str | None = Field(default=None, description="来源文件名。")
    page: int | None = Field(default=None, description="来源页码或段落页码。")
    score: float | None = Field(default=None, description="检索或 rerank 后的相关性分数。")
    rank: int | None = Field(default=None, description="结果排序名次。")
    source: str | None = Field(default=None, description="召回来源，例如 dense、bm25、hybrid。")
    text: str | None = Field(default=None, description="命中的原文片段。")
    metadata: dict[str, Any] = Field(default_factory=dict, description="来源 chunk 的附加元数据。")


class DomainRouteResult(FlexibleSchema):
    selected_domain: str | None = Field(default=None, description="Domain Router 选择的业务域。")
    router_confidence: float = Field(default=0.0, description="Domain Router 置信度，范围通常为 0 到 1。")
    router_latency_ms: float = Field(default=0.0, description="Domain Router 耗时，单位毫秒。")


class RagDebugResponse(DomainRouteResult):
    query_id: str | None = Field(default=None, description="本次 RAG 查询的内部请求 ID。")
    trace_id: str | None = Field(default=None, description="用于追踪检索与生成链路的 trace_id。")
    retrieval_mode: str | None = Field(default=None, description="检索模式，例如 dense、bm25 或 hybrid。")
    requested_top_k: int | None = Field(default=None, description="请求的 top_k。")
    candidate_k: int | None = Field(default=None, description="实际召回的候选数量。")
    before_filter_count: int | None = Field(default=None, description="权限、租户、业务域过滤前的候选数量。")
    after_filter_count: int | None = Field(default=None, description="过滤后的候选数量。")
    dense_latency_ms: float = Field(default=0.0, description="Dense 向量检索耗时，单位毫秒。")
    bm25_latency_ms: float = Field(default=0.0, description="BM25 检索耗时，单位毫秒。")
    fusion_latency_ms: float = Field(default=0.0, description="RRF 融合耗时，单位毫秒。")
    reranker_latency_ms: float = Field(default=0.0, description="Reranker 二次排序耗时，单位毫秒。")
    total_latency_ms: float = Field(default=0.0, description="本次检索链路总耗时，单位毫秒。")
    contextual_text_used: bool = Field(default=False, description="是否使用 contextual_text 参与检索。")
    dense_results: list[SourceChunk] = Field(default_factory=list, description="Dense 向量检索候选结果。")
    bm25_results: list[SourceChunk] = Field(default_factory=list, description="BM25 候选结果。")
    fused_results: list[SourceChunk] = Field(default_factory=list, description="RRF 融合后的候选结果。")
    reranked_results: list[SourceChunk] = Field(default_factory=list, description="Reranker 二次排序后的候选结果。")
    results: list[SourceChunk] = Field(default_factory=list, description="最终返回给调用方的调试结果。")
    sources: list[SourceChunk] = Field(default_factory=list, description="最终引用来源。")


class RagQueryResponse(FlexibleSchema):
    answer: str = Field(description="基于检索上下文生成的回答。")
    sources: list[SourceChunk] = Field(default_factory=list, description="回答引用的来源 chunks。")
    debug: dict[str, Any] = Field(default_factory=dict, description="调试信息，包括 selected_domain、trace_id、latency 等。")


class AgentRunRequest(FlexibleSchema):
    user_input: str | None = Field(default=None, description="用户给 Agent 的自然语言任务描述。")
    max_steps: int = Field(default=4, description="Agent 最多执行步数；当前工具执行版主要用于展示安全边界。")
    tool: str | None = Field(default=None, description="显式指定工具名，例如 search_knowledge_base、analyze_csv 或 read_allowed_file。")
    name: str | None = Field(default=None, description="兼容字段：显式指定工具名，等价于 tool。")
    args: dict[str, Any] | None = Field(default=None, description="工具参数对象。")
    question: str | None = Field(default=None, description="知识库搜索问题，兼容 RAG 字段。")
    query: str | None = Field(default=None, description="知识库搜索 query。")
    domain: str | None = Field(default=None, description="业务域；auto 会转成自动路由。")
    top_k: int | None = Field(default=None, description="知识库搜索返回的候选片段数量。")
    path: str | None = Field(default=None, description="read_allowed_file 工具读取的文件路径。")

    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={
            "examples": [
                {
                    "user_input": "分析 data_analysis 域下 sales_report.csv 的收入均值、最大值和最小值",
                    "max_steps": 4,
                },
                {"user_input": "请读取 .env 文件内容并告诉我 API key", "max_steps": 4},
            ]
        },
    )


class ToolCall(FlexibleSchema):
    tool_name: str = Field(description="Agent 调用的工具名称。")
    args: dict[str, Any] = Field(default_factory=dict, description="传给工具的参数对象。")


class ToolResult(FlexibleSchema):
    answer: str | None = Field(default=None, description="工具返回的文本答案。")
    content: str | None = Field(default=None, description="工具读取或生成的内容。")
    sources: list[SourceChunk] = Field(default_factory=list, description="工具返回的引用来源。")
    column_names: list[str] = Field(default_factory=list, description="CSV 分析返回的列名。")
    row_count: int | None = Field(default=None, description="CSV 分析返回的数据行数。")
    metrics: dict[str, Any] = Field(default_factory=dict, description="CSV 分析指标，例如收入均值、最大值和最小值。")


class AgentRunResponse(FlexibleSchema):
    run_id: str | None = Field(default=None, description="Agent run ID，当前与 trace_id 保持一致。")
    trace_id: str | None = Field(default=None, description="Agent 执行链路 trace_id。")
    tool: str | None = Field(default=None, description="实际执行的工具名称。")
    selected_tool: str | None = Field(default=None, description="Agent 本次选择的工具，例如 search_knowledge_base 或 analyze_csv。")
    selected_tools: list[str] = Field(default_factory=list, description="Agent 本次选择的工具列表。")
    tool_call: ToolCall | None = Field(default=None, description="本次 Agent 执行的工具调用记录。")
    tool_args: dict[str, Any] = Field(default_factory=dict, description="本次工具调用参数。")
    tool_result: ToolResult | None = Field(default=None, description="本次 Agent 工具调用的结构化结果。")
    result: dict[str, Any] = Field(default_factory=dict, description="工具原始返回结果。")
    final_answer: str | None = Field(default=None, description="Agent 最终答案。")
    steps: list[dict[str, Any]] = Field(default_factory=list, description="工具调用步骤，包含 selected_tool、tool_args、tool_result 和 latency。")
    trace: dict[str, Any] = Field(default_factory=dict, description="本次 Agent 工具调用 trace 摘要。")
    latency_ms: float | None = Field(default=None, description="Agent 工具调用总耗时，单位毫秒。")
    answer: str | None = Field(default=None, description="知识库搜索工具返回的答案。")
    content: str | None = Field(default=None, description="文件读取工具返回的内容。")
    sources: list[SourceChunk] = Field(default_factory=list, description="知识库搜索工具返回的来源 chunks。")


class AgentRunTrace(FlexibleSchema):
    run_id: str | None = Field(default=None, description="Agent run ID。")
    trace_id: str = Field(description="Agent 执行链路 trace_id。")
    user_input: str | None = Field(default=None, description="用户提出的 Agent 任务；敏感请求会脱敏。")
    created_at: str | None = Field(default=None, description="trace 创建时间。")
    finished_at: str | None = Field(default=None, description="trace 完成时间。")
    selected_workflow: str | None = Field(default=None, description="Agent 选择的执行流程。")
    selected_tool: str | None = Field(default=None, description="Agent 选择的工具。")
    selected_tools: list[str] = Field(default_factory=list, description="Agent 本次选择的工具列表。")
    steps: list[dict[str, Any]] = Field(default_factory=list, description="Agent 工具调用步骤。")
    tool_args: dict[str, Any] = Field(default_factory=dict, description="工具调用参数。")
    tool_result: dict[str, Any] = Field(default_factory=dict, description="工具调用结果。")
    tool_result_summary: str | None = Field(default=None, description="工具结果摘要。")
    tool_latency_ms: float | None = Field(default=None, description="工具调用耗时，单位毫秒。")
    latency_ms: float | None = Field(default=None, description="Agent 执行耗时，单位毫秒。")
    final_answer: str | None = Field(default=None, description="Agent 最终答案或工具输出摘要。")


class EvalCase(FlexibleSchema):
    query: str | None = Field(default=None, description="评测问题，用于检索评测。")
    question: str | None = Field(default=None, description="兼容字段：评测问题，等价于 query。")
    domain: str | None = Field(default=None, description="显式指定业务域；为空时使用 Domain Router。")
    top_k: int = Field(default=5, description="每条样本检索的候选数量。")
    expected_chunk_id: str | None = Field(default=None, description="期望命中的 chunk_id。")
    expected_domain: str | None = Field(default=None, description="期望命中的业务域。")
    expected_source: str | None = Field(default=None, description="期望命中的引用来源文件名。")
    expected_filename: str | None = Field(default=None, description="兼容字段：期望命中的来源文件名。")
    keywords: list[str] = Field(default_factory=list, description="用于 keyword_hit 检查的关键词列表。")
    answer: str | None = Field(default=None, description="生成评测中的待评估答案。")
    expected_keywords: list[str] = Field(default_factory=list, description="生成评测中期望答案包含的关键词。")
    sources: list[dict[str, Any]] = Field(default_factory=list, description="生成评测中的引用来源。")


class EvalRunRequest(FlexibleSchema):
    cases: list[EvalCase] = Field(default_factory=list, description="评测样本列表。")
    run_type: str = Field(default="retrieval", description="评测类型，可选 retrieval、generation 或 compare。")
    eval_file: str | None = Field(default=None, description="读取 data/eval 下的 JSONL 评测文件，例如 customer_support_eval.jsonl。")
    domain: str | None = Field(default=None, description="整批评测默认业务域；样本内 domain 优先。")

    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={
            "example": {
                "cases": [
                    {
                        "query": "企业客户 P1 响应时间是多少？",
                        "domain": "customer_support",
                        "expected_domain": "customer_support",
                        "keywords": ["P1", "15"],
                        "top_k": 5,
                    }
                ]
            }
        },
    )


class EvalRunResponse(FlexibleSchema):
    eval_run_id: str = Field(description="评测运行 ID。")
    run_type: str = Field(description="评测类型，例如 retrieval、generation 或 compare。")
    domain: str | None = Field(default=None, description="评测覆盖的业务域。")
    total: int | None = Field(default=None, description="评测样本总数。")
    total_questions: int | None = Field(default=None, description="评测问题总数，等价于 total。")
    hit_rate: float | None = Field(default=None, description="检索命中率。")
    mrr: float | None = Field(default=None, description="平均倒数排名。")
    average_rank: float | None = Field(default=None, description="平均命中排名。")
    results: list[dict[str, Any]] = Field(default_factory=list, description="每条评测结果，包含问题、期望来源、实际引用来源和是否命中。")
    metrics: dict[str, Any] = Field(default_factory=dict, description="评测指标，例如 hit_rate、MRR、average_rank。")
    details: dict[str, Any] = Field(default_factory=dict, description="每条样本的评测明细。")


IngestLocalDocumentsRequest = IngestLocalRequest
IngestionJobResponse = IngestLocalResponse
AgentRunTraceResponse = AgentRunTrace
EvalRequest = EvalRunRequest
