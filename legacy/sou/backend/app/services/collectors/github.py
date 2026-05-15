from __future__ import annotations

from datetime import UTC, datetime, timedelta
from urllib.parse import quote

from app.core.config import get_settings
from app.models import Source
from app.services.collectors.base import RawDocumentCandidate
from app.services.collectors.http_client import SafeHttpClient


class GitHubCollector:
    provider = "github"

    def __init__(self, db) -> None:
        self.db = db
        self.settings = get_settings()

    async def fetch(self, source: Source) -> list[RawDocumentCandidate]:
        query = (source.metadata_ or {}).get("query")
        if not query:
            since = (datetime.now(UTC) - timedelta(days=7)).date().isoformat()
            query = f"stars:>50 pushed:>{since}"
        url = f"https://api.github.com/search/repositories?q={quote(query)}&sort=stars&order=desc&per_page=10"
        headers = {"Accept": "application/vnd.github+json"}
        if self.settings.github_token:
            headers["Authorization"] = f"Bearer {self.settings.github_token}"
        client = SafeHttpClient(self.db, self.provider, source.rate_limit_per_minute)
        data = await client.get_json(url, headers=headers)
        items = data.get("items", []) if isinstance(data, dict) else []
        return [
            RawDocumentCandidate(
                url=item.get("html_url"),
                title=item.get("full_name"),
                snippet=item.get("description"),
                raw_content=item.get("description") or "",
                content_type="github_repository",
                metadata={
                    "stars": item.get("stargazers_count"),
                    "forks": item.get("forks_count"),
                    "language": item.get("language"),
                    "provider": self.provider,
                },
            )
            for item in items
            if item.get("html_url")
        ]
