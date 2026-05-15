from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import Timestamped


class WatchlistCreate(BaseModel):
    type: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    value: str = Field(min_length=1, max_length=300)
    enabled: bool = True
    metadata: dict = Field(default_factory=dict)


class WatchlistUpdate(BaseModel):
    type: str | None = Field(default=None, min_length=1, max_length=80)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    value: str | None = Field(default=None, min_length=1, max_length=300)
    enabled: bool | None = None
    metadata: dict | None = None


class WatchlistRead(Timestamped):
    id: str
    type: str
    name: str
    value: str
    enabled: bool
    metadata_: dict
