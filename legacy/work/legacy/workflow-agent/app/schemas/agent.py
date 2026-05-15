from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


ScenarioType = Literal[
    "customer_support",
    "finance_research",
    "ops_runbook",
    "unsafe_request",
    "unknown",
]

IntentType = Literal[
    "knowledge_question",
    "technical_issue",
    "complaint",
    "refund_or_after_sales",
    "handoff_to_human",
    "create_ticket_request",
    "financial_analysis",
    "financial_summary",
    "incident_troubleshooting",
    "incident_escalation",
    "unsafe_request",
    "unknown",
]

RunStatus = Literal["completed", "waiting_approval", "rejected", "error"]
ToolStatus = Literal["success", "error"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Source(BaseModel):
    title: str = Field(default="", description="知识库来源标题", examples=["SLA 服务等级协议"])
    url: str | None = Field(default=None, description="来源 URL，如 RAG 返回则透传")
    document_id: str | None = Field(default=None, description="文档 ID")
    chunk_id: str | None = Field(default=None, description="切片 ID")
    score: float | None = Field(default=None, description="检索相关性分数")
    snippet: str | None = Field(default=None, description="引用片段")


class ScenarioRouteResult(BaseModel):
    scenario: ScenarioType = Field(description="业务场景分类结果")
    confidence: float = Field(ge=0, le=1, description="分类置信度")
    reason: str = Field(description="中文分类理由")


class IntentResult(BaseModel):
    intent: IntentType = Field(description="意图分类结果")
    confidence: float = Field(ge=0, le=1, description="意图分类置信度")
    reason: str = Field(description="中文意图识别理由")


class PendingAction(BaseModel):
    tool: Literal["create_ticket", "notify_human_agent"] = Field(description="等待人工审批的写操作工具")
    args: dict[str, Any] = Field(default_factory=dict, description="审批通过后执行的工具参数")
    reason: str = Field(description="为什么需要人工审批")


class ToolStep(BaseModel):
    name: str = Field(description="工具名称")
    status: ToolStatus = Field(description="工具执行状态")
    args: dict[str, Any] = Field(default_factory=dict, description="已脱敏的工具参数")
    result: Any | None = Field(default=None, description="已脱敏的工具结果")
    error: str | None = Field(default=None, description="工具错误信息")
    started_at: str = Field(default_factory=utc_now, description="开始时间")
    ended_at: str = Field(default_factory=utc_now, description="结束时间")


class RAGSearchResult(BaseModel):
    answer: str = Field(default="", description="RAG 返回的答案")
    sources: list[Source] = Field(default_factory=list, description="RAG 返回的 citations / sources")
    domain: str = Field(default="auto", description="实际检索 domain")
    error: str | None = Field(default=None, description="RAG 不可用或返回异常时的错误")
    raw: dict[str, Any] = Field(default_factory=dict, description="脱敏后的 RAG 原始结果摘要")


class CSVAnalysisResult(BaseModel):
    columns: list[str] = Field(description="CSV 列名")
    row_count: int = Field(description="CSV 行数")
    quarter_summary: dict[str, dict[str, float]] = Field(description="按季度聚合结果")
    region_summary: dict[str, dict[str, float]] = Field(description="按区域聚合结果")
    metrics_summary: dict[str, dict[str, float]] = Field(description="数值列均值、最大值、最小值")
    growth_rates: dict[str, float] = Field(description="按区域计算的营收增长率")
    fastest_growth_region: str | None = Field(description="营收增长最快区域")
    calculation_logic: str = Field(description="中文计算逻辑说明")


class Ticket(BaseModel):
    ticket_id: str = Field(description="工单或通知 ID")
    ticket_type: Literal["customer_ticket", "incident_ticket", "notification"] = Field(description="记录类型")
    title: str = Field(description="标题")
    description: str = Field(description="详情")
    severity: Literal["P0", "P1", "P2", "P3", "unknown"] = Field(default="unknown", description="严重级别")
    scenario: ScenarioType = Field(description="所属业务场景")
    status: str = Field(default="created", description="状态")
    created_at: str = Field(default_factory=utc_now, description="创建时间")
    metadata: dict[str, Any] = Field(default_factory=dict, description="附加信息")


class AgentRunRequest(BaseModel):
    user_input: str = Field(
        min_length=1,
        max_length=4000,
        description="用户输入的中文业务请求",
        examples=["企业客户 P1 问题多久响应？"],
    )
    max_steps: int = Field(default=6, ge=1, le=20, description="单次 workflow 最大工具步数")


class AgentRunResponse(BaseModel):
    run_id: str = Field(description="运行 ID")
    status: RunStatus = Field(description="运行状态")
    scenario: ScenarioType = Field(description="业务场景")
    intent: IntentType = Field(description="用户意图")
    approval_required: bool = Field(description="是否需要人工审批")
    pending_action: PendingAction | None = Field(default=None, description="待审批动作")
    final_answer: str = Field(description="最终中文回答")
    sources: list[Source] = Field(default_factory=list, description="使用到的知识库来源")
    tool_steps: list[ToolStep] = Field(default_factory=list, description="工具执行轨迹")
    trace_url: str = Field(description="Trace 查询路径")


class AgentApproveRequest(BaseModel):
    approved: bool = Field(default=True, description="是否批准 pending action")
    comment: str | None = Field(default=None, max_length=1000, description="审批备注")


class AgentApproveResponse(BaseModel):
    run_id: str = Field(description="运行 ID")
    status: RunStatus = Field(description="审批后的状态")
    approval_executed: bool = Field(description="是否实际执行了写操作")
    pending_action: PendingAction | None = Field(default=None, description="剩余待审批动作")
    final_answer: str = Field(description="审批结果中文说明")
    ticket_id: str | None = Field(default=None, description="创建的工单或通知 ID")


class AgentTrace(BaseModel):
    run_id: str = Field(description="运行 ID")
    user_input: str = Field(description="原始用户输入")
    scenario: ScenarioType = Field(description="业务场景")
    intent: IntentType = Field(description="用户意图")
    status: RunStatus = Field(description="运行状态")
    approval_required: bool = Field(description="是否需要人工审批")
    pending_action: PendingAction | None = Field(default=None, description="待审批动作")
    final_answer: str = Field(description="最终中文回答")
    sources: list[Source] = Field(default_factory=list, description="引用来源")
    tool_steps: list[ToolStep] = Field(default_factory=list, description="工具轨迹")
    safety: dict[str, Any] = Field(default_factory=dict, description="安全检查结果")
    max_steps: int = Field(default=6, description="本次运行最大工具步数")
    created_at: str = Field(default_factory=utc_now, description="创建时间")
    updated_at: str = Field(default_factory=utc_now, description="更新时间")


class ErrorResponse(BaseModel):
    code: str = Field(description="错误码")
    message: str = Field(description="中文错误信息")
    details: dict[str, Any] | None = Field(default=None, description="错误详情")


class HealthResponse(BaseModel):
    status: str = Field(description="服务状态", examples=["ok"])
    name: str = Field(description="服务名称", examples=["多业务场景 Workflow Agent 演示系统"])
    rag_base_url: str = Field(description="外部 RAG 服务地址")
