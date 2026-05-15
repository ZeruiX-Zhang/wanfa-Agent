"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-08 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("url", sa.Text()),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("trust_score", sa.Float(), nullable=False),
        sa.Column("language", sa.String(20), nullable=False),
        sa.Column("country", sa.String(20)),
        sa.Column("fetch_interval_minutes", sa.Integer(), nullable=False),
        sa.Column("rate_limit_per_minute", sa.Integer(), nullable=False),
        sa.Column("legal_use_policy", sa.String(80), nullable=False),
        sa.Column("robots_policy", sa.String(80), nullable=False),
        sa.Column("license_name", sa.String(160)),
        sa.Column("terms_url", sa.Text()),
        sa.Column("compliance_status", sa.String(80), nullable=False),
        sa.Column("collection_mode", sa.String(80), nullable=False),
        sa.Column("attribution_required", sa.Boolean(), nullable=False),
        sa.Column("last_fetched_at", sa.DateTime(timezone=True)),
        sa.Column("last_status", sa.String(80)),
        sa.Column("last_error", sa.Text()),
        sa.Column("metadata", sa.JSON(), nullable=False),
        *timestamps(),
    )
    op.create_index("ix_sources_type", "sources", ["type"])
    op.create_index("ix_sources_category", "sources", ["category"])
    op.create_index("ix_sources_enabled", "sources", ["enabled"])
    op.create_index("ix_sources_legal_use_policy", "sources", ["legal_use_policy"])
    op.create_index("ix_sources_robots_policy", "sources", ["robots_policy"])
    op.create_index("ix_sources_compliance_status", "sources", ["compliance_status"])

    op.create_table(
        "source_policies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_id", sa.String(36), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("access_type", sa.String(80), nullable=False),
        sa.Column("allowed_uses", sa.JSON(), nullable=False),
        sa.Column("disallowed_uses", sa.JSON(), nullable=False),
        sa.Column("robots_txt_status", sa.String(80), nullable=False),
        sa.Column("license_name", sa.String(160)),
        sa.Column("terms_url", sa.Text()),
        sa.Column("retention_days", sa.Integer(), nullable=False),
        sa.Column("pii_handling", sa.String(120), nullable=False),
        sa.Column("requires_attribution", sa.Boolean(), nullable=False),
        sa.Column("compliance_status", sa.String(80), nullable=False),
        sa.Column("reviewed_by", sa.String(120)),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("notes", sa.Text()),
        sa.Column("metadata", sa.JSON(), nullable=False),
        *timestamps(),
        sa.UniqueConstraint("source_id", name="uq_source_policies_source_id"),
    )
    op.create_index("ix_source_policies_source_id", "source_policies", ["source_id"])
    op.create_index("ix_source_policies_compliance_status", "source_policies", ["compliance_status"])

    op.create_table(
        "compliance_decisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_id", sa.String(36), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("source_policy_id", sa.String(36), sa.ForeignKey("source_policies.id")),
        sa.Column("mode", sa.String(40), nullable=False),
        sa.Column("decision", sa.String(80), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("checks", sa.JSON(), nullable=False),
        sa.Column("decided_by", sa.String(120), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        *timestamps(),
    )
    op.create_index("ix_compliance_decisions_source_id", "compliance_decisions", ["source_id"])
    op.create_index("ix_compliance_decisions_source_policy_id", "compliance_decisions", ["source_policy_id"])
    op.create_index("ix_compliance_decisions_mode", "compliance_decisions", ["mode"])
    op.create_index("ix_compliance_decisions_decision", "compliance_decisions", ["decision"])

    op.create_table(
        "raw_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_id", sa.String(36), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text()),
        sa.Column("snippet", sa.Text()),
        sa.Column("raw_content", sa.Text()),
        sa.Column("content_type", sa.String(100)),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(80), nullable=False),
        sa.Column("error_reason", sa.Text()),
        sa.Column("metadata", sa.JSON(), nullable=False),
        *timestamps(),
        sa.UniqueConstraint("source_id", "url", name="uq_raw_source_url"),
    )
    op.create_index("ix_raw_documents_source_id", "raw_documents", ["source_id"])
    op.create_index("ix_raw_documents_status", "raw_documents", ["status"])

    op.create_table(
        "event_clusters",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("language", sa.String(20), nullable=False),
        sa.Column("cross_language_key", sa.String(120)),
        sa.Column("merged_summary", sa.Text(), nullable=False),
        sa.Column("source_diversity_score", sa.Float(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("importance_score", sa.Float(), nullable=False),
        sa.Column("verification_status", sa.String(80), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        *timestamps(),
    )
    op.create_index("ix_event_clusters_category", "event_clusters", ["category"])
    op.create_index("ix_event_clusters_language", "event_clusters", ["language"])
    op.create_index("ix_event_clusters_cross_language_key", "event_clusters", ["cross_language_key"])
    op.create_index("ix_event_clusters_importance_score", "event_clusters", ["importance_score"])
    op.create_index("ix_event_clusters_verification_status", "event_clusters", ["verification_status"])

    op.create_table(
        "cross_language_candidates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("cluster_id", sa.String(36), sa.ForeignKey("event_clusters.id"), nullable=False),
        sa.Column("candidate_cluster_id", sa.String(36), sa.ForeignKey("event_clusters.id"), nullable=False),
        sa.Column("source_language", sa.String(20), nullable=False),
        sa.Column("target_language", sa.String(20), nullable=False),
        sa.Column("similarity_score", sa.Float(), nullable=False),
        sa.Column("shared_entities", sa.JSON(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(80), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        *timestamps(),
        sa.UniqueConstraint("cluster_id", "candidate_cluster_id", name="uq_cross_language_pair"),
    )
    op.create_index("ix_cross_language_candidates_cluster_id", "cross_language_candidates", ["cluster_id"])
    op.create_index("ix_cross_language_candidates_candidate_cluster_id", "cross_language_candidates", ["candidate_cluster_id"])
    op.create_index("ix_cross_language_candidates_source_language", "cross_language_candidates", ["source_language"])
    op.create_index("ix_cross_language_candidates_target_language", "cross_language_candidates", ["target_language"])
    op.create_index("ix_cross_language_candidates_similarity_score", "cross_language_candidates", ["similarity_score"])
    op.create_index("ix_cross_language_candidates_status", "cross_language_candidates", ["status"])

    op.create_table(
        "normalized_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("raw_document_id", sa.String(36), sa.ForeignKey("raw_documents.id"), nullable=False),
        sa.Column("canonical_url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("clean_text", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text()),
        sa.Column("language", sa.String(20), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_id", sa.String(36), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("author", sa.String(200)),
        sa.Column("entities", sa.JSON(), nullable=False),
        sa.Column("domain", sa.String(80)),
        sa.Column("legal_use_policy", sa.String(80), nullable=False),
        sa.Column("compliance_status", sa.String(80), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("simhash", sa.String(32)),
        sa.Column("embedding_id", sa.String(100)),
        sa.Column("status", sa.String(80), nullable=False),
        sa.Column("quality_flags", sa.JSON(), nullable=False),
        sa.Column("published_at_inferred", sa.Boolean(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        *timestamps(),
        sa.UniqueConstraint("raw_document_id"),
    )
    op.create_index("ix_normalized_documents_raw_document_id", "normalized_documents", ["raw_document_id"])
    op.create_index("ix_normalized_documents_canonical_url", "normalized_documents", ["canonical_url"])
    op.create_index("ix_normalized_documents_source_id", "normalized_documents", ["source_id"])
    op.create_index("ix_normalized_documents_domain", "normalized_documents", ["domain"])
    op.create_index("ix_normalized_documents_compliance_status", "normalized_documents", ["compliance_status"])
    op.create_index("ix_normalized_documents_content_hash", "normalized_documents", ["content_hash"])
    op.create_index("ix_normalized_documents_status", "normalized_documents", ["status"])

    op.create_table(
        "events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True)),
        sa.Column("entities", sa.JSON(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("why_it_matters", sa.Text(), nullable=False),
        sa.Column("affected_parties", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("novelty_score", sa.Float(), nullable=False),
        sa.Column("impact_score", sa.Float(), nullable=False),
        sa.Column("actionability_score", sa.Float(), nullable=False),
        sa.Column("index_credibility", sa.Float(), nullable=False),
        sa.Column("index_novelty", sa.Float(), nullable=False),
        sa.Column("index_impact", sa.Float(), nullable=False),
        sa.Column("index_actionability", sa.Float(), nullable=False),
        sa.Column("index_urgency", sa.Float(), nullable=False),
        sa.Column("importance_score", sa.Float(), nullable=False),
        sa.Column("verification_status", sa.String(80), nullable=False),
        sa.Column("extraction_status", sa.String(80), nullable=False),
        sa.Column("cluster_id", sa.String(36), sa.ForeignKey("event_clusters.id")),
        sa.Column("metadata", sa.JSON(), nullable=False),
        *timestamps(),
    )
    op.create_index("ix_events_category", "events", ["category"])
    op.create_index("ix_events_event_time", "events", ["event_time"])
    op.create_index("ix_events_index_credibility", "events", ["index_credibility"])
    op.create_index("ix_events_importance_score", "events", ["importance_score"])
    op.create_index("ix_events_verification_status", "events", ["verification_status"])
    op.create_index("ix_events_extraction_status", "events", ["extraction_status"])
    op.create_index("ix_events_cluster_id", "events", ["cluster_id"])

    op.create_table(
        "event_claims",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_id", sa.String(36), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("evidence_quote", sa.Text()),
        sa.Column("evidence_url", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("needs_verification", sa.Boolean(), nullable=False),
        *timestamps(),
    )
    op.create_index("ix_event_claims_event_id", "event_claims", ["event_id"])

    op.create_table(
        "event_evidence",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_id", sa.String(36), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("normalized_document_id", sa.String(36), sa.ForeignKey("normalized_documents.id"), nullable=False),
        sa.Column("evidence_url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text()),
        sa.Column("source_name", sa.String(200)),
        sa.Column("quote", sa.Text()),
        sa.Column("ledger_hash", sa.String(64)),
        *timestamps(),
    )
    op.create_index("ix_event_evidence_event_id", "event_evidence", ["event_id"])
    op.create_index("ix_event_evidence_normalized_document_id", "event_evidence", ["normalized_document_id"])
    op.create_index("ix_event_evidence_ledger_hash", "event_evidence", ["ledger_hash"])

    op.create_table(
        "intelligence_objects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("object_type", sa.String(80), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("domain", sa.String(80), nullable=False),
        sa.Column("language", sa.String(20), nullable=False),
        sa.Column("region", sa.String(80)),
        sa.Column("canonical_url", sa.Text()),
        sa.Column("event_id", sa.String(36), sa.ForeignKey("events.id")),
        sa.Column("cluster_id", sa.String(36), sa.ForeignKey("event_clusters.id")),
        sa.Column("normalized_document_id", sa.String(36), sa.ForeignKey("normalized_documents.id")),
        sa.Column("entities", sa.JSON(), nullable=False),
        sa.Column("source_document_ids", sa.JSON(), nullable=False),
        sa.Column("source_count", sa.Integer(), nullable=False),
        sa.Column("evidence_count", sa.Integer(), nullable=False),
        sa.Column("mode", sa.String(40), nullable=False),
        sa.Column("status", sa.String(80), nullable=False),
        sa.Column("verification_status", sa.String(80), nullable=False),
        sa.Column("index_credibility", sa.Float(), nullable=False),
        sa.Column("index_novelty", sa.Float(), nullable=False),
        sa.Column("index_impact", sa.Float(), nullable=False),
        sa.Column("index_actionability", sa.Float(), nullable=False),
        sa.Column("index_urgency", sa.Float(), nullable=False),
        sa.Column("aggregate_score", sa.Float(), nullable=False),
        sa.Column("compliance_status", sa.String(80), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        *timestamps(),
    )
    op.create_index("ix_intelligence_objects_object_type", "intelligence_objects", ["object_type"])
    op.create_index("ix_intelligence_objects_domain", "intelligence_objects", ["domain"])
    op.create_index("ix_intelligence_objects_language", "intelligence_objects", ["language"])
    op.create_index("ix_intelligence_objects_region", "intelligence_objects", ["region"])
    op.create_index("ix_intelligence_objects_event_id", "intelligence_objects", ["event_id"])
    op.create_index("ix_intelligence_objects_cluster_id", "intelligence_objects", ["cluster_id"])
    op.create_index("ix_intelligence_objects_normalized_document_id", "intelligence_objects", ["normalized_document_id"])
    op.create_index("ix_intelligence_objects_mode", "intelligence_objects", ["mode"])
    op.create_index("ix_intelligence_objects_status", "intelligence_objects", ["status"])
    op.create_index("ix_intelligence_objects_verification_status", "intelligence_objects", ["verification_status"])
    op.create_index("ix_intelligence_objects_index_credibility", "intelligence_objects", ["index_credibility"])
    op.create_index("ix_intelligence_objects_aggregate_score", "intelligence_objects", ["aggregate_score"])
    op.create_index("ix_intelligence_objects_compliance_status", "intelligence_objects", ["compliance_status"])

    op.create_table(
        "evidence_ledger_entries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("intelligence_object_id", sa.String(36), sa.ForeignKey("intelligence_objects.id")),
        sa.Column("event_id", sa.String(36), sa.ForeignKey("events.id")),
        sa.Column("normalized_document_id", sa.String(36), sa.ForeignKey("normalized_documents.id")),
        sa.Column("source_id", sa.String(36), sa.ForeignKey("sources.id")),
        sa.Column("evidence_url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text()),
        sa.Column("source_name", sa.String(200)),
        sa.Column("source_type", sa.String(80)),
        sa.Column("quote", sa.Text()),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("ledger_hash", sa.String(64), nullable=False),
        sa.Column("citation_status", sa.String(80), nullable=False),
        sa.Column("legal_use_policy", sa.String(80), nullable=False),
        sa.Column("compliance_status", sa.String(80), nullable=False),
        sa.Column("trust_score", sa.Float(), nullable=False),
        sa.Column("relevance_score", sa.Float(), nullable=False),
        sa.Column("supports_claims", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        *timestamps(),
        sa.UniqueConstraint("ledger_hash", name="uq_evidence_ledger_hash"),
    )
    op.create_index("ix_evidence_ledger_entries_intelligence_object_id", "evidence_ledger_entries", ["intelligence_object_id"])
    op.create_index("ix_evidence_ledger_entries_event_id", "evidence_ledger_entries", ["event_id"])
    op.create_index("ix_evidence_ledger_entries_normalized_document_id", "evidence_ledger_entries", ["normalized_document_id"])
    op.create_index("ix_evidence_ledger_entries_source_id", "evidence_ledger_entries", ["source_id"])
    op.create_index("ix_evidence_ledger_entries_source_type", "evidence_ledger_entries", ["source_type"])
    op.create_index("ix_evidence_ledger_entries_captured_at", "evidence_ledger_entries", ["captured_at"])
    op.create_index("ix_evidence_ledger_entries_content_hash", "evidence_ledger_entries", ["content_hash"])
    op.create_index("ix_evidence_ledger_entries_ledger_hash", "evidence_ledger_entries", ["ledger_hash"])
    op.create_index("ix_evidence_ledger_entries_citation_status", "evidence_ledger_entries", ["citation_status"])
    op.create_index("ix_evidence_ledger_entries_compliance_status", "evidence_ledger_entries", ["compliance_status"])

    op.create_table(
        "reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("report_type", sa.String(80), nullable=False),
        sa.Column("mode", sa.String(40), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True)),
        sa.Column("period_end", sa.DateTime(timezone=True)),
        sa.Column("markdown", sa.Text(), nullable=False),
        sa.Column("json_content", sa.JSON(), nullable=False),
        sa.Column("html", sa.Text()),
        sa.Column("generation_seconds", sa.Float(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        *timestamps(),
    )
    op.create_index("ix_reports_report_type", "reports", ["report_type"])
    op.create_index("ix_reports_mode", "reports", ["mode"])

    op.create_table(
        "report_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("report_id", sa.String(36), sa.ForeignKey("reports.id"), nullable=False),
        sa.Column("event_id", sa.String(36), sa.ForeignKey("events.id")),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("recommended_action", sa.Text(), nullable=False),
        *timestamps(),
    )
    op.create_index("ix_report_items_report_id", "report_items", ["report_id"])
    op.create_index("ix_report_items_event_id", "report_items", ["event_id"])

    op.create_table(
        "watchlists",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("type", sa.String(80), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("value", sa.String(300), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        *timestamps(),
    )
    op.create_index("ix_watchlists_type", "watchlists", ["type"])

    op.create_table(
        "jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("type", sa.String(80), nullable=False),
        sa.Column("mode", sa.String(40), nullable=False),
        sa.Column("status", sa.String(80), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("success_count", sa.Integer(), nullable=False),
        sa.Column("failure_count", sa.Integer(), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        *timestamps(),
    )
    op.create_index("ix_jobs_type", "jobs", ["type"])
    op.create_index("ix_jobs_mode", "jobs", ["mode"])
    op.create_index("ix_jobs_status", "jobs", ["status"])

    op.create_table(
        "job_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("level", sa.String(30), nullable=False),
        sa.Column("stage", sa.String(80), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        *timestamps(),
    )
    op.create_index("ix_job_logs_job_id", "job_logs", ["job_id"])
    op.create_index("ix_job_logs_stage", "job_logs", ["stage"])

    op.create_table(
        "product_reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("product_name", sa.String(200), nullable=False),
        sa.Column("official_url", sa.Text()),
        sa.Column("target_users", sa.JSON(), nullable=False),
        sa.Column("competitors", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("status", sa.String(80), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        *timestamps(),
    )
    op.create_index("ix_product_reviews_product_name", "product_reviews", ["product_name"])
    op.create_index("ix_product_reviews_status", "product_reviews", ["status"])

    op.create_table(
        "product_review_evidence",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("review_id", sa.String(36), sa.ForeignKey("product_reviews.id"), nullable=False),
        sa.Column("source_type", sa.String(80), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text()),
        sa.Column("snippet", sa.Text()),
        sa.Column("confidence", sa.Float(), nullable=False),
        *timestamps(),
    )
    op.create_index("ix_product_review_evidence_review_id", "product_review_evidence", ["review_id"])

    op.create_table(
        "settings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("key", sa.String(120), nullable=False, unique=True),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("is_secret", sa.Boolean(), nullable=False),
        *timestamps(),
    )
    op.create_index("ix_settings_key", "settings", ["key"], unique=True)

    op.create_table(
        "api_usage_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("operation", sa.String(120), nullable=False),
        sa.Column("status", sa.String(80), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("cost_estimate", sa.Float(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        *timestamps(),
    )
    op.create_index("ix_api_usage_logs_provider", "api_usage_logs", ["provider"])
    op.create_index("ix_api_usage_logs_status", "api_usage_logs", ["status"])


def downgrade() -> None:
    for table in [
        "api_usage_logs",
        "settings",
        "product_review_evidence",
        "product_reviews",
        "job_logs",
        "jobs",
        "watchlists",
        "report_items",
        "reports",
        "evidence_ledger_entries",
        "intelligence_objects",
        "event_evidence",
        "event_claims",
        "events",
        "normalized_documents",
        "cross_language_candidates",
        "event_clusters",
        "raw_documents",
        "compliance_decisions",
        "source_policies",
        "sources",
    ]:
        op.drop_table(table)
