from __future__ import annotations

import feedparser
from dateutil import parser

from app.core.security import sanitize_html
from app.models import Source
from app.services.collectors.base import RawDocumentCandidate
from app.services.collectors.http_client import SafeHttpClient


class RSSCollector:
    provider = "rss"

    def __init__(self, db) -> None:
        self.db = db

    async def fetch(self, source: Source) -> list[RawDocumentCandidate]:
        if not source.url:
            return []
        client = SafeHttpClient(self.db, self.provider, source.rate_limit_per_minute)
        feed_text = await client.get_text(source.url)
        parsed = feedparser.parse(feed_text)
        documents: list[RawDocumentCandidate] = []
        for entry in parsed.entries:
            url = entry.get("link") or source.url
            published_at = None
            raw_date = entry.get("published") or entry.get("updated")
            if raw_date:
                try:
                    published_at = parser.parse(raw_date)
                except (ValueError, TypeError, OverflowError):
                    published_at = None
            content = entry.get("summary") or entry.get("description") or ""
            documents.append(
                RawDocumentCandidate(
                    url=url,
                    title=entry.get("title"),
                    snippet=sanitize_html(content)[:500],
                    raw_content=sanitize_html(content),
                    content_type="rss_entry",
                    published_at=published_at,
                    metadata={"feed_url": source.url, "entry_id": entry.get("id")},
                )
            )
        return documents
