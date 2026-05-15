from __future__ import annotations

from datetime import UTC, datetime

from app.models import RawDocument, Source
from app.services.normalization import canonicalize_url, detect_language, normalize_raw_document


def test_normalization_pipeline(db_session):
    source = Source(
        name="Manual",
        type="manual",
        category="ai_news",
        url="manual://x",
        trust_score=0.6,
        language="en",
        rate_limit_per_minute=10,
        fetch_interval_minutes=60,
        metadata_={},
    )
    db_session.add(source)
    db_session.commit()
    raw = RawDocument(
        source_id=source.id,
        url="https://example.com/a?utm_source=x&id=1#section",
        title="OpenAI Demo Update",
        raw_content="OpenAI released a demo update. " * 20,
        fetched_at=datetime.now(UTC),
        status="fetched",
        metadata_={},
    )
    db_session.add(raw)
    db_session.commit()
    doc = normalize_raw_document(db_session, raw)
    assert doc.canonical_url == "https://example.com/a?id=1"
    assert doc.content_hash
    assert doc.simhash
    assert doc.language == "en"
    assert "OpenAI" in doc.entities


def test_language_detection():
    assert detect_language("这是一个中文测试内容，用于判断语言检测。") == "zh"
    assert canonicalize_url("https://EXAMPLE.com/path/?utm_campaign=x&a=1") == "https://example.com/path?a=1"
