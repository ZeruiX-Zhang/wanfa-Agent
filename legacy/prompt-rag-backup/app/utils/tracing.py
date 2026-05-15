from __future__ import annotations

from contextvars import ContextVar, Token

_trace_id: ContextVar[str | None] = ContextVar("trace_id", default=None)


def get_trace_id() -> str | None:
    return _trace_id.get()


def set_trace_id(trace_id: str | None, token: Token[str | None] | None = None) -> Token[str | None] | None:
    if token is not None:
        _trace_id.reset(token)
        return None
    return _trace_id.set(trace_id)
