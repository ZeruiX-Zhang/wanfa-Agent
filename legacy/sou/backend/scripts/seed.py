from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models import (
    Event,
    EventClaim,
    EventCluster,
    EventEvidence,
    Job,
    JobLog,
    NormalizedDocument,
    RawDocument,
    Source,
    Watchlist,
)
from app.schemas.product_review import ProductReviewRequest
from app.services.compliance import ensure_source_policy, evaluate_source_compliance
from app.services.intelligence import domain_from_category, sync_objects_from_events
from app.services.product_reviews import build_product_review
from app.services.report_generator import generate_report
from app.services.scoring import apply_event_indices


def seed() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        existing = db.query(Source).filter(Source.metadata_["demo"].as_boolean().is_(True)).first()
        if existing:
            print("Demo seed already exists; skipping.")
            return
        now = datetime.now(UTC)
        source_specs = [
            ("Demo AI RSS", "rss", "ai_news", "https://example.com/demo/ai-rss", 0.7),
            ("Demo Official Blog", "official_blog", "ai_news", "https://example.com/demo/blog", 0.88),
            ("Demo arXiv", "arxiv", "arxiv_research", "https://export.arxiv.org", 0.82),
            ("Demo GitHub", "github", "github_trending", "https://api.github.com", 0.8),
            ("Demo CoinGecko", "coingecko", "crypto_news", "https://api.coingecko.com", 0.78),
            ("Demo DefiLlama", "defillama", "crypto_news", "https://api.llama.fi", 0.78),
            ("Demo Ecommerce", "manual", "ecommerce_market", "manual://ecommerce", 0.55),
            ("Demo Product Hunt", "product_hunt", "ai_product_review", "https://api.producthunt.com", 0.65),
            ("Demo Brave Search", "brave_search", "tech_news", "https://api.search.brave.com", 0.62),
            ("Demo Amazon Mock", "amazon_sp_api", "ecommerce_market", None, 0.6),
        ]
        sources: list[Source] = []
        for name, type_, category, url, trust in source_specs:
            source = Source(
                name=name,
                type=type_,
                category=category,
                url=url,
                enabled=True,
                trust_score=trust,
                language="en",
                country="US",
                fetch_interval_minutes=1440,
                rate_limit_per_minute=30,
                legal_use_policy="metadata_and_snippets",
                robots_policy="unknown",
                compliance_status="approved_limited",
                collection_mode="metadata_only",
                attribution_required=True,
                last_fetched_at=now - timedelta(hours=1),
                last_status="demo_seeded",
                metadata_={"demo": True},
            )
            db.add(source)
            sources.append(source)
        db.commit()
        for source in sources:
            db.refresh(source)
            ensure_source_policy(db, source)
            evaluate_source_compliance(db, source, mode="verified", decided_by="demo_seed")

        watchlists = [
            ("company", "OpenAI", "OpenAI"),
            ("product", "ChatGPT", "ChatGPT"),
            ("token", "BTC", "bitcoin"),
            ("ecommerce_category", "AI gadgets", "AI gadgets"),
            ("keyword", "RAG", "RAG benchmark"),
        ]
        for type_, name, value in watchlists:
            db.add(Watchlist(type=type_, name=name, value=value, enabled=True, metadata_={"demo": True}))
        db.commit()

        raws: list[RawDocument] = []
        categories = [
            ("ai_model", "AI model infrastructure signal"),
            ("ai_product", "AI product pricing signal"),
            ("open_source", "Open source repository trend"),
            ("paper_research", "Research paper trend"),
            ("crypto_market", "Crypto market data signal"),
            ("defi", "DeFi TVL signal"),
            ("ecommerce_market", "Ecommerce demand signal"),
        ]
        for i in range(30):
            source = sources[i % len(sources)]
            category, label = categories[i % len(categories)]
            raw = RawDocument(
                source_id=source.id,
                url=f"https://example.com/demo/intel/{i}",
                title=f"[DEMO] {label} #{i + 1}",
                snippet="Demo-only intelligence item. This is synthetic sample data, not a real-world claim.",
                raw_content=(
                    "Demo-only intelligence item for product validation. "
                    "It contains neutral placeholder text so dashboards, reports, evidence, and scoring can be tested "
                    "without creating or implying a real news conclusion. "
                    f"Category marker: {category}."
                ),
                content_type="demo",
                published_at=now - timedelta(hours=i),
                fetched_at=now - timedelta(minutes=i * 10),
                status="demo_seeded",
                metadata_={"demo": True, "category_marker": category},
            )
            db.add(raw)
            raws.append(raw)
        db.commit()
        for raw in raws:
            db.refresh(raw)

        normalized_docs: list[NormalizedDocument] = []
        for i, raw in enumerate(raws[:20]):
            doc = NormalizedDocument(
                raw_document_id=raw.id,
                canonical_url=raw.url,
                title=raw.title or f"[DEMO] Item {i}",
                clean_text=raw.raw_content or "",
                summary="Demo-only summary for validating the intelligence workflow.",
                language="en",
                published_at=raw.published_at or now,
                fetched_at=raw.fetched_at,
                source_id=raw.source_id,
                author="Demo seed",
                entities=["DemoCo", "SampleProduct"],
                domain=domain_from_category(raw.source.category if raw.source else "other"),
                legal_use_policy=raw.source.legal_use_policy if raw.source else "metadata_and_snippets",
                compliance_status=raw.source.compliance_status if raw.source else "approved_limited",
                content_hash=f"demo-hash-{i}",
                simhash=f"{i:016x}",
                status="normalized",
                quality_flags=[],
                published_at_inferred=False,
                metadata_={"demo": True, "evidence_url": raw.url},
            )
            db.add(doc)
            normalized_docs.append(doc)
        db.commit()
        for doc in normalized_docs:
            db.refresh(doc)

        clusters: list[EventCluster] = []
        for i in range(5):
            cluster = EventCluster(
                title=f"[DEMO] Intelligence cluster {i + 1}",
                category=categories[i % len(categories)][0],
                language="en",
                cross_language_key=f"demo-intelligence-cluster-{i + 1}",
                merged_summary="Demo-only merged summary. Not a real conclusion.",
                source_diversity_score=0.5,
                confidence_score=0.62,
                importance_score=0.6,
                verification_status="partially_verified",
                metadata_={"demo": True},
            )
            db.add(cluster)
            clusters.append(cluster)
        db.commit()
        for cluster in clusters:
            db.refresh(cluster)

        events: list[Event] = []
        for i in range(15):
            doc = normalized_docs[i % len(normalized_docs)]
            category = categories[i % len(categories)][0]
            cluster = clusters[i % len(clusters)]
            confidence = 0.5 + (i % 5) * 0.08
            impact = 0.45 + (i % 6) * 0.07
            novelty = 0.4 + (i % 4) * 0.08
            action = 0.35 + (i % 5) * 0.08
            event = Event(
                title=f"[DEMO] {categories[i % len(categories)][1]} event {i + 1}",
                category=category,
                event_time=now - timedelta(hours=i),
                entities=["DemoCo", "SampleProduct"],
                summary="Demo-only event summary for validating UI and report generation.",
                why_it_matters="Demo-only rationale; this is not a real recommendation or factual market conclusion.",
                affected_parties=["Demo operators"],
                confidence=confidence,
                novelty_score=novelty,
                impact_score=impact,
                actionability_score=action,
                importance_score=0.0,
                verification_status="verified" if i % 3 == 0 else "partially_verified" if i % 3 == 1 else "unverified",
                extraction_status="demo_seeded",
                cluster_id=cluster.id,
                metadata_={
                    "demo": True,
                    "source_document_ids": [doc.id],
                    "source_languages": [doc.language],
                    "primary_language": doc.language,
                },
            )
            apply_event_indices(event, source_count=1, evidence_count=1)
            db.add(event)
            db.flush()
            db.add(
                EventClaim(
                    event_id=event.id,
                    text="Demo-only claim used to validate schema and evidence display.",
                    evidence_quote="Demo-only intelligence item for product validation.",
                    evidence_url=doc.canonical_url,
                    confidence=0.55,
                    needs_verification=True,
                )
            )
            db.add(
                EventEvidence(
                    event_id=event.id,
                    normalized_document_id=doc.id,
                    evidence_url=doc.canonical_url,
                    title=doc.title,
                    source_name=doc.source.name,
                    quote=doc.clean_text[:300],
                )
            )
            events.append(event)
        db.commit()
        sync_objects_from_events(db, mode="verified")

        for report_type in ["daily", "crypto_daily", "weekly"]:
            generate_report(db, report_type, limit=10, mode="verified")

        build_product_review(
            db,
            ProductReviewRequest(
                product_name="DemoAI",
                official_url="https://example.com/demo/demoai",
                competitors=["SampleGPT", "ExampleBot"],
                target_users=["product teams", "research teams"],
            ),
        )
        build_product_review(
            db,
            ProductReviewRequest(
                product_name="ExampleAgent",
                competitors=["DemoAI"],
                target_users=["operators"],
            ),
        )

        for i in range(5):
            job = Job(
                name=f"Demo job {i + 1}",
                type="daily" if i % 2 == 0 else "collector",
                mode="verified" if i % 2 == 0 else "speed",
                status="completed" if i < 4 else "failed",
                started_at=now - timedelta(hours=i + 1),
                finished_at=now - timedelta(hours=i + 1, minutes=-4),
                success_count=10 + i,
                failure_count=0 if i < 4 else 1,
                parameters={"demo": True},
                metadata_={"demo": True, "run_id": f"demo-run-{i + 1}"},
            )
            db.add(job)
            db.flush()
            db.add(
                JobLog(
                    job_id=job.id,
                    level="info" if i < 4 else "error",
                    stage="demo",
                    message="Demo job log entry for observability validation.",
                    details={"demo": True},
                )
            )
        db.commit()
        print("Seeded demo data.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
