from __future__ import annotations

import time

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.security import validate_external_url
from app.models import ApiUsageLog
from app.services.collectors.base import AsyncRateLimiter


class SafeHttpClient:
    def __init__(self, db, provider: str, rate_limit_per_minute: int = 30) -> None:
        self.settings = get_settings()
        self.db = db
        self.provider = provider
        self.rate_limiter = AsyncRateLimiter(rate_limit_per_minute)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.3, min=0.3, max=3))
    async def get_text(self, url: str, headers: dict[str, str] | None = None) -> str:
        validate_external_url(url)
        await self.rate_limiter.wait()
        started = time.perf_counter()
        status = "error"
        async with httpx.AsyncClient(timeout=self.settings.http_timeout_seconds, follow_redirects=True) as client:
            try:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                content = response.content[: self.settings.external_max_bytes]
                status = str(response.status_code)
                return content.decode(response.encoding or "utf-8", errors="replace")
            finally:
                latency_ms = int((time.perf_counter() - started) * 1000)
                self.db.add(
                    ApiUsageLog(
                        provider=self.provider,
                        operation="GET",
                        status=status,
                        latency_ms=latency_ms,
                        cost_estimate=0.0,
                        metadata_={"url": url},
                    )
                )
                self.db.commit()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.3, min=0.3, max=3))
    async def get_json(self, url: str, headers: dict[str, str] | None = None) -> dict | list:
        text = await self.get_text(url, headers=headers)
        return httpx.Response(200, text=text).json()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.3, min=0.3, max=3))
    async def post_json(
        self, url: str, payload: dict, headers: dict[str, str] | None = None
    ) -> dict | list:
        validate_external_url(url)
        await self.rate_limiter.wait()
        started = time.perf_counter()
        status = "error"
        async with httpx.AsyncClient(timeout=self.settings.http_timeout_seconds) as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                status = str(response.status_code)
                return response.json()
            finally:
                latency_ms = int((time.perf_counter() - started) * 1000)
                self.db.add(
                    ApiUsageLog(
                        provider=self.provider,
                        operation="POST",
                        status=status,
                        latency_ms=latency_ms,
                        cost_estimate=0.0,
                        metadata_={"url": url},
                    )
                )
                self.db.commit()
