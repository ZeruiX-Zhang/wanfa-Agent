from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import Timestamped


class ProductReviewRequest(BaseModel):
    product_name: str = Field(min_length=1, max_length=200)
    official_url: str | None = None
    competitors: list[str] = Field(default_factory=list)
    target_users: list[str] = Field(default_factory=list)


class ProductReviewEvidenceRead(Timestamped):
    id: str
    review_id: str
    source_type: str
    url: str
    title: str | None
    snippet: str | None
    confidence: float


class ProductReviewRead(Timestamped):
    id: str
    product_name: str
    official_url: str | None
    target_users: list[str]
    competitors: list[str]
    result: dict
    confidence: float
    status: str
    metadata_: dict


class ProductReviewDetail(ProductReviewRead):
    evidence: list[ProductReviewEvidenceRead]
