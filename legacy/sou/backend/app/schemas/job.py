from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import IntelligenceMode, Timestamped


class JobCreateRequest(BaseModel):
    name: str = Field(default="Intelligence run", min_length=1, max_length=200)
    type: str = Field(default="daily", max_length=80)
    mode: IntelligenceMode = "speed"
    run_now: bool = True
    parameters: dict = Field(default_factory=dict)


class JobLogRead(Timestamped):
    id: str
    job_id: str
    level: str
    stage: str
    message: str
    details: dict


class JobRead(Timestamped):
    id: str
    name: str
    type: str
    mode: str
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    success_count: int
    failure_count: int
    parameters: dict
    metadata_: dict


class JobDetail(JobRead):
    logs: list[JobLogRead]
