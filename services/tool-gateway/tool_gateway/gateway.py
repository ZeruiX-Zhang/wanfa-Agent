"""Tool gateway shell with disabled-by-default execution policy."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable
from uuid import uuid4


class RiskLevel(str, Enum):
    """Tool execution risk levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ToolResultStatus(str, Enum):
    """Result states for gateway requests."""

    DISABLED = "disabled"
    DRY_RUN = "dry_run"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"


HIGH_RISK_TERMS = frozenset(
    {
        "delete",
        "remove",
        "write",
        "overwrite",
        "move",
        "rename",
        "exec",
        "shell",
        "deploy",
        "network",
        "external",
        "secret",
        "credential",
        "api_key",
        "env",
        "package.json",
        "scripts",
        "legacy",
    }
)

SECRET_TERMS = frozenset({"secret", "token", "password", "api_key", "authorization"})


@dataclass(frozen=True, slots=True)
class ToolExecutionRequest:
    """A request to execute a tool through the gateway."""

    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    requested_by: str = "supervisor"
    approval_id: str | None = None
    request_id: str = field(default_factory=lambda: f"tool_req_{uuid4().hex[:12]}")


@dataclass(frozen=True, slots=True)
class ToolPolicy:
    """Execution policy for tool calls.

    execution_enabled remains false by default. Even when enabled by a future
    host adapter, high-risk actions still require an approved request id.
    """

    execution_enabled: bool = False
    dry_run: bool = True
    approved_request_ids: frozenset[str] = frozenset()
    allowed_tools: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class ToolExecutionResult:
    """Gateway response with no raw secret leakage."""

    request_id: str
    tool_name: str
    status: ToolResultStatus
    dry_run: bool
    execution_disabled: bool
    risk_level: RiskLevel
    approval_required: bool
    message: str
    arguments_preview: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to API-safe primitives."""

        return {
            "request_id": self.request_id,
            "tool_name": self.tool_name,
            "status": self.status.value,
            "dry_run": self.dry_run,
            "execution_disabled": self.execution_disabled,
            "risk_level": self.risk_level.value,
            "approval_required": self.approval_required,
            "message": self.message,
            "arguments_preview": self.arguments_preview,
        }


Executor = Callable[[ToolExecutionRequest], dict[str, Any]]


class ToolGateway:
    """Small policy gate for tool execution.

    The gateway never executes by itself. A trusted host must explicitly pass an
    executor and enable execution; this keeps tool execution mock-safe by default.
    """

    def __init__(self, policy: ToolPolicy | None = None, executor: Executor | None = None) -> None:
        self.policy = policy or ToolPolicy()
        self._executor = executor

    def assess_risk(self, request: ToolExecutionRequest) -> RiskLevel:
        """Assess risk using conservative name and argument heuristics."""

        haystack = f"{request.tool_name} {request.arguments}".lower()
        if any(term in haystack for term in ("secret", "credential", "api_key", "password")):
            return RiskLevel.CRITICAL
        if any(term in haystack for term in HIGH_RISK_TERMS):
            return RiskLevel.HIGH
        if "http" in haystack or "file" in haystack or "url" in haystack:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    def requires_approval(self, request: ToolExecutionRequest) -> bool:
        """Return true when a request needs explicit approval."""

        return self.assess_risk(request) in {RiskLevel.HIGH, RiskLevel.CRITICAL}

    def execute(self, request: ToolExecutionRequest) -> ToolExecutionResult:
        """Gate a tool call and default to disabled/dry-run behavior."""

        risk_level = self.assess_risk(request)
        approval_required = risk_level in {RiskLevel.HIGH, RiskLevel.CRITICAL}
        arguments_preview = redact_mapping(request.arguments)

        if self.policy.allowed_tools and request.tool_name not in self.policy.allowed_tools:
            return ToolExecutionResult(
                request_id=request.request_id,
                tool_name=request.tool_name,
                status=ToolResultStatus.DISABLED,
                dry_run=True,
                execution_disabled=True,
                risk_level=risk_level,
                approval_required=approval_required,
                message="Tool is not in the allowlist.",
                arguments_preview=arguments_preview,
            )

        if approval_required and request.request_id not in self.policy.approved_request_ids:
            return ToolExecutionResult(
                request_id=request.request_id,
                tool_name=request.tool_name,
                status=ToolResultStatus.WAITING_APPROVAL,
                dry_run=True,
                execution_disabled=True,
                risk_level=risk_level,
                approval_required=True,
                message="High-risk action requires approval before execution.",
                arguments_preview=arguments_preview,
            )

        if not self.policy.execution_enabled or self.policy.dry_run or self._executor is None:
            return ToolExecutionResult(
                request_id=request.request_id,
                tool_name=request.tool_name,
                status=ToolResultStatus.DRY_RUN,
                dry_run=True,
                execution_disabled=not self.policy.execution_enabled,
                risk_level=risk_level,
                approval_required=approval_required,
                message="Dry-run only; no real tool execution occurred.",
                arguments_preview=arguments_preview,
            )

        try:
            result = self._executor(request)
        except Exception as exc:
            return ToolExecutionResult(
                request_id=request.request_id,
                tool_name=request.tool_name,
                status=ToolResultStatus.FAILED,
                dry_run=False,
                execution_disabled=False,
                risk_level=risk_level,
                approval_required=approval_required,
                message=f"Executor failed: {exc.__class__.__name__}",
                arguments_preview=arguments_preview,
            )

        return ToolExecutionResult(
            request_id=request.request_id,
            tool_name=request.tool_name,
            status=ToolResultStatus.COMPLETED,
            dry_run=False,
            execution_disabled=False,
            risk_level=risk_level,
            approval_required=approval_required,
            message=str(result.get("message", "Tool execution completed.")),
            arguments_preview=arguments_preview,
        )


def redact_mapping(arguments: dict[str, Any]) -> dict[str, Any]:
    """Return a shallow redacted copy of request arguments."""

    redacted: dict[str, Any] = {}
    for key, value in arguments.items():
        key_text = str(key).lower()
        if any(term in key_text for term in SECRET_TERMS):
            redacted[str(key)] = "[redacted]"
            continue
        redacted[str(key)] = value
    return redacted
