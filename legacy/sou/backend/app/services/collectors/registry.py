from __future__ import annotations

from app.models import Source
from app.services.collectors.amazon import AmazonSPAPICollector
from app.services.collectors.arxiv import ArxivCollector
from app.services.collectors.custom import CustomUrlCollector, ManualSourceCollector
from app.services.collectors.github import GitHubCollector
from app.services.collectors.markets import CoinGeckoCollector, DefiLlamaCollector
from app.services.collectors.product import ProductHuntCollector
from app.services.collectors.rss import RSSCollector
from app.services.collectors.search import BraveSearchCollector, TavilyCollector, WebSearchCollector


def get_collector(db, source: Source):
    mapping = {
        "rss": RSSCollector,
        "web_search": WebSearchCollector,
        "news_search": BraveSearchCollector,
        "brave_search": BraveSearchCollector,
        "tavily": TavilyCollector,
        "official_blog": RSSCollector,
        "github": GitHubCollector,
        "arxiv": ArxivCollector,
        "coingecko": CoinGeckoCollector,
        "defillama": DefiLlamaCollector,
        "product_hunt": ProductHuntCollector,
        "amazon_sp_api": AmazonSPAPICollector,
        "custom_url": CustomUrlCollector,
        "manual": ManualSourceCollector,
        "manual_source": ManualSourceCollector,
    }
    collector_cls = mapping.get(source.type, CustomUrlCollector)
    return collector_cls(db)
