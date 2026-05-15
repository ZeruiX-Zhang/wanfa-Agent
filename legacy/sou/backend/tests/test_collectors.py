from __future__ import annotations

import pytest

from app.models import Source
from app.services.collectors.http_client import SafeHttpClient
from app.services.collectors.rss import RSSCollector


@pytest.mark.asyncio
async def test_rss_collector_mock(db_session, monkeypatch):
    async def fake_get_text(self, url, headers=None):
        return """
        <rss><channel>
          <item>
            <title>Demo item</title>
            <link>https://example.com/item</link>
            <description>Demo description</description>
            <pubDate>Fri, 08 May 2026 00:00:00 GMT</pubDate>
          </item>
        </channel></rss>
        """

    monkeypatch.setattr(SafeHttpClient, "get_text", fake_get_text)
    source = Source(
        name="RSS",
        type="rss",
        category="ai_news",
        url="https://example.com/feed.xml",
        trust_score=0.7,
        language="en",
        rate_limit_per_minute=60,
        fetch_interval_minutes=60,
        metadata_={},
    )
    docs = await RSSCollector(db_session).fetch(source)
    assert len(docs) == 1
    assert docs[0].title == "Demo item"
    assert docs[0].url == "https://example.com/item"
