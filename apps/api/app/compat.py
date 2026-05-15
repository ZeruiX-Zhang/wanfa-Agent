"""Frontend-compatibility router (`/api/*`).

This module exposes the API shape the `apps/web` Next.js frontend expects
(`/api/dashboard`, `/api/sources`, ...) while reusing the legacy-safe backend
endpoints defined in :mod:`apps.api.main`. No legacy project is mutated, no
external tool is executed, and all writes default to in-memory or
pending-review stores.

The router is deliberately a thin adapter layer: it maps between the web
contract in :file:`apps/web/lib/types.ts` and the in-memory mock-safe data
structures already maintained by the API module. Production persistence remains
a follow-up before deployment.
"""

from __future__ import annotations

import base64
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from .. import main as api_main
from ..schemas import (
    CaptureRequest,
    CaptureResponse,
    ClarificationQuestion,
    PendingKnowledgeCreateRequest,
    PendingKnowledgeRecord,
    new_id,
    utc_now,
)
from ..security import current_context, secret_status
from .intelligence import (
    Language as IntelligenceLanguage,
    describe_image,
    run_model_probes,
    summarize_supervisor,
)

router = APIRouter(prefix="/api", tags=["compat"])


# ---------------------------------------------------------------------------
# shared helpers
# ---------------------------------------------------------------------------


def _paginated(items: list[Any], limit: int, offset: int) -> dict[str, Any]:
    if limit < 0:
        limit = 0
    if offset < 0:
        offset = 0
    sliced = items[offset : offset + limit] if limit else []
    return {"items": sliced, "total": len(items), "limit": limit, "offset": offset}


def _utc_iso(dt: datetime | None = None) -> str:
    if dt is None:
        dt = datetime.now(timezone.utc)
    return dt.isoformat()


# ---------------------------------------------------------------------------
# in-memory domain stores (scoped per process)
# ---------------------------------------------------------------------------


class _SourceRecord(BaseModel):
    id: str
    name: str
    type: str
    category: str
    url: str | None = None
    enabled: bool = True
    trust_score: float = 0.6
    language: str = "en"
    country: str | None = None
    fetch_interval_minutes: int = 1440
    rate_limit_per_minute: int = 30
    legal_use_policy: str = "pending_review"
    robots_policy: str = "respect"
    license_name: str | None = None
    terms_url: str | None = None
    compliance_status: str = "unreviewed"
    collection_mode: str = "read_only"
    attribution_required: bool = True
    last_fetched_at: str | None = None
    last_status: str | None = None
    last_error: str | None = None
    metadata_: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=_utc_iso)
    updated_at: str = Field(default_factory=_utc_iso)

    model_config = ConfigDict(populate_by_name=True)


class _Watchlist(BaseModel):
    id: str
    type: str = "keyword"
    name: str
    value: str
    enabled: bool = True
    metadata_: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=_utc_iso)
    updated_at: str = Field(default_factory=_utc_iso)


class _Job(BaseModel):
    id: str
    name: str
    type: str = "smoke"
    mode: str = "speed"
    status: str = "succeeded"
    started_at: str | None = None
    finished_at: str | None = None
    success_count: int = 1
    failure_count: int = 0
    parameters: dict[str, Any] = Field(default_factory=dict)
    metadata_: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=_utc_iso)
    updated_at: str = Field(default_factory=_utc_iso)


_SEED_SOURCES: list[_SourceRecord] = [
    _SourceRecord(
        id="src_reality_os_adapter_notes",
        name="Reality OS adapter notes",
        type="custom_url",
        category="ai_news",
        url="about:blank",
        enabled=True,
        trust_score=0.72,
        language="en",
        country=None,
        fetch_interval_minutes=1440,
        rate_limit_per_minute=30,
        legal_use_policy="adapter_read_only",
        compliance_status="approved_limited",
        collection_mode="read_only",
        attribution_required=True,
        last_status="mock_safe",
        metadata_={"origin": "legacy:sou", "tags": ["reality-os", "adapter"]},
    ),
    _SourceRecord(
        id="src_search_knowledge",
        name="Search knowledge inventory",
        type="custom_url",
        category="ai_news",
        url=None,
        enabled=True,
        trust_score=0.64,
        language="en",
        legal_use_policy="adapter_read_only",
        compliance_status="unreviewed",
        collection_mode="read_only",
        last_status="mock_safe",
        metadata_={"origin": "legacy:sou", "tags": ["search", "knowledge"]},
    ),
]

_sources: dict[str, _SourceRecord] = {source.id: source.model_copy(deep=True) for source in _SEED_SOURCES}
_watchlists: dict[str, _Watchlist] = {}
_jobs: dict[str, _Job] = {}
_intelligence_synced_at: str | None = None


_NAME_PATTERN = re.compile(r"^[\w .,'()/_-]{1,120}$")


def _validate_name(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="name is required")
    if not _NAME_PATTERN.match(cleaned):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="name contains unsupported characters")
    return cleaned


# ---------------------------------------------------------------------------
# /api/dashboard
# ---------------------------------------------------------------------------


@router.get("/dashboard")
async def dashboard(request: Request) -> dict[str, Any]:
    context = current_context(request)
    storage = api_main.storage
    pending_total = len([*api_main.PENDING_KNOWLEDGE.values(), *storage.list_pending(context.tenant_id)])
    intelligence = api_main.INTELLIGENCE_OBJECTS
    verified = [item for item in intelligence if item.confidence >= 0.75]
    top_events = [
        {
            "id": item.id,
            "title": item.title,
            "category": item.object_type,
            "importance_score": item.confidence,
            "confidence": item.confidence,
            "verification_status": "pending_review" if item.confidence < 0.75 else "needs_human_review",
        }
        for item in intelligence
    ]
    today = datetime.now(timezone.utc).date()
    trend = [
        {"date": (today - timedelta(days=offset)).isoformat(), "events": max(0, len(intelligence) - offset)}
        for offset in range(6, -1, -1)
    ]
    return {
        "total_events_today": len(intelligence),
        "verified_events": len(verified),
        "high_impact_events": len(verified),
        "low_trust_events": max(0, len(intelligence) - len(verified)),
        "category_distribution": [
            {"category": "architecture_note", "count": sum(1 for item in intelligence if item.object_type == "architecture_note")},
            {"category": "policy_note", "count": sum(1 for item in intelligence if item.object_type == "policy_note")},
        ],
        "trend": trend,
        "top_events": top_events,
        "pending_knowledge_total": pending_total,
    }


# ---------------------------------------------------------------------------
# /api/sources  (+ policy + compliance)
# ---------------------------------------------------------------------------


class _SourceCreatePayload(BaseModel):
    name: str
    type: str
    category: str
    url: str | None = None
    enabled: bool = True
    trust_score: float = 0.6
    language: str = "en"
    country: str | None = None
    fetch_interval_minutes: int = 1440
    rate_limit_per_minute: int = 30
    metadata: dict[str, Any] | None = None


class _SourcePatchPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str | None = None
    type: str | None = None
    category: str | None = None
    url: str | None = None
    enabled: bool | None = None
    trust_score: float | None = None
    language: str | None = None
    country: str | None = None
    fetch_interval_minutes: int | None = None
    rate_limit_per_minute: int | None = None
    metadata: dict[str, Any] | None = None


@router.get("/sources")
async def list_sources(limit: int = 100, offset: int = 0) -> dict[str, Any]:
    items = [source.model_dump(by_alias=False) for source in _sources.values()]
    return _paginated(items, limit=limit, offset=offset)


@router.post("/sources", status_code=status.HTTP_201_CREATED)
async def create_source(payload: _SourceCreatePayload) -> dict[str, Any]:
    name = _validate_name(payload.name)
    record = _SourceRecord(
        id=new_id("src"),
        name=name,
        type=payload.type,
        category=payload.category,
        url=payload.url,
        enabled=payload.enabled,
        trust_score=max(0.0, min(1.0, payload.trust_score)),
        language=payload.language,
        country=payload.country,
        fetch_interval_minutes=max(1, payload.fetch_interval_minutes),
        rate_limit_per_minute=max(0, payload.rate_limit_per_minute),
        metadata_=payload.metadata or {},
        last_status="pending",
    )
    _sources[record.id] = record
    return record.model_dump()


@router.patch("/sources/{source_id}")
async def patch_source(source_id: str, payload: _SourcePatchPayload) -> dict[str, Any]:
    source = _sources.get(source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source not found")
    data = source.model_dump()
    updates = payload.model_dump(exclude_unset=True)
    if "metadata" in updates:
        updates["metadata_"] = updates.pop("metadata") or {}
    if "name" in updates:
        updates["name"] = _validate_name(str(updates["name"]))
    if "trust_score" in updates and updates["trust_score"] is not None:
        updates["trust_score"] = max(0.0, min(1.0, float(updates["trust_score"])))
    data.update(updates)
    data["updated_at"] = _utc_iso()
    _sources[source_id] = _SourceRecord.model_validate(data)
    return _sources[source_id].model_dump()


@router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(source_id: str) -> None:
    if source_id not in _sources:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source not found")
    del _sources[source_id]


def _empty_policy(source_id: str) -> dict[str, Any]:
    now = _utc_iso()
    return {
        "id": f"policy_{source_id}",
        "source_id": source_id,
        "access_type": "adapter_read_only",
        "allowed_uses": ["internal_review"],
        "disallowed_uses": ["formal_knowledge_write", "external_sharing"],
        "robots_txt_status": "respected",
        "license_name": None,
        "terms_url": None,
        "retention_days": 30,
        "pii_handling": "redact_in_logs",
        "requires_attribution": True,
        "compliance_status": "needs_review",
        "reviewed_by": None,
        "reviewed_at": None,
        "notes": "Default adapter policy. Replace with a reviewed source policy before ingesting.",
        "metadata_": {},
        "created_at": now,
        "updated_at": now,
    }


@router.get("/source-policies")
async def list_source_policies(limit: int = 100, offset: int = 0) -> dict[str, Any]:
    items = [_empty_policy(source_id) for source_id in _sources]
    return _paginated(items, limit=limit, offset=offset)


@router.get("/sources/{source_id}/policy")
async def get_source_policy(source_id: str) -> dict[str, Any]:
    if source_id not in _sources:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source not found")
    return _empty_policy(source_id)


@router.patch("/sources/{source_id}/policy")
async def patch_source_policy(source_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    if source_id not in _sources:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source not found")
    policy = _empty_policy(source_id)
    policy.update({key: value for key, value in payload.items() if key in policy})
    policy["updated_at"] = _utc_iso()
    return policy


class _ComplianceEvalPayload(BaseModel):
    mode: Literal["speed", "verified"] | None = "speed"
    decided_by: str | None = "adapter"


@router.post("/sources/{source_id}/compliance/evaluate")
async def evaluate_source_compliance(source_id: str, payload: _ComplianceEvalPayload) -> dict[str, Any]:
    if source_id not in _sources:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source not found")
    now = _utc_iso()
    return {
        "id": f"cd_{source_id}",
        "source_id": source_id,
        "source_policy_id": f"policy_{source_id}",
        "mode": payload.mode or "speed",
        "decision": "needs_review",
        "reason": "Automatic evaluation is mock-safe; promote via human review before writing.",
        "checks": {"robots": "respect", "license": "unknown", "pii": "redact"},
        "decided_by": payload.decided_by or "adapter",
        "metadata_": {},
        "created_at": now,
        "updated_at": now,
    }


@router.get("/compliance-decisions")
async def list_compliance_decisions(limit: int = 50, offset: int = 0) -> dict[str, Any]:
    return _paginated([], limit=limit, offset=offset)


# ---------------------------------------------------------------------------
# /api/events  (empty until an ingestion path exists)
# ---------------------------------------------------------------------------


@router.get("/events")
async def list_events(limit: int = 50, offset: int = 0) -> dict[str, Any]:
    return _paginated([], limit=limit, offset=offset)


@router.get("/events/{event_id}")
async def get_event(event_id: str) -> dict[str, Any]:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="event not found")


# ---------------------------------------------------------------------------
# /api/intelligence-objects  (+ sync)
# ---------------------------------------------------------------------------


def _intelligence_object_view(item: Any) -> dict[str, Any]:
    global _intelligence_synced_at
    now = _intelligence_synced_at or _utc_iso()
    return {
        "id": item.id,
        "object_type": item.object_type,
        "title": item.title,
        "summary": item.summary,
        "domain": "reality_os",
        "language": "en",
        "region": None,
        "canonical_url": None,
        "event_id": None,
        "cluster_id": None,
        "normalized_document_id": None,
        "entities": [],
        "source_document_ids": list(item.evidence_ids),
        "source_count": len(item.evidence_ids),
        "evidence_count": len(item.evidence_ids),
        "mode": "adapter",
        "status": "mock_safe",
        "verification_status": "needs_human_review",
        "index_credibility": round(item.confidence, 3),
        "index_novelty": 0.4,
        "index_impact": 0.5,
        "index_actionability": 0.5,
        "index_urgency": 0.3,
        "aggregate_score": round(item.confidence, 3),
        "compliance_status": "unreviewed",
        "metadata_": {},
        "created_at": now,
        "updated_at": now,
    }


@router.get("/intelligence-objects")
async def list_intelligence_objects(limit: int = 50, offset: int = 0) -> dict[str, Any]:
    items = [_intelligence_object_view(item) for item in api_main.INTELLIGENCE_OBJECTS]
    return _paginated(items, limit=limit, offset=offset)


@router.post("/intelligence-objects/sync")
async def sync_intelligence_objects(mode: Literal["speed", "verified"] = "speed") -> list[dict[str, Any]]:
    global _intelligence_synced_at
    _intelligence_synced_at = _utc_iso()
    return [_intelligence_object_view(item) for item in api_main.INTELLIGENCE_OBJECTS]


@router.get("/intelligence-objects/{object_id}")
async def get_intelligence_object(object_id: str) -> dict[str, Any]:
    for item in api_main.INTELLIGENCE_OBJECTS:
        if item.id == object_id:
            view = _intelligence_object_view(item)
            view["ledger_entries"] = [_evidence_ledger_view(ev) for ev in api_main.EVIDENCE if ev.id in set(item.evidence_ids)]
            return view
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="intelligence object not found")


# ---------------------------------------------------------------------------
# /api/evidence-ledger
# ---------------------------------------------------------------------------


def _evidence_ledger_view(item: Any) -> dict[str, Any]:
    now = _utc_iso()
    return {
        "id": item.id,
        "intelligence_object_id": None,
        "event_id": None,
        "normalized_document_id": None,
        "source_id": item.source_id,
        "evidence_url": "about:blank",
        "title": item.claim[:80],
        "source_name": item.source_id,
        "source_type": "adapter",
        "quote": item.quote,
        "captured_at": now,
        "content_hash": None,
        "ledger_hash": f"mock-{item.id}",
        "citation_status": "unverified",
        "legal_use_policy": "adapter_read_only",
        "compliance_status": "needs_review",
        "trust_score": 0.64,
        "relevance_score": 0.58,
        "supports_claims": [item.claim],
        "metadata_": {},
        "created_at": now,
        "updated_at": now,
    }


@router.get("/evidence-ledger")
async def list_evidence_ledger(limit: int = 100, offset: int = 0) -> dict[str, Any]:
    items = [_evidence_ledger_view(item) for item in api_main.EVIDENCE]
    return _paginated(items, limit=limit, offset=offset)


# ---------------------------------------------------------------------------
# /api/clusters, /api/cross-language-candidates  (empty pages)
# ---------------------------------------------------------------------------


@router.get("/clusters")
async def list_clusters(limit: int = 50, offset: int = 0) -> dict[str, Any]:
    return _paginated([], limit=limit, offset=offset)


@router.get("/cross-language-candidates")
async def list_cross_language_candidates(limit: int = 50, offset: int = 0) -> dict[str, Any]:
    return _paginated([], limit=limit, offset=offset)


# ---------------------------------------------------------------------------
# /api/reports
# ---------------------------------------------------------------------------


@router.get("/reports")
async def list_reports(limit: int = 20, offset: int = 0) -> dict[str, Any]:
    return _paginated([], limit=limit, offset=offset)


@router.get("/reports/{report_id}")
async def get_report(report_id: str) -> dict[str, Any]:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="report not found")


@router.post("/reports/generate")
async def generate_report(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    now = _utc_iso()
    report_id = new_id("report")
    return {
        "id": report_id,
        "title": "Mock-safe daily brief",
        "report_type": (payload or {}).get("report_type", "daily"),
        "mode": (payload or {}).get("mode", "speed"),
        "period_start": now,
        "period_end": now,
        "generation_seconds": 0.1,
        "metadata_": {"mock": True},
        "created_at": now,
        "updated_at": now,
        "markdown": "# Mock-safe report\n\nGenerated by the compat adapter for UI wiring only.",
        "json_content": {"summary": "Replace with a connected report engine."},
        "html": None,
        "items": [],
    }


# ---------------------------------------------------------------------------
# /api/watchlists
# ---------------------------------------------------------------------------


class _WatchlistCreatePayload(BaseModel):
    type: str = "keyword"
    name: str
    value: str
    enabled: bool = True
    metadata: dict[str, Any] | None = None


class _WatchlistPatchPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: str | None = None
    name: str | None = None
    value: str | None = None
    enabled: bool | None = None
    metadata: dict[str, Any] | None = None


@router.get("/watchlists")
async def list_watchlists(limit: int = 50, offset: int = 0) -> dict[str, Any]:
    items = [wl.model_dump() for wl in _watchlists.values()]
    return _paginated(items, limit=limit, offset=offset)


@router.post("/watchlists", status_code=status.HTTP_201_CREATED)
async def create_watchlist(payload: _WatchlistCreatePayload) -> dict[str, Any]:
    item = _Watchlist(
        id=new_id("watch"),
        type=payload.type,
        name=_validate_name(payload.name),
        value=payload.value,
        enabled=payload.enabled,
        metadata_=payload.metadata or {},
    )
    _watchlists[item.id] = item
    return item.model_dump()


@router.patch("/watchlists/{watch_id}")
async def patch_watchlist(watch_id: str, payload: _WatchlistPatchPayload) -> dict[str, Any]:
    item = _watchlists.get(watch_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="watchlist not found")
    data = item.model_dump()
    updates = payload.model_dump(exclude_unset=True)
    if "metadata" in updates:
        updates["metadata_"] = updates.pop("metadata") or {}
    if "name" in updates:
        updates["name"] = _validate_name(str(updates["name"]))
    data.update(updates)
    data["updated_at"] = _utc_iso()
    _watchlists[watch_id] = _Watchlist.model_validate(data)
    return _watchlists[watch_id].model_dump()


@router.delete("/watchlists/{watch_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_watchlist(watch_id: str) -> None:
    if watch_id not in _watchlists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="watchlist not found")
    del _watchlists[watch_id]


# ---------------------------------------------------------------------------
# /api/jobs
# ---------------------------------------------------------------------------


class _JobCreatePayload(BaseModel):
    name: str
    type: str = "custom"
    mode: str = "speed"
    parameters: dict[str, Any] | None = None


def _job_with_logs(item: _Job) -> dict[str, Any]:
    data = item.model_dump()
    data["logs"] = [
        {
            "id": new_id("log"),
            "job_id": item.id,
            "level": "info",
            "stage": "init",
            "message": "Job recorded in the compat adapter (no tools were executed).",
            "details": {},
            "created_at": item.created_at,
            "updated_at": item.updated_at,
        }
    ]
    return data


@router.get("/jobs")
async def list_jobs(limit: int = 20, offset: int = 0) -> dict[str, Any]:
    items = [job.model_dump() for job in sorted(_jobs.values(), key=lambda item: item.created_at, reverse=True)]
    return _paginated(items, limit=limit, offset=offset)


@router.get("/jobs/{job_id}")
async def get_job(job_id: str) -> dict[str, Any]:
    item = _jobs.get(job_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    return _job_with_logs(item)


@router.post("/jobs", status_code=status.HTTP_201_CREATED)
async def create_job(payload: _JobCreatePayload) -> dict[str, Any]:
    now = _utc_iso()
    item = _Job(
        id=new_id("job"),
        name=_validate_name(payload.name),
        type=payload.type,
        mode=payload.mode,
        status="succeeded",
        started_at=now,
        finished_at=now,
        parameters=payload.parameters or {},
    )
    _jobs[item.id] = item
    return _job_with_logs(item)


@router.post("/jobs/{job_id}/run")
async def run_job(job_id: str) -> dict[str, Any]:
    item = _jobs.get(job_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    item.started_at = _utc_iso()
    item.finished_at = _utc_iso()
    item.status = "succeeded"
    item.success_count += 1
    item.updated_at = _utc_iso()
    return _job_with_logs(item)


@router.post("/jobs/run-daily")
async def run_daily(mode: Literal["speed", "verified"] = "verified") -> dict[str, Any]:
    now = _utc_iso()
    item = _Job(
        id=new_id("job"),
        name=f"daily-{mode}",
        type="daily",
        mode=mode,
        status="succeeded",
        started_at=now,
        finished_at=now,
        parameters={"mode": mode},
        metadata_={"generated_by": "compat"},
    )
    _jobs[item.id] = item
    return _job_with_logs(item)


# ---------------------------------------------------------------------------
# /api/product-reviews
# ---------------------------------------------------------------------------


@router.get("/product-reviews")
async def list_product_reviews(limit: int = 20, offset: int = 0) -> dict[str, Any]:
    return _paginated([], limit=limit, offset=offset)


@router.get("/product-reviews/{review_id}")
async def get_product_review(review_id: str) -> dict[str, Any]:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="product review not found")


class _ProductReviewCreatePayload(BaseModel):
    product_name: str
    official_url: str | None = None
    competitors: list[str] = Field(default_factory=list)
    target_users: list[str] = Field(default_factory=list)


@router.post("/product-reviews", status_code=status.HTTP_201_CREATED)
async def create_product_review(payload: _ProductReviewCreatePayload) -> dict[str, Any]:
    now = _utc_iso()
    review_id = new_id("review")
    return {
        "id": review_id,
        "product_name": payload.product_name,
        "official_url": payload.official_url,
        "target_users": payload.target_users,
        "competitors": payload.competitors,
        "result": {"status": "pending_human_review"},
        "confidence": 0.0,
        "status": "pending_review",
        "metadata_": {"mock": True},
        "created_at": now,
        "updated_at": now,
        "evidence": [],
    }


# ---------------------------------------------------------------------------
# /api/settings
# ---------------------------------------------------------------------------


_SETTINGS_STATE = {
    "llm_provider": os.getenv("REALITY_OS_LLM_PROVIDER", "server-configured"),
    "llm_model": os.getenv("REALITY_OS_LLM_MODEL", "server-configured"),
    "search_provider": os.getenv("REALITY_OS_SEARCH_PROVIDER", "server-configured"),
    "report_time": os.getenv("REALITY_OS_REPORT_TIME", "08:00"),
    "retention_days": int(os.getenv("REALITY_OS_RETENTION_DAYS", "30")),
}


def _api_key_status() -> dict[str, bool]:
    return {key: value for key, value in secret_status()["configured"].items()}


@router.get("/settings")
async def get_settings(request: Request) -> dict[str, Any]:
    context = current_context(request)
    return {
        **_SETTINGS_STATE,
        "api_key_status": _api_key_status(),
        "auth_required": context.auth_required,
        "tenant_required_in_production": True,
    }


class _SettingsPatchPayload(BaseModel):
    llm_provider: str | None = None
    llm_model: str | None = None
    search_provider: str | None = None
    report_time: str | None = None
    retention_days: int | None = None


@router.patch("/settings")
async def patch_settings(payload: _SettingsPatchPayload, request: Request) -> dict[str, Any]:
    for key, value in payload.model_dump(exclude_unset=True).items():
        if value is None:
            continue
        if key == "retention_days":
            _SETTINGS_STATE[key] = max(1, int(value))
        else:
            _SETTINGS_STATE[key] = str(value)
    return await get_settings(request)


# ---------------------------------------------------------------------------
# /api/prompt/capture  and /api/prompt/capture-summary
# ---------------------------------------------------------------------------


@router.post("/prompt/capture", status_code=status.HTTP_202_ACCEPTED)
async def api_prompt_capture(payload: CaptureRequest | dict[str, Any]) -> CaptureResponse:
    if isinstance(payload, dict):
        payload = CaptureRequest.model_validate({
            "content": str(payload.get("text") or payload.get("content") or "").strip()
            or "(empty capture)",
            "source": str(payload.get("source", {}).get("kind") if isinstance(payload.get("source"), dict) else payload.get("source") or "extension"),
            "uri": payload.get("source", {}).get("url") if isinstance(payload.get("source"), dict) else payload.get("uri"),
            "tags": payload.get("tags", []) if isinstance(payload.get("tags"), list) else [],
            "created_by": str(payload.get("created_by", "extension")),
        })
    return await api_main.prompt_capture(payload)  # type: ignore[arg-type]


@router.get("/prompt/capture-summary")
async def api_prompt_capture_summary() -> dict[str, Any]:
    return {
        "mode": "mock-safe",
        "entryPoints": [
            {"id": "text", "label": "Text", "status": "ready", "detail": "Captured locally for clarification; no formal knowledge write."},
            {"id": "webpage", "label": "Webpage", "status": "untrusted", "detail": "External URLs are treated as untrusted until reviewed."},
            {"id": "extension", "label": "Browser extension", "status": "input_only", "detail": "Lightweight capture entry; complex business logic remains server-side."},
        ],
        "clarificationQuestions": [
            ClarificationQuestion(id="goal", question="What decision or judgment do you need to make?", reason="Decisions need a target.", required=True).model_dump(),
            ClarificationQuestion(id="scope", question="What sources, time range, or tenant boundary should retrieval use?", reason="Scope determines retrieval filters.", required=True).model_dump(),
            ClarificationQuestion(id="risk", question="What would make an answer unacceptable or unsafe?", reason="Risks shape verification.", required=False).model_dump(),
        ],
        "knowledgeOsSummary": {
            "status": "pending_review_only",
            "domains": ["personal", "industry", "enterprise", "study"],
            "pendingReviewRequired": True,
        },
    }


# ---------------------------------------------------------------------------
# /api/knowledge/pending  (delegates to existing main.py handlers)
# ---------------------------------------------------------------------------


@router.post("/knowledge/pending", status_code=status.HTTP_202_ACCEPTED)
async def api_create_pending_knowledge(payload: PendingKnowledgeCreateRequest, request: Request) -> PendingKnowledgeRecord:
    return await api_main.create_pending_knowledge(payload, request)


@router.get("/knowledge/pending")
async def api_list_pending_knowledge(request: Request) -> dict[str, Any]:
    response = await api_main.list_pending_knowledge(request)
    return response.model_dump()


@router.post("/knowledge/pending/{pending_id}/undo")
async def api_undo_pending_knowledge(pending_id: str, request: Request) -> dict[str, Any]:
    response = await api_main.undo_pending_knowledge(pending_id, request)
    return response.model_dump()


# ---------------------------------------------------------------------------
# /api/work/supervisor  (thin projection of the existing snapshot)
# ---------------------------------------------------------------------------


def _risk(text: str | None) -> str:
    value = (text or "").lower()
    if value in {"low", "medium", "high"}:
        return value
    if "high" in value or "destruct" in value:
        return "high"
    if "medium" in value:
        return "medium"
    return "low"


@router.get("/work/supervisor")
async def api_supervisor(request: Request) -> dict[str, Any]:
    snapshot = await api_main.supervisor_snapshot(request)
    workflow = snapshot.workflow
    tasks = workflow.tasks
    return {
        "mode": "mock-safe" if snapshot.metadata.mode == "mock-safe" else snapshot.metadata.mode,
        "workflow": {
            "id": workflow.id,
            "name": workflow.title,
            "status": workflow.status,
        },
        "agentTasks": [
            {
                "id": task.id,
                "title": task.title,
                "status": task.status,
                "risk": _risk(task.status),
                "dryRun": True,
            }
            for task in tasks
        ],
        "steps": [
            {
                "id": step.id,
                "taskId": task.id,
                "label": step.title,
                "status": step.status,
            }
            for task in tasks
            for step in task.steps
        ],
        "toolCalls": [
            {
                "id": tool.id,
                "tool": tool.tool_name,
                "status": tool.status,
                "dryRun": True,
                "reason": "Tool execution is disabled/dry-run by default.",
            }
            for tool in snapshot.tool_logs
        ],
        "approvalRequests": [
            {
                "id": approval.id,
                "action": approval.action,
                "risk": _risk(approval.risk),
                "status": approval.status,
                "required": approval.risk == "high",
            }
            for approval in snapshot.approvals
        ],
        "logs": [
            "Tool gateway default: disabled/dry-run.",
            "High-risk actions require approval before execution.",
            "Supervisor snapshot projected from /supervisor/snapshot.",
        ],
    }


__all__ = ["router"]



# ---------------------------------------------------------------------------
# /api/vision/describe  (language-aware caption + OCR + visual bullets)
# ---------------------------------------------------------------------------


def _coerce_language(value: Any) -> IntelligenceLanguage:
    raw = str(value or "").strip().lower()
    if raw in {"en", "en-us", "english"}:
        return "en"
    return "zh-CN"


class _VisionDescribeRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    language: str | None = None
    image_base64: str | None = Field(default=None, description="Base64 of the image bytes, optional.")
    image_hint: str | None = None
    user_notes: str | None = None


@router.post("/vision/describe")
async def vision_describe(payload: _VisionDescribeRequest) -> dict[str, Any]:
    language = _coerce_language(payload.language)
    image_bytes: bytes | None = None
    if payload.image_base64:
        try:
            image_bytes = base64.b64decode(payload.image_base64, validate=False)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="image_base64 must be valid base64",
            )
        if len(image_bytes) > 5 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="image payload exceeds the 5 MiB mock-safe limit",
            )
    description = describe_image(
        language=language,
        image_bytes=image_bytes,
        image_hint=payload.image_hint,
        user_notes=payload.user_notes,
    )
    return {
        "language": description.language,
        "source": description.source,
        "caption": description.caption,
        "ocr_text": description.ocr_text,
        "visual_description": list(description.visual_description),
        "warnings": list(description.warnings),
        "evidence_hash": description.evidence_hash,
    }


# ---------------------------------------------------------------------------
# /api/supervisor/summarize  (first-principles digest over the snapshot)
# ---------------------------------------------------------------------------


class _SupervisorSummarizeRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    language: str | None = None
    snapshot: dict[str, Any] | None = None


@router.post("/supervisor/summarize")
async def supervisor_summarize(payload: _SupervisorSummarizeRequest, request: Request) -> dict[str, Any]:
    language = _coerce_language(payload.language)
    snapshot = payload.snapshot
    if not snapshot:
        snapshot = await api_supervisor(request)  # type: ignore[func-returns-value]
    digest = summarize_supervisor(snapshot or {}, language)
    return {
        "language": digest.language,
        "goal": digest.goal,
        "single_next_action": digest.single_next_action,
        "blocked_on": list(digest.blocked_on),
        "drift_alert": digest.drift_alert,
        "risk_counts": dict(digest.risk_counts),
        "approvals_waiting": digest.approvals_waiting,
        "generated_from": list(digest.generated_from),
        "raw_snapshot": snapshot,
    }


# ---------------------------------------------------------------------------
# /api/models/test  (intelligence probe → workflow strategy)
# ---------------------------------------------------------------------------


class _ModelTestRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    language: str | None = None
    provider: str | None = None
    model: str | None = None


@router.post("/models/test")
async def api_models_test(payload: _ModelTestRequest) -> dict[str, Any]:
    language = _coerce_language(payload.language)
    provider = (payload.provider or _SETTINGS_STATE.get("search_provider") or "server-configured").strip() or "server-configured"
    model = (payload.model or _SETTINGS_STATE.get("llm_model") or "server-configured").strip() or "server-configured"
    report = run_model_probes(provider=provider, model=model, language=language, runner=None)
    return {
        "language": report.language,
        "provider": report.provider,
        "model": report.model,
        "source": report.source,
        "tier": report.tier,
        "aggregate_score": report.aggregate_score,
        "probes": [
            {
                "id": probe.id,
                "label": probe.label,
                "expected": probe.expected,
                "actual": probe.actual,
                "passed": probe.passed,
                "score": probe.score,
                "detail": probe.detail,
            }
            for probe in report.probes
        ],
        "workflow_strategy": report.workflow_strategy,
        "recommendation": report.recommendation,
        "notes": list(report.notes),
    }
