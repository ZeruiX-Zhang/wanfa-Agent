from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from workflow_core.runtime_context import get_tool_guard
from workflow_core.schemas.agent import ToolStep, utc_now
from workflow_core.security.policies import redact_secrets
from workflow_core.utils.json import to_jsonable

T = TypeVar("T")


class StepLimitExceeded(RuntimeError):
    pass


class WorkflowRuntime:
    def __init__(self, max_steps: int) -> None:
        self.max_steps = max_steps
        self.tool_steps: list[ToolStep] = []

    def run_tool(self, name: str, args: dict[str, Any], fn: Callable[[], T]) -> T:
        if len(self.tool_steps) >= self.max_steps:
            raise StepLimitExceeded(f"max_steps={self.max_steps} 宸茶Е鍙戯紝鍋滄鎵ц宸ュ叿 {name}")
        started_at = utc_now()
        try:
            tool_guard = get_tool_guard()
            if tool_guard is not None:
                tool_guard(name, args)
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
