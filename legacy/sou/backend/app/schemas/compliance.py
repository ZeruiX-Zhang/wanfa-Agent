from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import IntelligenceMode, Timestamped


class SourcePolicyBase(BaseModel):
    access_type: str = Field(default="public_web", max_length=80)
    allowed_uses: list[str] = Field(default_factory=lambda: ["metadata", "snippet", "link"])
    disallowed_uses: list[str] = Field(default_factory=list)
    robots_txt_status: str = Field(default="unknown", max_length=80)
    license_name: str | None = Field(default=None, max_length=160)
    terms_url: str | None = None
    retention_days: int = Field(default=365, ge=1, le=3650)
    pii_handling: str = Field(default="minimize_and_redact", max_length=120)
    requires_attribution: bool = True
    compliance_status: str = Field(default="unreviewed", max_length=80)
    reviewed_by: str | None = Field(default=None, max_length=120)
    reviewed_at: datetime | None = None
    notes: str | None = None
    metadata: dict = Field(default_factory=dict)


class SourcePolicyUpdate(BaseModel):
    access_type: str | None = Field(default=None, max_length=80)
    allowed_uses: list[str] | None = None
    disallowed_uses: list[str] | None = None
    robots_txt_status: str | None = Field(default=None, max_length=80)
    license_name: str | None = Field(default=None, max_length=160)
    terms_url: str | None = None
    retention_days: int | None = Field(default=None, ge=1, le=3650)
    pii_handling: str | None = Field(default=None, max_length=120)
    requires_attribution: bool | None = None
    compliance_status: str | None = Field(default=None, max_length=80)
    reviewed_by: str | None = Field(default=None, max_length=120)
    reviewed_at: datetime | None = None
    notes: str | None = None
    metadata: dict | None = None


class SourcePolicyRead(Timestamped):
    id: str
    source_id: str
    access_type: str
    allowed_uses: list[str]
    disallowed_uses: list[str]
    robots_txt_status: str
    license_name: str | None
    terms_url: str | None
    retention_days: int
    pii_handling: str
    requires_attribution: bool
    compliance_status: str
    reviewed_by: str | None
    reviewed_at: datetime | None
    notes: str | None
    metadata_: dict


class ComplianceEvaluateRequest(BaseModel):
    mode: IntelligenceMode = "speed"
    decided_by: str = Field(default="system", max_length=120)


class ComplianceDecisionRead(Timestamped):
    id: str
    source_id: str
    source_policy_id: str | None
    mode: str
    decision: str
    reason: str
    checks: dict
    decided_by: str
    metadata_: dict
