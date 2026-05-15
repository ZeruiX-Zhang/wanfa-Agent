from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from platform_common.models import AuthContext


ToolGuard = Callable[[str, dict[str, Any]], None]

_AUTH_CONTEXT: ContextVar[AuthContext] = ContextVar("workflow_auth_context", default=AuthContext())
_RUN_MODE: ContextVar[str] = ContextVar("workflow_run_mode", default="auto")
_TOOL_GUARD: ContextVar[ToolGuard | None] = ContextVar("workflow_tool_guard", default=None)


@contextmanager
def workflow_session(
    auth_context: AuthContext | None = None,
    run_mode: str = "auto",
    tool_guard: ToolGuard | None = None,
) -> Iterator[None]:
    auth_token = _AUTH_CONTEXT.set(auth_context or AuthContext())
    mode_token = _RUN_MODE.set(run_mode)
    guard_token = _TOOL_GUARD.set(tool_guard)
    try:
        yield
    finally:
        _AUTH_CONTEXT.reset(auth_token)
        _RUN_MODE.reset(mode_token)
        _TOOL_GUARD.reset(guard_token)


def get_auth_context() -> AuthContext:
    return _AUTH_CONTEXT.get()


def get_run_mode() -> str:
    return _RUN_MODE.get()


def get_tool_guard() -> ToolGuard | None:
    return _TOOL_GUARD.get()
