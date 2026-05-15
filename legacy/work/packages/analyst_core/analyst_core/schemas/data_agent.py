from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


AnalysisType = Literal[
    "sales_trend",
    "regional_growth",
    "channel_conversion",
    "customer_support",
    "profitability",
    "general_query",
]

ChartType = Literal["bar", "line", "pie", "none"]


class ErrorResponse(BaseModel):
    """标准错误响应。"""

    code: str = Field(description="错误代码", examples=["unauthorized"])
    message: str = Field(description="中文错误说明", examples=["缺少或无效的 API Key"])
    trace_id: str | None = Field(default=None, description="可选 trace id")


class DataAgentQueryRequest(BaseModel):
    """自然语言数据分析请求。"""

    question: str = Field(
        min_length=1,
        max_length=500,
        description="中文业务问题，系统会基于 schema grounding 生成只读 SQL",
        examples=["2025 年各季度营收变化趋势是什么？"],
    )
    include_trace: bool = Field(default=True, description="是否在响应中返回 trace_url")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"question": "哪个渠道转化率最低？", "include_trace": True},
            ]
        }
    )


class SQLValidationRequest(BaseModel):
    """SQL 安全校验请求。"""

    sql: str = Field(
        min_length=1,
        max_length=5000,
        description="待校验 SQL，仅允许 SELECT",
        examples=["SELECT region, SUM(revenue) AS total_revenue FROM orders GROUP BY region"],
    )


class SQLPlan(BaseModel):
    """结构化 SQL 分析计划，模拟 Structured Outputs / JSON Schema 输出。"""

    question: str = Field(description="原始业务问题")
    analysis_type: AnalysisType = Field(description="分析类型")
    tables: list[str] = Field(description="本次分析使用的数据表")
    sql: str = Field(description="候选 SQL，后续必须经过 SQL Safety Checker")
    chart_type: ChartType = Field(description="建议图表类型")
    explanation: str = Field(description="中文 SQL 计划说明")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "question": "2025 年各季度营收变化趋势是什么？",
                    "analysis_type": "sales_trend",
                    "tables": ["orders"],
                    "sql": "SELECT quarter, total_revenue FROM ...",
                    "chart_type": "line",
                    "explanation": "按季度聚合 2025 年订单收入。",
                }
            ]
        }
    )


class SQLValidationResult(BaseModel):
    """SQL Safety Checker 结果。"""

    is_valid: bool = Field(description="是否通过安全校验")
    original_sql: str = Field(description="原始 SQL")
    sanitized_sql: str | None = Field(default=None, description="追加 LIMIT 后的只读 SQL")
    reasons: list[str] = Field(default_factory=list, description="校验原因或拒绝原因")
    blocked_keywords: list[str] = Field(default_factory=list, description="命中的危险关键字")
    enforced_limit: int | None = Field(default=None, description="强制追加的最大 LIMIT")
    max_result_rows: int = Field(description="允许返回的最大行数")


class SQLExecutionResult(BaseModel):
    """只读 SQL 执行结果。"""

    executed_sql: str = Field(description="实际执行的 SQL")
    columns: list[str] = Field(default_factory=list, description="结果列名")
    rows: list[dict[str, Any]] = Field(default_factory=list, description="表格结果行")
    row_count: int = Field(default=0, description="返回行数")
    elapsed_ms: int = Field(default=0, description="SQL 执行耗时，单位毫秒")
    error: str | None = Field(default=None, description="执行错误")


class ChartSpec(BaseModel):
    """图表生成计划。"""

    chart_type: ChartType = Field(description="图表类型")
    x_column: str | None = Field(default=None, description="X 轴字段")
    y_column: str | None = Field(default=None, description="Y 轴字段")
    title: str = Field(default="AI 数据分析图表", description="图表标题")


class ChartResult(BaseModel):
    """图表生成结果。"""

    chart_type: ChartType = Field(description="图表类型")
    chart_path: str | None = Field(default=None, description="图表文件路径")
    chart_url: str | None = Field(default=None, description="可访问的图表 URL")
    chart_error: str | None = Field(default=None, description="图表生成失败原因")
    generated: bool = Field(default=False, description="是否生成图表")


class ColumnInfo(BaseModel):
    """字段元信息。"""

    name: str = Field(description="字段名")
    type: str = Field(description="SQLite 字段类型")
    description: str = Field(description="中文字段说明")
    sample_values: list[Any] = Field(default_factory=list, description="样例值")


class TableSchema(BaseModel):
    """数据表 schema。"""

    name: str = Field(description="表名")
    description: str = Field(description="中文表说明")
    row_count: int = Field(description="表行数")
    columns: list[ColumnInfo] = Field(description="字段列表")


class SchemaInfo(BaseModel):
    """Schema Grounding 返回信息。"""

    database: str = Field(description="数据库路径")
    generated_at: datetime = Field(description="schema 生成时间")
    tables: list[TableSchema] = Field(description="数据表 schema 列表")


class DataAgentTrace(BaseModel):
    """单次数据分析审计 trace。"""

    run_id: str
    trace_id: str
    question: str
    schema_used: list[str]
    sql_plan: SQLPlan | None = None
    sql_validation: SQLValidationResult
    executed_sql: str | None = None
    row_count: int = 0
    chart_result: ChartResult | None = None
    final_answer: str
    latency_ms: int
    created_at: datetime
    finished_at: datetime


class DataAgentQueryResponse(BaseModel):
    """Data Analyst Agent 查询响应。"""

    run_id: str = Field(description="本次运行 ID")
    trace_id: str = Field(description="审计 trace ID")
    status: Literal["completed", "rejected", "failed"] = Field(description="查询状态")
    question: str = Field(description="原始问题")
    final_answer: str = Field(description="中文业务结论")
    sql_plan: SQLPlan | None = Field(default=None, description="结构化 SQL 计划")
    sql: str | None = Field(default=None, description="通过校验后的 SQL")
    table_columns: list[str] = Field(default_factory=list, description="表格列")
    table_rows: list[dict[str, Any]] = Field(default_factory=list, description="表格结果")
    row_count: int = Field(default=0, description="结果行数")
    query_latency_ms: int = Field(default=0, description="整体查询耗时")
    sql_validation: SQLValidationResult = Field(description="SQL 安全校验结果")
    execution: SQLExecutionResult | None = Field(default=None, description="SQL 执行结果")
    chart: ChartResult | None = Field(default=None, description="图表结果")
    chart_url: str | None = Field(default=None, description="图表 URL")
    trace_url: str | None = Field(default=None, description="trace 查询 URL")
    created_at: datetime = Field(description="创建时间")
    finished_at: datetime = Field(description="完成时间")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "run_id": "run_123",
                    "trace_id": "trace_123",
                    "status": "completed",
                    "question": "哪个渠道转化率最低？",
                    "final_answer": "转化率最低的渠道是伙伴渠道。",
                    "sql": "SELECT * FROM (...) AS safe_query LIMIT 100",
                    "table_columns": ["channel", "conversion_rate"],
                    "table_rows": [{"channel": "伙伴渠道", "conversion_rate": 0.08}],
                    "row_count": 1,
                    "query_latency_ms": 123,
                    "chart_url": "/data-agent/charts/run_123.png",
                    "trace_url": "/data-agent/runs/run_123",
                }
            ]
        }
    )


class HealthResponse(BaseModel):
    """健康检查响应。"""

    status: Literal["ok"] = Field(description="服务状态")
    service: str = Field(description="服务名称")
    database_exists: bool = Field(description="数据库文件是否存在")
    app_env: str = Field(description="当前环境")

