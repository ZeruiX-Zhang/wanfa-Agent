"""In-memory supervisor shell for plans, steps, tools, approvals, and logs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from services.workflow import (
    AgentStep,
    AgentStepStatus,
    AgentTask,
    AgentTaskStatus,
    ApprovalRequest,
    ApprovalStatus,
    RiskLevel,
    ToolCallLog,
    ToolCallStatus,
    Workflow,
    WorkflowStatus,
    build_supervisor_workflow,
    utc_now,
)


@dataclass(slots=True)
class SupervisorShell:
    """Rollback-friendly in-memory supervisor read model.

    The shell does not execute tools. It exposes the state that API and web
    adapters need while keeping side effects disabled.
    """

    workflow: Workflow = field(default_factory=build_supervisor_workflow)

    def snapshot(self) -> dict[str, Any]:
        """Return the full supervisor state as API-safe primitives."""

        return self.workflow.to_dict()

    def plan(self) -> dict[str, Any]:
        """Return plan, task, and step details for the supervisor view."""

        return {
            "workflow_id": self.workflow.id,
            "title": self.workflow.title,
            "status": self.workflow.status.value,
            "tasks": [
                {
                    "id": task.id,
                    "title": task.title,
                    "worker": task.worker,
                    "status": task.status.value,
                    "steps": [
                        {
                            "id": step.id,
                            "title": step.title,
                            "status": step.status.value,
                            "summary": step.summary,
                            "tool_call_ids": list(step.tool_call_ids),
                        }
                        for step in task.steps
                    ],
                }
                for task in self.workflow.tasks
            ],
        }

    def tool_calls(self) -> list[dict[str, Any]]:
        """Return redacted tool calls."""

        return [tool_call.to_dict() if hasattr(tool_call, "to_dict") else self._tool_call_dict(tool_call) for tool_call in self.workflow.tool_calls]

    def approvals(self) -> list[dict[str, Any]]:
        """Return approval requests."""

        return [self._approval_dict(approval) for approval in self.workflow.approvals]

    def logs(self) -> list[str]:
        """Return supervisor log lines."""

        return list(self.workflow.logs)

    def placeholders(self) -> dict[str, str]:
        """Return diff and test placeholders."""

        return {
            "diff": self.workflow.diff_placeholder,
            "tests": self.workflow.test_placeholder,
        }

    def record_tool_call(
        self,
        tool_name: str,
        request_preview: dict[str, Any],
        risk_level: RiskLevel = RiskLevel.MEDIUM,
        approval_required: bool = False,
    ) -> ToolCallLog:
        """Record a dry-run tool call without executing it."""

        approval_id: str | None = None
        status = ToolCallStatus.DRY_RUN

        if approval_required or risk_level in {RiskLevel.HIGH, RiskLevel.CRITICAL}:
            approval = ApprovalRequest(
                action=f"approve tool call: {tool_name}",
                reason="Risk policy requires human approval before execution.",
                risk_level=risk_level,
            )
            self.workflow.approvals.append(approval)
            approval_id = approval.id
            status = ToolCallStatus.WAITING_APPROVAL

        tool_call = ToolCallLog(
            tool_name=tool_name,
            request_preview=request_preview,
            status=status,
            risk_level=risk_level,
            approval_required=approval_id is not None,
            approval_id=approval_id,
            result_preview={"message": "Recorded only; execution is disabled."},
        )
        if approval_id:
            self.workflow.approvals[-1].tool_call_id = tool_call.id

        self.workflow.tool_calls.append(tool_call)
        self.workflow.logs.append(f"{utc_now()} recorded dry-run tool call {tool_call.id}.")
        self.workflow.updated_at = utc_now()
        return tool_call

    def add_task(self, title: str, worker: str, steps: list[str]) -> AgentTask:
        """Add a bounded task and planned steps."""

        task = AgentTask(
            title=title,
            worker=worker,
            status=AgentTaskStatus.PENDING,
            steps=[AgentStep(title=step, status=AgentStepStatus.PENDING) for step in steps],
        )
        self.workflow.tasks.append(task)
        self.workflow.updated_at = utc_now()
        return task

    def resolve_approval(
        self,
        approval_id: str,
        approved: bool,
        note: str,
    ) -> ApprovalRequest:
        """Resolve an approval request without executing the related tool."""

        for approval in self.workflow.approvals:
            if approval.id == approval_id:
                approval.status = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
                approval.resolved_at = utc_now()
                approval.resolution_note = note
                self.workflow.logs.append(f"{utc_now()} resolved approval {approval.id}.")
                self.workflow.updated_at = utc_now()
                return approval
        raise ValueError(f"Unknown approval id: {approval_id}")

    @staticmethod
    def _tool_call_dict(tool_call: ToolCallLog) -> dict[str, Any]:
        """Serialize a tool call without relying on framework encoders."""

        return {
            "id": tool_call.id,
            "tool_name": tool_call.tool_name,
            "request_preview": tool_call.request_preview,
            "status": tool_call.status.value,
            "dry_run": tool_call.dry_run,
            "execution_disabled": tool_call.execution_disabled,
            "risk_level": tool_call.risk_level.value,
            "approval_required": tool_call.approval_required,
            "approval_id": tool_call.approval_id,
            "result_preview": tool_call.result_preview,
            "created_at": tool_call.created_at,
        }

    @staticmethod
    def _approval_dict(approval: ApprovalRequest) -> dict[str, Any]:
        """Serialize an approval request."""

        return {
            "id": approval.id,
            "action": approval.action,
            "reason": approval.reason,
            "risk_level": approval.risk_level.value,
            "status": approval.status.value,
            "requested_by": approval.requested_by,
            "tool_call_id": approval.tool_call_id,
            "created_at": approval.created_at,
            "resolved_at": approval.resolved_at,
            "resolution_note": approval.resolution_note,
        }


def build_default_supervisor_snapshot() -> dict[str, Any]:
    """Return a default supervisor snapshot."""

    return SupervisorShell().snapshot()
