from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

DomainName = Literal[
    "enterprise_kb",
    "customer_support",
    "finance_research",
    "ops_runbook",
    "legal_contract",
    "data_analysis",
]

SUPPORTED_DOMAINS: tuple[str, ...] = (
    "enterprise_kb",
    "customer_support",
    "finance_research",
    "ops_runbook",
    "legal_contract",
    "data_analysis",
)

DomainRequestValue = Literal[
    "auto",
    "enterprise_kb",
    "customer_support",
    "finance_research",
    "ops_runbook",
    "legal_contract",
    "data_analysis",
]


class DomainRouteResult(BaseModel):
    domain: DomainName
    intent: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = Field(min_length=1)
