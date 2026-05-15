from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from app.models import Source


class ConnectorUnconfigured(RuntimeError):
    def __init__(self, provider: str, message: str = "connector_unconfigured") -> None:
        super().__init__(message)
        self.provider = provider
        self.message = message


@dataclass
class RawDocumentCandidate:
    url: str
    title: str | None = None
    snippet: str | None = None
    raw_content: str | None = None
    content_type: str | None = None
    published_at: datetime | None = None
    status: str = "fetched"
    error_reason: str | None = None
    metadata: dict = field(default_factory=dict)


class BaseCollector(Protocol):
    provider: str

    async def fetch(self, source: Source) -> list[RawDocumentCandidate]:
        ...


class AsyncRateLimiter:
    def __init__(self, per_minute: int) -> None:
        self.interval = 60.0 / max(per_minute, 1)
        self._lock = asyncio.Lock()
        self._last = 0.0

    async def wait(self) -> None:
        async with self._lock:
            elapsed = time.monotonic() - self._last
            if elapsed < self.interval:
                await asyncio.sleep(self.interval - elapsed)
            self._last = time.monotonic()
