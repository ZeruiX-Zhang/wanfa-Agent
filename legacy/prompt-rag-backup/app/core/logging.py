from __future__ import annotations

import logging

from app.utils.tracing import get_trace_id


class TraceIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = get_trace_id() or "-"
        return True


def configure_logging(level: str = "INFO") -> None:
    trace_filter = TraceIdFilter()
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s trace_id=%(trace_id)s %(name)s - %(message)s",
    )
    root = logging.getLogger()
    if not any(isinstance(item, TraceIdFilter) for item in root.filters):
        root.addFilter(trace_filter)
    for handler in root.handlers:
        if not any(isinstance(item, TraceIdFilter) for item in handler.filters):
            handler.addFilter(trace_filter)
