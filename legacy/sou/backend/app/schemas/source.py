from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl

from app.schemas.common import Timestamped


class SourceBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    type: str = Field(min_length=1, max_length=50)
    category: str = Field(min_length=1, max_length=80)
    url: str | None = None
    enabled: bool = True
    trust_score: float = Field(default=0.6, ge=0.0, le=1.0)
    language: str = "en"
    country: str | None = None
    fetch_interval_minutes: int = Field(default=1440, ge=1)
    rate_limit_per_minute: int = Field(default=30, ge=1, le=600)
    legal_use_policy: str = Field(default="metadata_and_snippets", max_length=80)
    robots_policy: str = Field(default="unknown", max_length=80)
    license_name: str | None = Field(default=None, max_length=160)
    terms_url: str | None = None
    compliance_status: str = Field(default="unreviewed", max_length=80)
    collection_mode: str = Field(default="metadata_only", max_length=80)
    attribution_required: bool = True
    metadata: dict = Field(default_factory=dict)


class SourceCreate(SourceBase):
    pass


class SourceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    type: str | None = Field(default=None, min_length=1, max_length=50)
    category: str | None = Field(default=None, min_length=1, max_length=80)
    url: str | None = None
    enabled: bool | None = None
    trust_score: float | None = Field(default=None, ge=0.0, le=1.0)
    language: str | None = None
    country: str | None = None
    fetch_interval_minutes: int | None = Field(default=None, ge=1)
    rate_limit_per_minute: int | None = Field(default=None, ge=1, le=600)
    legal_use_policy: str | None = Field(default=None, max_length=80)
    robots_policy: str | None = Field(default=None, max_length=80)
    license_name: str | None = Field(default=None, max_length=160)
    terms_url: str | None = None
    compliance_status: str | None = Field(default=None, max_length=80)
    collection_mode: str | None = Field(default=None, max_length=80)
    attribution_required: bool | None = None
    metadata: dict | None = None


class SourceRead(Timestamped):
    id: str
    name: str
    type: str
    category: str
    url: str | None
    enabled: bool
    trust_score: float
    language: str
    country: str | None
    fetch_interval_minutes: int
    rate_limit_per_minute: int
    legal_use_policy: str
    robots_policy: str
    license_name: str | None
    terms_url: str | None
    compliance_status: str
    collection_mode: str
    attribution_required: bool
    last_fetched_at: datetime | None
    last_status: str | None
    last_error: str | None
    metadata_: dict


class SourceStatus(BaseModel):
    configured: bool
    message: str
    docs_url: HttpUrl | None = None
