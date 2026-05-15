from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import ProductReview, ProductReviewEvidence
from app.schemas.product_review import ProductReviewRequest


def build_product_review(db: Session, request: ProductReviewRequest) -> ProductReview:
    evidence_specs = []
    if request.official_url:
        evidence_specs.append(("official", request.official_url, request.product_name, "Official product URL"))
    queries = [
        f"{request.product_name} pricing",
        f"{request.product_name} changelog",
        f"{request.product_name} Product Hunt",
        f"{request.product_name} Hacker News",
        f"{request.product_name} Reddit",
    ]
    for competitor in request.competitors:
        queries.append(f"{request.product_name} vs {competitor}")
    for query in queries:
        evidence_specs.append(
            (
                "search_query",
                "https://www.google.com/search?q=" + query.replace(" ", "+"),
                query,
                "Search query abstraction; configure Brave/Tavily for live collection.",
            )
        )
    comparison = [
        {
            "capability": "Positioning",
            request.product_name: "Requires verified source collection",
            **{competitor: "Requires verified source collection" for competitor in request.competitors},
        },
        {
            "capability": "Pricing",
            request.product_name: "Monitor official pricing page",
            **{competitor: "Monitor official pricing page" for competitor in request.competitors},
        },
    ]
    result = {
        "product_name": request.product_name,
        "positioning": "Pending verified extraction from official docs, changelog and trusted reviews.",
        "core_features": [],
        "pricing": [],
        "strengths": [],
        "weaknesses": ["Insufficient verified evidence until connectors collect primary sources."],
        "target_users": request.target_users,
        "competitors": request.competitors,
        "comparison_table": comparison,
        "evidence": [{"type": spec[0], "url": spec[1], "title": spec[2]} for spec in evidence_specs],
        "recommendation": "monitor",
        "confidence": 0.35 if not request.official_url else 0.45,
    }
    review = ProductReview(
        product_name=request.product_name,
        official_url=request.official_url,
        target_users=request.target_users,
        competitors=request.competitors,
        result=result,
        confidence=result["confidence"],
        status="completed",
        metadata_={"adapter": "evidence_first_review"},
    )
    db.add(review)
    db.flush()
    for source_type, url, title, snippet in evidence_specs:
        db.add(
            ProductReviewEvidence(
                review_id=review.id,
                source_type=source_type,
                url=url,
                title=title,
                snippet=snippet,
                confidence=0.4 if source_type == "search_query" else 0.6,
            )
        )
    db.commit()
    db.refresh(review)
    return review
