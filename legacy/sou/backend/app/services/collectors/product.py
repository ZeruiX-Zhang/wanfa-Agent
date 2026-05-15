from __future__ import annotations

from app.core.config import get_settings
from app.models import Source
from app.services.collectors.base import ConnectorUnconfigured, RawDocumentCandidate
from app.services.collectors.http_client import SafeHttpClient


class ProductHuntCollector:
    provider = "product_hunt"

    def __init__(self, db) -> None:
        self.db = db
        self.settings = get_settings()

    async def fetch(self, source: Source) -> list[RawDocumentCandidate]:
        if not self.settings.product_hunt_token:
            raise ConnectorUnconfigured(self.provider)
        query = """
        query {
          posts(first: 10, order: NEWEST) {
            edges { node { name tagline url website createdAt votesCount } }
          }
        }
        """
        client = SafeHttpClient(self.db, self.provider, source.rate_limit_per_minute)
        data = await client.post_json(
            "https://api.producthunt.com/v2/api/graphql",
            {"query": query},
            headers={"Authorization": f"Bearer {self.settings.product_hunt_token}"},
        )
        edges = data.get("data", {}).get("posts", {}).get("edges", []) if isinstance(data, dict) else []
        return [
            RawDocumentCandidate(
                url=edge["node"].get("website") or edge["node"].get("url"),
                title=edge["node"].get("name"),
                snippet=edge["node"].get("tagline"),
                raw_content=edge["node"].get("tagline"),
                content_type="product_hunt_post",
                metadata={"provider": self.provider, "votes": edge["node"].get("votesCount")},
            )
            for edge in edges
            if edge.get("node", {}).get("url")
        ]
