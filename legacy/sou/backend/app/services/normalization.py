from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from difflib import SequenceMatcher
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import sanitize_html
from app.models import NormalizedDocument, RawDocument
from app.services.intelligence import domain_from_category

TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "fbclid", "gclid"}


def canonicalize_url(url: str) -> str:
    if url.startswith("manual://"):
        return url
    parsed = urlparse(url)
    query = urlencode([(k, v) for k, v in parse_qsl(parsed.query) if k not in TRACKING_PARAMS])
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/") or "/"
    return urlunparse((parsed.scheme.lower(), netloc, path, "", query, ""))


def detect_language(text: str) -> str:
    zh_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    return "zh" if zh_chars >= max(5, len(text) * 0.05) else "en"


def extract_entities(text: str) -> list[str]:
    candidates = set(re.findall(r"\b[A-Z][A-Za-z0-9&.-]{1,30}\b|\$[A-Z]{2,8}", text))
    zh_candidates = set(re.findall(r"[\u4e00-\u9fff]{2,8}", text[:1000]))
    return sorted(candidates | zh_candidates)[:30]


def summarize(text: str, max_chars: int = 420) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    return compact[:max_chars]


def content_hash(text: str) -> str:
    compact = re.sub(r"\s+", " ", text).strip().lower()
    return hashlib.sha256(compact.encode("utf-8")).hexdigest()


def simhash(text: str) -> str:
    tokens = re.findall(r"\w+", text.lower())[:1000]
    vector = [0] * 64
    for token in tokens:
        digest = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
        for i in range(64):
            vector[i] += 1 if digest & (1 << i) else -1
    value = 0
    for i, weight in enumerate(vector):
        if weight > 0:
            value |= 1 << i
    return f"{value:016x}"


def normalize_raw_document(db: Session, raw: RawDocument) -> NormalizedDocument:
    text = raw.raw_content or raw.snippet or raw.title or ""
    text = sanitize_html(text)
    title = (raw.title or raw.snippet or raw.url)[:500]
    fetched_at = raw.fetched_at or datetime.now(UTC)
    published_at_inferred = raw.published_at is None
    published_at = raw.published_at or fetched_at
    clean = re.sub(r"\s+", " ", text).strip()
    flags: list[str] = []
    if len(clean) < 120:
        flags.append("low_content_quality")
    canonical = canonicalize_url(raw.url)
    digest = content_hash(clean or title)
    duplicate = (
        db.query(NormalizedDocument)
        .filter(
            (NormalizedDocument.canonical_url == canonical) | (NormalizedDocument.content_hash == digest)
        )
        .first()
    )
    if duplicate:
        flags.append("duplicate_candidate")
    else:
        similar_titles = db.query(NormalizedDocument).limit(200).all()
        for existing in similar_titles:
            if SequenceMatcher(None, existing.title.lower(), title.lower()).ratio() > 0.92:
                flags.append("title_similarity_duplicate")
                break
    doc = NormalizedDocument(
        raw_document_id=raw.id,
        canonical_url=canonical,
        title=title,
        clean_text=clean,
        summary=summarize(clean or title),
        language=detect_language(clean or title),
        published_at=published_at,
        fetched_at=fetched_at,
        source_id=raw.source_id,
        author=(raw.metadata_ or {}).get("author"),
        entities=extract_entities(f"{title} {clean}"),
        domain=domain_from_category(raw.source.category if raw.source else "other"),
        legal_use_policy=raw.source.legal_use_policy if raw.source else "metadata_and_snippets",
        compliance_status=raw.source.compliance_status if raw.source else "unreviewed",
        content_hash=digest,
        simhash=simhash(clean or title),
        status="normalized" if not flags else "normalized_with_flags",
        quality_flags=flags,
        published_at_inferred=published_at_inferred,
        metadata_={"evidence_url": raw.url, "raw_status": raw.status, "raw_error": raw.error_reason},
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def normalize_pending(db: Session, limit: int = 200) -> list[NormalizedDocument]:
    normalized_ids = select(NormalizedDocument.raw_document_id)
    raws = (
        db.query(RawDocument)
        .filter(~RawDocument.id.in_(normalized_ids))
        .order_by(RawDocument.fetched_at.desc())
        .limit(limit)
        .all()
    )
    docs: list[NormalizedDocument] = []
    for raw in raws:
        docs.append(normalize_raw_document(db, raw))
    return docs
