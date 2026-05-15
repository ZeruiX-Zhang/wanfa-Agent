from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import IntelligenceMode, Timestamped


class ReportGenerateRequest(BaseModel):
    report_type: str = "daily"
    category: str | None = None
    mode: IntelligenceMode = "verified"
    limit: int = Field(default=10, ge=1, le=200)


class ReportItemRead(Timestamped):
    id: str
    report_id: str
    event_id: str | None
    rank: int
    title: str
    summary: str
    recommended_action: str


class ReportRead(Timestamped):
    id: str
    title: str
    report_type: str
    mode: str
    period_start: datetime | None
    period_end: datetime | None
    generation_seconds: float
    metadata_: dict


class ReportDetail(ReportRead):
    markdown: str
    json_content: dict
    html: str | None
    items: list[ReportItemRead]


class ReportExport(BaseModel):
    format: Literal["markdown", "json"]
    content: str | dict
