from __future__ import annotations

import ast
import operator
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from analyst_core.service import run_analysis
from platform_common.settings import get_settings
from rag_core.rag.service import RequestContext, rag_service
from workflow_core.tools.ticket_tool import create_ticket


RiskLevel = Literal["low", "medium", "high"]


class ToolExecutionError(RuntimeError):
    pass


class SearchKnowledgeArgs(BaseModel):
    query: str = Field(min_length=1)
    domain: str | None = None
    top_k: int = Field(default=5, ge=1, le=20)


class CreateTicketArgs(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=4000)
    scenario: str = "customer_support"
    severity: str = "P2"
    ticket_type: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SummarizeConversationArgs(BaseModel):
    messages: list[str] = Field(default_factory=list)
    max_sentences: int = Field(default=3, ge=1, le=8)


class GenerateCustomerReplyArgs(BaseModel):
    customer_message: str = Field(min_length=1)
    context: str = ""
    tone: str = "professional"


class QueryDataAgentArgs(BaseModel):
    question: str = Field(min_length=1, max_length=500)


class MathArgs(BaseModel):
    expression: str = Field(min_length=1, max_length=200)


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: type[BaseModel]
    output_schema: dict[str, Any]
    risk_level: RiskLevel = "low"
    requires_confirmation: bool = False
    timeout_seconds: int = 10
    examples: list[dict[str, Any]] = field(default_factory=list)
    handler: Callable[[BaseModel], dict[str, Any]] | None = None

    def public_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema.model_json_schema(),
            "output_schema": self.output_schema,
            "risk_level": self.risk_level,
            "requires_confirmation": self.requires_confirmation,
            "timeout_seconds": self.timeout_seconds,
            "examples": self.examples,
        }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def list_specs(self) -> list[dict[str, Any]]:
        return [spec.public_dict() for spec in sorted(self._tools.values(), key=lambda item: item.name)]

    def validate_args(self, name: str, args: dict[str, Any]) -> BaseModel:
        spec = self._require(name)
        return spec.input_schema.model_validate(args)

    def execute(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        spec = self._require(name)
        try:
            parsed = spec.input_schema.model_validate(args)
        except ValidationError as exc:
            raise ToolExecutionError(str(exc)) from exc
        if spec.requires_confirmation:
            return {
                "status": "pending_confirmation",
                "tool": name,
                "args": parsed.model_dump(),
                "reason": f"{name} is {spec.risk_level} risk and requires confirmation.",
            }
        if spec.handler is None:
            raise ToolExecutionError(f"Tool {name} has no handler")
        started = time.perf_counter()
        result = spec.handler(parsed)
        result.setdefault("latency_ms", round((time.perf_counter() - started) * 1000, 3))
        return result

    def _require(self, name: str) -> ToolSpec:
        spec = self._tools.get(name)
        if spec is None:
            raise ToolExecutionError(f"Unknown tool: {name}")
        return spec


def _search_knowledge_base(args: BaseModel) -> dict[str, Any]:
    parsed = SearchKnowledgeArgs.model_validate(args)
    settings = get_settings()
    payload = rag_service.query(
        query=parsed.query,
        top_k=parsed.top_k,
        domain=parsed.domain,
        context=RequestContext(tenant_id=settings.default_tenant_id, roles=settings.default_roles),
    )
    return {"status": "completed", "answer": payload["answer"], "sources": payload.get("sources", []), "debug": payload.get("debug", {})}


def _create_ticket(args: BaseModel) -> dict[str, Any]:
    parsed = CreateTicketArgs.model_validate(args)
    ticket = create_ticket(**parsed.model_dump())
    return {"status": "completed", "ticket": ticket.model_dump()}


def _summarize_conversation(args: BaseModel) -> dict[str, Any]:
    parsed = SummarizeConversationArgs.model_validate(args)
    text = " ".join(message.strip() for message in parsed.messages if message.strip())
    sentences = [part.strip() for part in text.replace("?", ".").replace("!", ".").split(".") if part.strip()]
    summary = ". ".join(sentences[: parsed.max_sentences])
    return {"status": "completed", "summary": summary or text[:400]}


def _generate_customer_reply(args: BaseModel) -> dict[str, Any]:
    parsed = GenerateCustomerReplyArgs.model_validate(args)
    reply = (
        "Thanks for the details. "
        "Based on the available context, I will help verify the issue and share the next step. "
        f"Context: {parsed.context[:300]}"
    )
    return {"status": "completed", "reply": reply, "tone": parsed.tone}


def _query_data_agent(args: BaseModel) -> dict[str, Any]:
    parsed = QueryDataAgentArgs.model_validate(args)
    result = run_analysis(parsed.question, include_trace=True, enable_internal_trace=False)
    return {
        "status": result.status,
        "answer": result.final_answer,
        "generated_sql": result.sql,
        "row_count": result.row_count,
        "artifacts": [artifact.model_dump() for artifact in result.data_artifacts],
        "trace_id": result.trace_id,
    }


ALLOWED_MATH_NODES = {
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Constant,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
    ast.USub,
    ast.UAdd,
}
OPERATORS: dict[type[ast.AST], Callable[[Any, Any], Any]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}


def _safe_eval(node: ast.AST) -> float:
    if type(node) not in ALLOWED_MATH_NODES:
        raise ValueError("Only numeric expressions are allowed")
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.UnaryOp):
        value = _safe_eval(node.operand)
        return -value if isinstance(node.op, ast.USub) else value
    if isinstance(node, ast.BinOp):
        return float(OPERATORS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right)))
    raise ValueError("Unsupported math expression")


def _simple_python_math(args: BaseModel) -> dict[str, Any]:
    parsed = MathArgs.model_validate(args)
    expression = ast.parse(parsed.expression, mode="eval")
    return {"status": "completed", "result": _safe_eval(expression), "expression": parsed.expression}


def get_default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(ToolSpec("search_knowledge_base", "Search the enterprise knowledge base and return citations.", SearchKnowledgeArgs, {"type": "object"}, "low", False, 10, [{"query": "P1 SLA response time"}], _search_knowledge_base))
    registry.register(ToolSpec("create_ticket_mock", "Create a mock support or incident ticket after confirmation.", CreateTicketArgs, {"type": "object"}, "high", True, 10, [{"title": "P1 incident", "description": "Payment errors"}], _create_ticket))
    registry.register(ToolSpec("summarize_conversation", "Summarize a user or support conversation.", SummarizeConversationArgs, {"type": "object"}, "low", False, 5, [{"messages": ["customer cannot login", "support reset password"]}], _summarize_conversation))
    registry.register(ToolSpec("generate_customer_reply", "Draft a customer-facing reply from context.", GenerateCustomerReplyArgs, {"type": "object"}, "medium", False, 10, [{"customer_message": "I cannot login"}], _generate_customer_reply))
    registry.register(ToolSpec("query_data_agent", "Ask the data analyst agent a schema-grounded question.", QueryDataAgentArgs, {"type": "object"}, "medium", False, 15, [{"question": "2025 revenue by quarter"}], _query_data_agent))
    registry.register(ToolSpec("simple_python_math", "Evaluate a safe numeric expression.", MathArgs, {"type": "object"}, "low", False, 3, [{"expression": "(10 + 5) / 3"}], _simple_python_math))
    registry.register(ToolSpec("create_ticket", "Alias for high-risk ticket creation.", CreateTicketArgs, {"type": "object"}, "high", True, 10, [], _create_ticket))
    registry.register(ToolSpec("notify_human_agent", "High-risk human notification placeholder.", CreateTicketArgs, {"type": "object"}, "high", True, 10, [], _create_ticket))
    return registry
