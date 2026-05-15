"""Pure Python workflow schemas for the Phase 9 supervisor shell.

The module intentionally avoids framework dependencies so the API adapter can
wrap these dataclasses later without forcing a storage or web framework choice.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


def new_id(prefix: str) -> str:
    """Create a stable, human-readable identifier."""

    return f"{prefix}_{uuid4().hex[:12]}"


def utc_now() -> str:
    """Return an ISO-8601 UTC timestamp."""

    return datetime.now(timezone.utc).isoformat()


class SerializableEnum(str, Enum):
    """Enum base that serializes as its value."""

    def __str__(self) -> str:
        return self.value


class WorkflowStatus(SerializableEnum):
    """Lifecycle states for a workflow."""

    PLANNED = "planned"
    RUNNING = "running"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentTaskStatus(SerializableEnum):
    """Lifecycle states for an agent task."""

    PENDING = "pending"
    RUNNING = "running"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentStepStatus(SerializableEnum):
    """Lifecycle states for an agent step."""

    PENDING = "pending"
    DRY_RUN = "dry_run"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"


class ToolCallStatus(SerializableEnum):
    """Tool call states exposed to the supervisor."""

    DISABLED = "disabled"
    DRY_RUN = "dry_run"
    WAITING_APPROVAL = "waiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    FAILED = "failed"


class ApprovalStatus(SerializableEnum):
    """Approval request states."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELED = "canceled"


class RiskLevel(SerializableEnum):
    """Risk levels used by workflow, supervisor, and tool gateway shells."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(slots=True)
class AgentStep:
    """A single planned or executed step inside an agent task."""

    title: str
    id: str = field(default_factory=lambda: new_id("step"))
    status: AgentStepStatus = AgentStepStatus.PENDING
    summary: str = ""
    tool_call_ids: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)


@dataclass(slots=True)
class AgentTask:
    """A bounded task assigned to a worker or service."""

    title: str
    worker: str
    id: str = field(default_factory=lambda: new_id("task"))
    status: AgentTaskStatus = AgentTaskStatus.PENDING
    steps: list[AgentStep] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)


@dataclass(slots=True)
class ToolCallLog:
    """A redacted, supervisor-visible tool call record."""

    tool_name: str
    request_preview: dict[str, Any]
    id: str = field(default_factory=lambda: new_id("tool"))
    status: ToolCallStatus = ToolCallStatus.DISABLED
    dry_run: bool = True
    execution_disabled: bool = True
    risk_level: RiskLevel = RiskLevel.MEDIUM
    approval_required: bool = False
    approval_id: str | None = None
    result_preview: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)


@dataclass(slots=True)
class ApprovalRequest:
    """A request for human approval before a risky action can run."""

    action: str
    reason: str
    risk_level: RiskLevel
    id: str = field(default_factory=lambda: new_id("approval"))
    status: ApprovalStatus = ApprovalStatus.PENDING
    requested_by: str = "supervisor"
    tool_call_id: str | None = None
    created_at: str = field(default_factory=utc_now)
    resolved_at: str | None = None
    resolution_note: str = ""


@dataclass(slots=True)
class Workflow:
    """Supervisor-facing workflow snapshot."""

    title: str
    id: str = field(default_factory=lambda: new_id("workflow"))
    status: WorkflowStatus = WorkflowStatus.PLANNED
    tasks: list[AgentTask] = field(default_factory=list)
    tool_calls: list[ToolCallLog] = field(default_factory=list)
    approvals: list[ApprovalRequest] = field(default_factory=list)
    logs: list[str] = field(default_factory=list)
    diff_placeholder: str = "No diff captured yet. Tool execution is disabled by default."
    test_placeholder: str = "No test run captured yet. Smoke hooks can attach results here."
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the workflow as API-safe primitive data."""

        return serialize(self)


def serialize(value: Any) -> Any:
    """Serialize dataclasses and enums into JSON-compatible primitives."""

    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {key: serialize(item) for key, item in asdict(value).items()}
    if isinstance(value, list):
        return [serialize(item) for item in value]
    if isinstance(value, dict):
        return {str(key): serialize(item) for key, item in value.items()}
    return value


def build_phase_9_workflow() -> Workflow:
    """Build the minimal Phase 9 supervisor shell workflow."""

    approval = ApprovalRequest(
        action="execute high-risk tool call",
        reason="High-risk tool execution requires explicit human approval.",
        risk_level=RiskLevel.HIGH,
    )
    tool_call = ToolCallLog(
        tool_name="tool-gateway.execute",
        request_preview={"mode": "dry_run", "target": "placeholder"},
        status=ToolCallStatus.WAITING_APPROVAL,
        risk_level=RiskLevel.HIGH,
        approval_required=True,
        approval_id=approval.id,
        result_preview={"message": "Execution blocked until approved."},
    )
    approval.tool_call_id = tool_call.id

    task = AgentTask(
        title="Phase 9 supervisor shell",
        worker="Worker 6",
        status=AgentTaskStatus.BLOCKED,
        steps=[
            AgentStep(
                title="Render workflow plan and task list",
                status=AgentStepStatus.COMPLETED,
                summary="Plan and task schemas are available.",
            ),
            AgentStep(
                title="Expose dry-run tool call log",
                status=AgentStepStatus.WAITING_APPROVAL,
                summary="High-risk execution is blocked and awaiting approval.",
                tool_call_ids=[tool_call.id],
            ),
            AgentStep(
                title="Attach diff and test placeholders",
                status=AgentStepStatus.DRY_RUN,
                summary="Placeholders are exposed for later adapter integration.",
            ),
        ],
    )

    return Workflow(
        title="Reality OS Phase 9 Agent Supervisor",
        status=WorkflowStatus.BLOCKED,
        tasks=[task],
        tool_calls=[tool_call],
        approvals=[approval],
        logs=[
            "Supervisor shell initialized.",
            "Tool execution defaults to disabled and dry-run.",
            "High-risk actions require approval before execution.",
        ],
    )
