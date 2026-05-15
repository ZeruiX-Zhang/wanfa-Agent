"""Human oversight quality gate for Reality OS knowledge pipeline.

This module manages the review workflow for knowledge items that require
human approval before formal ingestion. It provides:

- Submission of items to the review queue
- Approve/reject operations with audit logging
- Batch approve/reject for bulk operations
- Listing pending review items
- Preview reports for pre-ingestion scoring

Design principles:
- Uses the same SQLite database as KnowledgeCore (via get_core())
- All review operations are recorded to the trace system
- Reject operations write to the audit_log table
- Batch operations are transactional
- Pending items are ordered by created_at DESC
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from .knowledge_core import SourceKind, get_core
from .skill_validator import ValidationResult, ValidationDimension


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ReviewItem:
    """A knowledge item in the review queue."""

    id: str
    tenant_id: str
    knowledge_item_id: str | None
    title: str
    original_body: str
    model_summary: str | None
    divergence_score: float
    validation_result: ValidationResult
    status: Literal["pending_review", "approved", "rejected"]
    reviewer: str | None
    reject_reason: str | None
    created_at: str
    reviewed_at: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "knowledge_item_id": self.knowledge_item_id,
            "title": self.title,
            "original_body": self.original_body,
            "model_summary": self.model_summary,
            "divergence_score": round(self.divergence_score, 4),
            "validation_result": {
                "passed": self.validation_result.passed,
                "dimensions": [
                    {
                        "name": d.name,
                        "passed": d.passed,
                        "score": round(d.score, 3),
                        "severity": d.severity,
                        "details": d.details,
                    }
                    for d in self.validation_result.dimensions
                ],
                "skill_used": self.validation_result.skill_used,
                "overall_severity": self.validation_result.overall_severity,
                "warnings": self.validation_result.warnings,
                "blocking_issues": self.validation_result.blocking_issues,
            },
            "status": self.status,
            "reviewer": self.reviewer,
            "reject_reason": self.reject_reason,
            "created_at": self.created_at,
            "reviewed_at": self.reviewed_at,
        }


# ---------------------------------------------------------------------------
# QualityGate
# ---------------------------------------------------------------------------


class QualityGate:
    """Human oversight quality gate for the knowledge pipeline.

    Manages the review queue, approval/rejection workflow, and provides
    preview reports for pre-ingestion scoring.
    """

    def submit_for_review(
        self,
        *,
        tenant_id: str,
        knowledge_item_id: str | None = None,
        title: str,
        original_body: str,
        model_summary: str | None = None,
        divergence_score: float = 0.0,
        validation_result: ValidationResult,
        actor: str = "system",
    ) -> ReviewItem:
        """Submit a knowledge item to the review queue.

        Creates a new entry in the review_queue table with status
        'pending_review' and records the operation to the trace system.
        """
        from . import trace

        review_id = _new_id("rev")
        now = _utc_now_iso()

        validation_json = json.dumps(
            {
                "passed": validation_result.passed,
                "dimensions": [
                    {
                        "name": d.name,
                        "passed": d.passed,
                        "score": d.score,
                        "severity": d.severity,
                        "details": d.details,
                    }
                    for d in validation_result.dimensions
                ],
                "skill_used": validation_result.skill_used,
                "overall_severity": validation_result.overall_severity,
                "warnings": validation_result.warnings,
                "blocking_issues": validation_result.blocking_issues,
            },
            ensure_ascii=False,
        )

        core = get_core()
        with core._lock, core._connect() as db:
            db.execute(
                """
                INSERT INTO review_queue(
                    id, tenant_id, knowledge_item_id, title, original_body,
                    model_summary, divergence_score, validation_result_json,
                    status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    review_id,
                    tenant_id,
                    knowledge_item_id,
                    title,
                    original_body,
                    model_summary,
                    divergence_score,
                    validation_json,
                    "pending_review",
                    now,
                ),
            )

        # Record to trace system
        trace.record_step(
            run_id=None,
            step_type="quality_gate_submit",
            status="completed",
            input_value={
                "tenant_id": tenant_id,
                "knowledge_item_id": knowledge_item_id,
                "title": title,
                "divergence_score": divergence_score,
            },
            output_value={"review_id": review_id, "status": "pending_review"},
            metadata={"actor": actor},
        )

        return ReviewItem(
            id=review_id,
            tenant_id=tenant_id,
            knowledge_item_id=knowledge_item_id,
            title=title,
            original_body=original_body,
            model_summary=model_summary,
            divergence_score=divergence_score,
            validation_result=validation_result,
            status="pending_review",
            reviewer=None,
            reject_reason=None,
            created_at=now,
            reviewed_at=None,
        )

    def approve(
        self,
        *,
        tenant_id: str,
        review_id: str,
        reviewer: str,
    ) -> ReviewItem:
        """Approve a pending review item.

        Updates the review_queue status to 'approved', then updates the
        associated knowledge_item's validation_status to 'passed' to
        complete formal ingestion.
        """
        from . import trace

        now = _utc_now_iso()
        core = get_core()

        with core._lock, core._connect() as db:
            row = db.execute(
                "SELECT * FROM review_queue WHERE id = ? AND tenant_id = ?",
                (review_id, tenant_id),
            ).fetchone()

            if row is None:
                raise KeyError(f"Review item not found: {review_id}")

            if row["status"] != "pending_review":
                raise ValueError(
                    f"Review item {review_id} is not pending (status: {row['status']})"
                )

            # Update review_queue status
            db.execute(
                """
                UPDATE review_queue
                SET status = 'approved', reviewer = ?, reviewed_at = ?
                WHERE id = ? AND tenant_id = ?
                """,
                (reviewer, now, review_id, tenant_id),
            )

            # Complete formal ingestion: update knowledge_items validation_status
            knowledge_item_id = row["knowledge_item_id"]
            if knowledge_item_id:
                db.execute(
                    """
                    UPDATE knowledge_items
                    SET validation_status = 'passed', review_required = 0, updated_at = ?
                    WHERE id = ? AND tenant_id = ?
                    """,
                    (now, knowledge_item_id, tenant_id),
                )

        # Record to trace system
        trace.record_step(
            run_id=None,
            step_type="quality_gate_approve",
            status="completed",
            input_value={
                "tenant_id": tenant_id,
                "review_id": review_id,
                "reviewer": reviewer,
            },
            output_value={
                "status": "approved",
                "knowledge_item_id": knowledge_item_id,
            },
        )

        validation_result = _parse_validation_json(row["validation_result_json"])

        return ReviewItem(
            id=review_id,
            tenant_id=tenant_id,
            knowledge_item_id=knowledge_item_id,
            title=row["title"],
            original_body=row["original_body"],
            model_summary=row["model_summary"],
            divergence_score=row["divergence_score"],
            validation_result=validation_result,
            status="approved",
            reviewer=reviewer,
            reject_reason=None,
            created_at=row["created_at"],
            reviewed_at=now,
        )

    def reject(
        self,
        *,
        tenant_id: str,
        review_id: str,
        reviewer: str,
        reason: str,
    ) -> ReviewItem:
        """Reject a pending review item.

        Updates the review_queue status to 'rejected' and records the
        rejection reason to the audit_log table.
        """
        from . import trace

        now = _utc_now_iso()
        core = get_core()

        with core._lock, core._connect() as db:
            row = db.execute(
                "SELECT * FROM review_queue WHERE id = ? AND tenant_id = ?",
                (review_id, tenant_id),
            ).fetchone()

            if row is None:
                raise KeyError(f"Review item not found: {review_id}")

            if row["status"] != "pending_review":
                raise ValueError(
                    f"Review item {review_id} is not pending (status: {row['status']})"
                )

            # Update review_queue status
            db.execute(
                """
                UPDATE review_queue
                SET status = 'rejected', reviewer = ?, reject_reason = ?, reviewed_at = ?
                WHERE id = ? AND tenant_id = ?
                """,
                (reviewer, reason, now, review_id, tenant_id),
            )

            # Update knowledge_items validation_status if linked
            knowledge_item_id = row["knowledge_item_id"]
            if knowledge_item_id:
                db.execute(
                    """
                    UPDATE knowledge_items
                    SET validation_status = 'failed', updated_at = ?
                    WHERE id = ? AND tenant_id = ?
                    """,
                    (now, knowledge_item_id, tenant_id),
                )

            # Record rejection reason to audit_log
            audit_id = _new_id("aud")
            db.execute(
                """
                INSERT INTO audit_log(id, tenant_id, actor, action, subject, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    audit_id,
                    tenant_id,
                    reviewer,
                    "review_reject",
                    review_id,
                    json.dumps(
                        {
                            "review_id": review_id,
                            "knowledge_item_id": knowledge_item_id,
                            "reason": reason,
                            "title": row["title"],
                        },
                        ensure_ascii=False,
                    ),
                    now,
                ),
            )

        # Record to trace system
        trace.record_step(
            run_id=None,
            step_type="quality_gate_reject",
            status="completed",
            input_value={
                "tenant_id": tenant_id,
                "review_id": review_id,
                "reviewer": reviewer,
                "reason": reason,
            },
            output_value={
                "status": "rejected",
                "knowledge_item_id": knowledge_item_id,
            },
        )

        validation_result = _parse_validation_json(row["validation_result_json"])

        return ReviewItem(
            id=review_id,
            tenant_id=tenant_id,
            knowledge_item_id=knowledge_item_id,
            title=row["title"],
            original_body=row["original_body"],
            model_summary=row["model_summary"],
            divergence_score=row["divergence_score"],
            validation_result=validation_result,
            status="rejected",
            reviewer=reviewer,
            reject_reason=reason,
            created_at=row["created_at"],
            reviewed_at=now,
        )

    def batch_approve(
        self,
        *,
        tenant_id: str,
        review_ids: list[str],
        reviewer: str,
    ) -> list[ReviewItem]:
        """Batch approve multiple pending review items.

        All operations are transactional — if any item fails, the entire
        batch is rolled back.
        """
        from . import trace

        if not review_ids:
            return []

        now = _utc_now_iso()
        core = get_core()
        results: list[ReviewItem] = []

        with core._lock, core._connect() as db:
            for review_id in review_ids:
                row = db.execute(
                    "SELECT * FROM review_queue WHERE id = ? AND tenant_id = ?",
                    (review_id, tenant_id),
                ).fetchone()

                if row is None:
                    raise KeyError(f"Review item not found: {review_id}")

                if row["status"] != "pending_review":
                    raise ValueError(
                        f"Review item {review_id} is not pending (status: {row['status']})"
                    )

                # Update review_queue status
                db.execute(
                    """
                    UPDATE review_queue
                    SET status = 'approved', reviewer = ?, reviewed_at = ?
                    WHERE id = ? AND tenant_id = ?
                    """,
                    (reviewer, now, review_id, tenant_id),
                )

                # Complete formal ingestion
                knowledge_item_id = row["knowledge_item_id"]
                if knowledge_item_id:
                    db.execute(
                        """
                        UPDATE knowledge_items
                        SET validation_status = 'passed', review_required = 0, updated_at = ?
                        WHERE id = ? AND tenant_id = ?
                        """,
                        (now, knowledge_item_id, tenant_id),
                    )

                validation_result = _parse_validation_json(row["validation_result_json"])

                results.append(
                    ReviewItem(
                        id=review_id,
                        tenant_id=tenant_id,
                        knowledge_item_id=knowledge_item_id,
                        title=row["title"],
                        original_body=row["original_body"],
                        model_summary=row["model_summary"],
                        divergence_score=row["divergence_score"],
                        validation_result=validation_result,
                        status="approved",
                        reviewer=reviewer,
                        reject_reason=None,
                        created_at=row["created_at"],
                        reviewed_at=now,
                    )
                )

        # Record batch operation to trace system
        trace.record_step(
            run_id=None,
            step_type="quality_gate_batch_approve",
            status="completed",
            input_value={
                "tenant_id": tenant_id,
                "review_ids": review_ids,
                "reviewer": reviewer,
            },
            output_value={
                "approved_count": len(results),
            },
        )

        return results

    def batch_reject(
        self,
        *,
        tenant_id: str,
        review_ids: list[str],
        reviewer: str,
        reason: str,
    ) -> list[ReviewItem]:
        """Batch reject multiple pending review items.

        All operations are transactional — if any item fails, the entire
        batch is rolled back. Each rejection is recorded to the audit_log.
        """
        from . import trace

        if not review_ids:
            return []

        now = _utc_now_iso()
        core = get_core()
        results: list[ReviewItem] = []

        with core._lock, core._connect() as db:
            for review_id in review_ids:
                row = db.execute(
                    "SELECT * FROM review_queue WHERE id = ? AND tenant_id = ?",
                    (review_id, tenant_id),
                ).fetchone()

                if row is None:
                    raise KeyError(f"Review item not found: {review_id}")

                if row["status"] != "pending_review":
                    raise ValueError(
                        f"Review item {review_id} is not pending (status: {row['status']})"
                    )

                # Update review_queue status
                db.execute(
                    """
                    UPDATE review_queue
                    SET status = 'rejected', reviewer = ?, reject_reason = ?, reviewed_at = ?
                    WHERE id = ? AND tenant_id = ?
                    """,
                    (reviewer, reason, now, review_id, tenant_id),
                )

                # Update knowledge_items validation_status if linked
                knowledge_item_id = row["knowledge_item_id"]
                if knowledge_item_id:
                    db.execute(
                        """
                        UPDATE knowledge_items
                        SET validation_status = 'failed', updated_at = ?
                        WHERE id = ? AND tenant_id = ?
                        """,
                        (now, knowledge_item_id, tenant_id),
                    )

                # Record rejection to audit_log
                audit_id = _new_id("aud")
                db.execute(
                    """
                    INSERT INTO audit_log(id, tenant_id, actor, action, subject, payload_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        audit_id,
                        tenant_id,
                        reviewer,
                        "review_reject",
                        review_id,
                        json.dumps(
                            {
                                "review_id": review_id,
                                "knowledge_item_id": knowledge_item_id,
                                "reason": reason,
                                "title": row["title"],
                            },
                            ensure_ascii=False,
                        ),
                        now,
                    ),
                )

                validation_result = _parse_validation_json(row["validation_result_json"])

                results.append(
                    ReviewItem(
                        id=review_id,
                        tenant_id=tenant_id,
                        knowledge_item_id=knowledge_item_id,
                        title=row["title"],
                        original_body=row["original_body"],
                        model_summary=row["model_summary"],
                        divergence_score=row["divergence_score"],
                        validation_result=validation_result,
                        status="rejected",
                        reviewer=reviewer,
                        reject_reason=reason,
                        created_at=row["created_at"],
                        reviewed_at=now,
                    )
                )

        # Record batch operation to trace system
        trace.record_step(
            run_id=None,
            step_type="quality_gate_batch_reject",
            status="completed",
            input_value={
                "tenant_id": tenant_id,
                "review_ids": review_ids,
                "reviewer": reviewer,
                "reason": reason,
            },
            output_value={
                "rejected_count": len(results),
            },
        )

        return results

    def list_pending(
        self,
        *,
        tenant_id: str,
        limit: int = 50,
    ) -> list[ReviewItem]:
        """List pending review items ordered by created_at DESC.

        Returns up to `limit` items that are in 'pending_review' status.
        """
        core = get_core()

        with core._lock, core._connect() as db:
            rows = db.execute(
                """
                SELECT * FROM review_queue
                WHERE tenant_id = ? AND status = 'pending_review'
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (tenant_id, limit),
            ).fetchall()

        results: list[ReviewItem] = []
        for row in rows:
            validation_result = _parse_validation_json(row["validation_result_json"])
            results.append(
                ReviewItem(
                    id=row["id"],
                    tenant_id=row["tenant_id"],
                    knowledge_item_id=row["knowledge_item_id"],
                    title=row["title"],
                    original_body=row["original_body"],
                    model_summary=row["model_summary"],
                    divergence_score=row["divergence_score"],
                    validation_result=validation_result,
                    status=row["status"],
                    reviewer=row["reviewer"],
                    reject_reason=row["reject_reason"],
                    created_at=row["created_at"],
                    reviewed_at=row["reviewed_at"],
                )
            )

        return results

    def get_preview_report(
        self,
        *,
        tenant_id: str,
        title: str,
        body: str,
        source_kind: SourceKind,
        source_url: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Generate a full pre-ingestion scoring preview report.

        Calls ModelSummarizer and SkillValidator to produce a comprehensive
        report without actually ingesting the knowledge item. This allows
        users to preview scores and potential issues before committing.
        """
        from .model_summarizer import ModelSummarizer
        from .skill_validator import SkillValidator
        from . import trace

        tags = tags or []

        # Generate summary preview
        summarizer = ModelSummarizer()
        summary_result = summarizer.summarize(
            title=title,
            body=body,
            source_kind=source_kind,
            language="zh-CN",
        )

        # Run validation preview
        validator = SkillValidator()
        validation_result = validator.validate(
            item_title=title,
            item_body=body,
            source_kind=source_kind,
            tags=tags,
            source_url=source_url,
        )

        # Determine if human review would be triggered
        review_required = (
            summary_result.divergence_score > 0.3
            or validation_result.overall_severity == "critical"
        )

        # Build the preview report
        report: dict[str, Any] = {
            "title": title,
            "source_kind": source_kind,
            "source_url": source_url,
            "tags": tags,
            "summary": summary_result.to_dict(),
            "validation": {
                "passed": validation_result.passed,
                "overall_severity": validation_result.overall_severity,
                "dimensions": [
                    {
                        "name": d.name,
                        "passed": d.passed,
                        "score": round(d.score, 3),
                        "severity": d.severity,
                        "details": d.details,
                    }
                    for d in validation_result.dimensions
                ],
                "warnings": validation_result.warnings,
                "blocking_issues": validation_result.blocking_issues,
                "skill_used": validation_result.skill_used,
            },
            "review_required": review_required,
            "divergence_score": round(summary_result.divergence_score, 4),
            "recommendation": _build_recommendation(
                validation_result, summary_result.divergence_score, review_required
            ),
        }

        # Record preview to trace
        trace.record_step(
            run_id=None,
            step_type="quality_gate_preview",
            status="completed",
            input_value={
                "tenant_id": tenant_id,
                "title": title,
                "source_kind": source_kind,
            },
            output_value={
                "review_required": review_required,
                "overall_severity": validation_result.overall_severity,
                "divergence_score": summary_result.divergence_score,
            },
        )

        return report


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _parse_validation_json(json_str: str) -> ValidationResult:
    """Parse a validation_result_json string back into a ValidationResult."""
    try:
        data = json.loads(json_str) if json_str else {}
    except (json.JSONDecodeError, TypeError):
        data = {}

    dimensions: list[ValidationDimension] = []
    for dim_data in data.get("dimensions", []):
        dimensions.append(
            ValidationDimension(
                name=dim_data.get("name", "unknown"),
                passed=dim_data.get("passed", True),
                score=dim_data.get("score", 1.0),
                severity=dim_data.get("severity", "pass"),
                details=dim_data.get("details", ""),
            )
        )

    return ValidationResult(
        passed=data.get("passed", True),
        dimensions=dimensions,
        skill_used=data.get("skill_used"),
        overall_severity=data.get("overall_severity", "pass"),
        warnings=data.get("warnings", []),
        blocking_issues=data.get("blocking_issues", []),
    )


def _build_recommendation(
    validation_result: ValidationResult,
    divergence_score: float,
    review_required: bool,
) -> str:
    """Build a human-readable recommendation based on validation results."""
    if validation_result.overall_severity == "critical":
        return (
            "该知识条目存在严重问题，建议修正后重新提交。"
            f"阻塞问题: {'; '.join(validation_result.blocking_issues)}"
        )

    if review_required:
        reasons: list[str] = []
        if divergence_score > 0.3:
            reasons.append(f"模型摘要与原文偏差较大 ({divergence_score:.1%})")
        if validation_result.overall_severity == "warning":
            reasons.append(f"验证警告: {'; '.join(validation_result.warnings)}")
        return f"建议人工审核。原因: {'; '.join(reasons)}"

    if validation_result.warnings:
        return f"可以入库，但存在警告: {'; '.join(validation_result.warnings)}"

    return "所有检查通过，可以直接入库。"
