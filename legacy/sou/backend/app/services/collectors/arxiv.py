from __future__ import annotations

from urllib.parse import quote

import feedparser
from dateutil import parser

from app.core.security import sanitize_html
from app.models import Source
from app.services.collectors.base import RawDocumentCandidate
from app.services.collectors.http_client import SafeHttpClient


class ArxivCollector:
    provider = "arxiv"

    def __init__(self, db) -> None:
        self.db = db

    async def fetch(self, source: Source) -> list[RawDocumentCandidate]:
        query = (source.metadata_ or {}).get("query") or source.name or "artificial intelligence"
        url = (
            "https://export.arxiv.org/api/query?"
            f"search_query=all:{quote(query)}&start=0&max_results=10&sortBy=submittedDate&sortOrder=descending"
        )
        client = SafeHttpClient(self.db, self.provider, source.rate_limit_per_minute)
        feed_text = await client.get_text(url)
        parsed = feedparser.parse(feed_text)
        docs: list[RawDocumentCandidate] = []
        for entry in parsed.entries:
            published_at = None
            if entry.get("published"):
                try:
                    published_at = parser.parse(entry.get("published"))
                except (ValueError, TypeError, OverflowError):
                    published_at = None
            docs.append(
                RawDocumentCandidate(
                    url=entry.get("link"),
                    title=entry.get("title"),
                    snippet=sanitize_html(entry.get("summary", ""))[:500],
                    raw_content=sanitize_html(entry.get("summary", "")),
                    content_type="arxiv_paper",
                    published_at=published_at,
                    metadata={
                        "query": query,
                        "authors": [author.get("name") for author in entry.get("authors", [])],
                        "provider": self.provider,
                    },
                )
            )
        return [doc for doc in docs if doc.url]
