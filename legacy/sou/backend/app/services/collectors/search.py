from __future__ import annotations

from urllib.parse import quote

from app.core.config import get_settings
from app.models import Source
from app.services.collectors.base import ConnectorUnconfigured, RawDocumentCandidate
from app.services.collectors.http_client import SafeHttpClient


class WebSearchCollector:
    provider = "web_search"

    def __init__(self, db) -> None:
        self.db = db

    async def fetch(self, source: Source) -> list[RawDocumentCandidate]:
        raise ConnectorUnconfigured(self.provider, "Configure Brave or Tavily for web search")


class BraveSearchCollector:
    provider = "brave"

    def __init__(self, db) -> None:
        self.db = db
        self.settings = get_settings()

    async def fetch(self, source: Source) -> list[RawDocumentCandidate]:
        if not self.settings.brave_search_api_key:
            raise ConnectorUnconfigured(self.provider)
        query = (source.metadata_ or {}).get("query") or source.name
        url = f"https://api.search.brave.com/res/v1/web/search?q={quote(query)}&count=10"
        client = SafeHttpClient(self.db, self.provider, source.rate_limit_per_minute)
        data = await client.get_json(
            url, headers={"X-Subscription-Token": self.settings.brave_search_api_key}
        )
        results = data.get("web", {}).get("results", []) if isinstance(data, dict) else []
        return [
            RawDocumentCandidate(
                url=item.get("url"),
                title=item.get("title"),
                snippet=item.get("description"),
                raw_content=item.get("description"),
                content_type="search_result",
                metadata={"query": query, "provider": self.provider},
            )
            for item in results
            if item.get("url")
        ]


class TavilyCollector:
    provider = "tavily"

    def __init__(self, db) -> None:
        self.db = db
        self.settings = get_settings()

    async def fetch(self, source: Source) -> list[RawDocumentCandidate]:
        if not self.settings.tavily_api_key:
            raise ConnectorUnconfigured(self.provider)
        query = (source.metadata_ or {}).get("query") or source.name
        client = SafeHttpClient(self.db, self.provider, source.rate_limit_per_minute)
        data = await client.post_json(
            "https://api.tavily.com/search",
            {"api_key": self.settings.tavily_api_key, "query": query, "max_results": 10},
        )
        results = data.get("results", []) if isinstance(data, dict) else []
        return [
            RawDocumentCandidate(
                url=item.get("url"),
                title=item.get("title"),
                snippet=item.get("content"),
                raw_content=item.get("content"),
                content_type="search_result",
                metadata={"query": query, "provider": self.provider},
            )
            for item in results
            if item.get("url")
        ]
