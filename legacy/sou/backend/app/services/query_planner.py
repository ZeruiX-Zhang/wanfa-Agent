from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import Watchlist

DEFAULT_QUERY_TEMPLATES: dict[str, list[str]] = {
    "ai_news": [
        "{company} latest AI model release",
        "{company} API pricing update",
        "{product} changelog AI",
        "AI agent framework release",
        "RAG benchmark new paper",
        "multimodal model release",
    ],
    "crypto_news": [
        "crypto regulation latest",
        "{token} hack exploit vulnerability",
        "{protocol} TVL change",
        "{exchange} listing delisting",
        "stablecoin inflow outflow",
    ],
    "tech_news": ["semiconductor AI latest", "cloud infrastructure update", "robotics breakthrough"],
    "ai_product_review": [
        "{product} review",
        "{product} vs {competitor}",
        "{product} pricing",
        "{product} alternative",
        "{product} Product Hunt",
        "{product} Hacker News",
        "{product} Reddit",
    ],
    "ecommerce_market": [
        "{category} ecommerce trend",
        "{category} Amazon best sellers",
        "{keyword} Google Trends",
        "{brand} traffic change",
        "{product} price drop",
        "{category} TikTok Shop trend",
    ],
    "github_trending": ["AI agent stars:>100 pushed:>2026-01-01", "RAG framework stars:>100"],
    "arxiv_research": ["retrieval augmented generation", "multimodal model", "agent benchmark"],
    "company_watchlist": ["{company} AI release", "{company} earnings AI"],
    "competitor_watchlist": ["{product} competitor pricing", "{product} alternative"],
}


@dataclass
class QueryBatch:
    run_id: str
    queries: list[dict]


class QueryPlanner:
    def __init__(self, db: Session) -> None:
        self.db = db

    def generate_daily_batch(self) -> QueryBatch:
        run_id = str(uuid.uuid4())
        watchlists = self.db.query(Watchlist).filter(Watchlist.enabled.is_(True)).all()
        context = {
            "company": [w.value for w in watchlists if w.type == "company"] or ["OpenAI", "Anthropic"],
            "product": [w.value for w in watchlists if w.type == "product"] or ["ChatGPT", "Claude"],
            "token": [w.value for w in watchlists if w.type == "token"] or ["bitcoin", "ethereum"],
            "category": [w.value for w in watchlists if w.type == "ecommerce_category"] or ["AI gadgets"],
            "keyword": [w.value for w in watchlists if w.type == "keyword"] or ["AI tools"],
            "brand": [w.value for w in watchlists if w.type == "brand"] or ["demo brand"],
            "protocol": [w.value for w in watchlists if w.type == "protocol"] or ["uniswap"],
            "exchange": [w.value for w in watchlists if w.type == "exchange"] or ["coinbase"],
            "competitor": [w.value for w in watchlists if w.type == "competitor"] or ["Perplexity"],
        }
        queries: list[dict] = []
        for category, templates in DEFAULT_QUERY_TEMPLATES.items():
            for template in templates:
                expanded = self._expand_template(template, context)
                for query in expanded:
                    queries.append({"run_id": run_id, "category": category, "query": query})
        return QueryBatch(run_id=run_id, queries=queries)

    def _expand_template(self, template: str, context: dict[str, list[str]]) -> list[str]:
        keys = [key for key in context if "{" + key + "}" in template]
        if not keys:
            return [template]
        queries = [template]
        for key in keys:
            next_queries = []
            for query in queries:
                for value in context[key][:5]:
                    next_queries.append(query.replace("{" + key + "}", value))
            queries = next_queries
        return queries[:20]
