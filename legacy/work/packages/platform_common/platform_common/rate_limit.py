from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import HTTPException, status

from platform_common.settings import get_settings


_requests: dict[str, deque[float]] = defaultdict(deque)


def check_rate_limit(key: str) -> None:
    settings = get_settings()
    if not settings.rate_limit_enabled:
        return
    now = time.monotonic()
    window_start = now - 60
    bucket = _requests[key]
    while bucket and bucket[0] < window_start:
        bucket.popleft()
    if len(bucket) >= settings.requests_per_minute:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error_code": "rate_limited",
                "message": "Too many requests in the current one-minute window.",
                "detail": {"requests_per_minute": settings.requests_per_minute},
                "suggestion": "Retry after the current rate limit window resets.",
            },
        )
    bucket.append(now)
