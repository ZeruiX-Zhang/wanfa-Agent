from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.all_models import ComplianceDecision, Source, SourcePolicy

DEFAULT_ALLOWED_USES = ["metadata", "snippet", "link"]
BLOCKING_STATUSES = {"blocked", "disallowed", "takedown_required"}
LIMITED_STATUSES = {"unreviewed", "approved_limited", "needs_review"}


def ensure_source_policy(db: Session, source: Source) -> SourcePolicy:
    policy = db.query(SourcePolicy).filter(SourcePolicy.source_id == source.id).first()
    if policy:
        return policy
    policy = SourcePolicy(
        source_id=source.id,
        access_type="api" if source.type in {"github", "arxiv", "coingecko", "defillama"} else "public_web",
        allowed_uses=DEFAULT_ALLOWED_USES.copy(),
        disallowed_uses=[],
        robots_txt_status=source.robots_policy,
        license_name=source.license_name,
        terms_url=source.terms_url,
        retention_days=365,
        pii_handling="minimize_and_redact",
        requires_attribution=source.attribution_required,
        compliance_status=source.compliance_status,
        metadata_={"source_type": source.type, "collection_mode": source.collection_mode},
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return policy


def _decision_for(source: Source, policy: SourcePolicy, mode: str) -> tuple[str, str, dict]:
    checks = {
        "source_enabled": source.enabled,
        "source_compliance_status": source.compliance_status,
        "policy_compliance_status": policy.compliance_status,
        "collection_mode": source.collection_mode,
        "legal_use_policy": source.legal_use_policy,
        "robots_txt_status": policy.robots_txt_status,
        "allowed_uses": policy.allowed_uses,
        "disallowed_uses": policy.disallowed_uses,
        "mode": mode,
    }
    if not source.enabled:
        return "block", "Source is disabled.", checks
    if source.compliance_status in BLOCKING_STATUSES or policy.compliance_status in BLOCKING_STATUSES:
        return "block", "Source policy is blocked by compliance status.", checks
    if source.collection_mode == "none" or "collection" in (policy.disallowed_uses or []):
        return "block", "Collection is disallowed for this source.", checks
    if mode == "verified" and source.compliance_status in LIMITED_STATUSES and policy.compliance_status in LIMITED_STATUSES:
        return "allow_limited", "Verified mode may use metadata, snippets, links, and cited evidence only.", checks
    if policy.robots_txt_status in {"disallow", "blocked"}:
        return "allow_limited", "Robots policy limits automated collection; use metadata or official APIs only.", checks
    if source.compliance_status == "approved" or policy.compliance_status == "approved":
        return "allow", "Source has an approved legal source policy.", checks
    return "allow_limited", "No blocking rule found; defaulting to limited evidence-first collection.", checks


def evaluate_source_compliance(
    db: Session,
    source: Source,
    mode: str = "speed",
    decided_by: str = "system",
) -> ComplianceDecision:
    policy = ensure_source_policy(db, source)
    decision, reason, checks = _decision_for(source, policy, mode)
    if decision == "block":
        source.compliance_status = "blocked"
        policy.compliance_status = "blocked"
    elif decision == "allow":
        source.compliance_status = "approved"
        policy.compliance_status = "approved"
    else:
        source.compliance_status = "approved_limited"
        policy.compliance_status = "approved_limited"
    policy.reviewed_at = policy.reviewed_at or datetime.now(UTC)
    row = ComplianceDecision(
        source_id=source.id,
        source_policy_id=policy.id,
        mode=mode,
        decision=decision,
        reason=reason,
        checks=checks,
        decided_by=decided_by,
        metadata_={"policy_version": "v1"},
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def can_collect_source(source: Source, mode: str = "speed") -> bool:
    if not source.enabled:
        return False
    if source.compliance_status in BLOCKING_STATUSES or source.collection_mode == "none":
        return False
    if mode == "verified":
        return source.compliance_status in {"approved", "approved_limited"}
    return True
