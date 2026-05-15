from __future__ import annotations

from pydantic import BaseModel, Field


class DashboardMetric(BaseModel):
    label: str
    value: int | float


class DashboardOverview(BaseModel):
    total_events_today: int
    total_intelligence_objects: int = 0
    verified_events: int
    high_impact_events: int
    low_trust_events: int
    mode_distribution: list[dict] = Field(default_factory=list)
    five_index_averages: dict[str, float] = Field(default_factory=dict)
    category_distribution: list[dict]
    trend: list[dict]
    top_events: list[dict]
