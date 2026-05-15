from __future__ import annotations

from app.models import Source
from app.services.collectors.base import RawDocumentCandidate
from app.services.collectors.http_client import SafeHttpClient


class CoinGeckoCollector:
    provider = "coingecko"

    def __init__(self, db) -> None:
        self.db = db

    async def fetch(self, source: Source) -> list[RawDocumentCandidate]:
        coins = (source.metadata_ or {}).get("coins") or ["bitcoin", "ethereum", "solana"]
        ids = ",".join(coins)
        url = (
            "https://api.coingecko.com/api/v3/coins/markets"
            f"?vs_currency=usd&ids={ids}&price_change_percentage=24h"
        )
        client = SafeHttpClient(self.db, self.provider, source.rate_limit_per_minute)
        data = await client.get_json(url)
        rows = data if isinstance(data, list) else []
        return [
            RawDocumentCandidate(
                url=f"https://www.coingecko.com/en/coins/{item.get('id')}",
                title=f"{item.get('name')} market snapshot",
                snippet=(
                    f"Price ${item.get('current_price')}; 24h change "
                    f"{item.get('price_change_percentage_24h')}%; market cap {item.get('market_cap')}"
                ),
                raw_content=str(item),
                content_type="market_data",
                metadata={"provider": self.provider, "asset": item.get("id"), "data": item},
            )
            for item in rows
            if item.get("id")
        ]


class DefiLlamaCollector:
    provider = "defillama"

    def __init__(self, db) -> None:
        self.db = db

    async def fetch(self, source: Source) -> list[RawDocumentCandidate]:
        protocol = (source.metadata_ or {}).get("protocol")
        url = "https://api.llama.fi/protocols" if not protocol else f"https://api.llama.fi/protocol/{protocol}"
        client = SafeHttpClient(self.db, self.provider, source.rate_limit_per_minute)
        data = await client.get_json(url)
        if isinstance(data, list):
            rows = data[:20]
        else:
            rows = [data]
        docs: list[RawDocumentCandidate] = []
        for item in rows:
            name = item.get("name") or item.get("slug")
            if not name:
                continue
            docs.append(
                RawDocumentCandidate(
                    url=item.get("url") or f"https://defillama.com/protocol/{item.get('slug', name)}",
                    title=f"{name} DeFi TVL snapshot",
                    snippet=f"TVL {item.get('tvl')}; category {item.get('category')}; chain {item.get('chain')}",
                    raw_content=str(item),
                    content_type="defi_data",
                    metadata={"provider": self.provider, "protocol": name, "data": item},
                )
            )
        return docs
