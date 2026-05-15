from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from app.schemas.agent import ToolStep, utc_now
from app.security.policies import redact_secrets
from app.utils.json import to_jsonable

T = TypeVar("T")


class StepLimitExceeded(RuntimeError):
    pass


class WorkflowRuntime:
    def __init__(self, max_steps: int) -> None:
        self.max_steps = max_steps
        self.tool_steps: list[ToolStep] = []

    def run_tool(self, name: str, args: dict[str, Any], fn: Callable[[], T]) -> T:
        if len(self.tool_steps) >= self.max_steps:
            raise StepLimitExceeded(f"max_steps={self.max_steps} 已触发，停止执行工具 {name}")
        started_at = utc_now()
        try:
            result = fn()
            step = ToolStep(
                name=name,
                status="success",
                args=redact_secrets(args),
                result=redact_secrets(to_jsonable(result)),
                started_at=started_at,
                ended_at=utc_now(),
            )
            self.tool_steps.append(step)
            return result
        except Exception as exc:
            step = ToolStep(
                name=name,
                status="error",
                args=redact_secrets(args),
                result=None,
                error=str(exc),
                started_at=started_at,
                ended_at=utc_now(),
            )
            self.tool_steps.append(step)
            raise

