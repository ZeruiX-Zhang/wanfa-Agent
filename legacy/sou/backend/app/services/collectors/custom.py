from __future__ import annotations

import trafilatura

from app.core.security import sanitize_html
from app.models import Source
from app.services.collectors.base import RawDocumentCandidate
from app.services.collectors.http_client import SafeHttpClient


class CustomUrlCollector:
    provider = "custom_url"

    def __init__(self, db) -> None:
        self.db = db

    async def fetch(self, source: Source) -> list[RawDocumentCandidate]:
        if not source.url:
            return []
        client = SafeHttpClient(self.db, self.provider, source.rate_limit_per_minute)
        html = await client.get_text(source.url)
        extracted = trafilatura.extract(html) or sanitize_html(html)
        return [
            RawDocumentCandidate(
                url=source.url,
                title=source.name,
                snippet=extracted[:500] if extracted else None,
                raw_content=extracted,
                content_type="web_page",
                metadata={"provider": self.provider},
            )
        ]


class ManualSourceCollector:
    provider = "manual_source"

    async def fetch(self, source: Source) -> list[RawDocumentCandidate]:
        content = (source.metadata_ or {}).get("content")
        if not content:
            return []
        return [
            RawDocumentCandidate(
                url=source.url or f"manual://{source.id}",
                title=source.name,
                snippet=content[:500],
                raw_content=content,
                content_type="manual",
                metadata={"provider": self.provider},
            )
        ]
