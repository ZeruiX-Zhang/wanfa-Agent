from __future__ import annotations

from pydantic import BaseModel, Field


class SettingsRead(BaseModel):
    llm_provider: str
    llm_model: str
    search_provider: str
    report_time: str
    retention_days: int
    api_key_status: dict[str, bool]


class SettingsUpdate(BaseModel):
    llm_provider: str | None = None
    llm_model: str | None = None
    search_provider: str | None = None
    report_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    retention_days: int | None = Field(default=None, ge=1, le=3650)
