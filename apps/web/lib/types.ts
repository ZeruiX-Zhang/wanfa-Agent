export type Page<T> = {
  items: T[];
  total: number;
  limit: number;
  offset: number;
};

export type Source = {
  id: string;
  name: string;
  type: string;
  category: string;
  url: string | null;
  enabled: boolean;
  trust_score: number;
  language: string;
  country: string | null;
  fetch_interval_minutes: number;
  rate_limit_per_minute: number;
  legal_use_policy: string;
  robots_policy: string;
  license_name: string | null;
  terms_url: string | null;
  compliance_status: string;
  collection_mode: string;
  attribution_required: boolean;
  last_fetched_at: string | null;
  last_status: string | null;
  last_error: string | null;
  metadata_: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type Event = {
  id: string;
  title: string;
  category: string;
  event_time: string | null;
  entities: string[];
  summary: string;
  why_it_matters: string;
  affected_parties: string[];
  confidence: number;
  novelty_score: number;
  impact_score: number;
  actionability_score: number;
  index_credibility: number;
  index_novelty: number;
  index_impact: number;
  index_actionability: number;
  index_urgency: number;
  importance_score: number;
  verification_status: string;
  extraction_status: string;
  cluster_id: string | null;
  metadata_: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type EventEvidence = {
  id: string;
  event_id: string;
  normalized_document_id: string;
  evidence_url: string;
  title: string | null;
  source_name: string | null;
  quote: string | null;
  created_at: string;
  updated_at: string;
};

export type EventClaim = {
  id: string;
  event_id: string;
  text: string;
  evidence_quote: string | null;
  evidence_url: string;
  confidence: number;
  needs_verification: boolean;
  created_at: string;
  updated_at: string;
};

export type EventDetail = Event & {
  claims: EventClaim[];
  evidence: EventEvidence[];
};

export type Report = {
  id: string;
  title: string;
  report_type: string;
  mode: string;
  period_start: string | null;
  period_end: string | null;
  generation_seconds: number;
  metadata_: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type ReportDetail = Report & {
  markdown: string;
  json_content: Record<string, unknown>;
  html: string | null;
  items: Array<{
    id: string;
    report_id: string;
    event_id: string | null;
    rank: number;
    title: string;
    summary: string;
    recommended_action: string;
    created_at: string;
    updated_at: string;
  }>;
};

export type Watchlist = {
  id: string;
  type: string;
  name: string;
  value: string;
  enabled: boolean;
  metadata_: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type Job = {
  id: string;
  name: string;
  type: string;
  mode: string;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  success_count: number;
  failure_count: number;
  parameters: Record<string, unknown>;
  metadata_: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type JobLog = {
  id: string;
  job_id: string;
  level: string;
  stage: string;
  message: string;
  details: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type JobDetail = Job & { logs: JobLog[] };

export type ProductReview = {
  id: string;
  product_name: string;
  official_url: string | null;
  target_users: string[];
  competitors: string[];
  result: Record<string, unknown>;
  confidence: number;
  status: string;
  metadata_: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type ProductReviewEvidence = {
  id: string;
  review_id: string;
  source_type: string;
  url: string;
  title: string | null;
  snippet: string | null;
  confidence: number;
  created_at: string;
  updated_at: string;
};

export type ProductReviewDetail = ProductReview & { evidence: ProductReviewEvidence[] };

export type DashboardOverview = {
  total_events_today: number;
  verified_events: number;
  high_impact_events: number;
  low_trust_events: number;
  category_distribution: Array<{ category: string; count: number }>;
  trend: Array<{ date: string; events: number }>;
  top_events: Array<{
    id: string;
    title: string;
    category: string;
    importance_score: number;
    confidence: number;
    verification_status: string;
  }>;
};

export type Settings = {
  llm_provider: string;
  llm_model: string;
  search_provider: string;
  report_time: string;
  retention_days: number;
  api_key_status: Record<string, boolean>;
  auth_required?: boolean;
  tenant_required_in_production?: boolean;
};

export type SourcePolicy = {
  id: string;
  source_id: string;
  access_type: string;
  allowed_uses: string[];
  disallowed_uses: string[];
  robots_txt_status: string;
  license_name: string | null;
  terms_url: string | null;
  retention_days: number;
  pii_handling: string;
  requires_attribution: boolean;
  compliance_status: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
  notes: string | null;
  metadata_: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type ComplianceDecision = {
  id: string;
  source_id: string;
  source_policy_id: string | null;
  mode: string;
  decision: string;
  reason: string;
  checks: Record<string, unknown>;
  decided_by: string;
  metadata_: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type IntelligenceObject = {
  id: string;
  object_type: string;
  title: string;
  summary: string;
  domain: string;
  language: string;
  region: string | null;
  canonical_url: string | null;
  event_id: string | null;
  cluster_id: string | null;
  normalized_document_id: string | null;
  entities: string[];
  source_document_ids: string[];
  source_count: number;
  evidence_count: number;
  mode: string;
  status: string;
  verification_status: string;
  index_credibility: number;
  index_novelty: number;
  index_impact: number;
  index_actionability: number;
  index_urgency: number;
  aggregate_score: number;
  compliance_status: string;
  metadata_: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type EvidenceLedgerEntry = {
  id: string;
  intelligence_object_id: string | null;
  event_id: string | null;
  normalized_document_id: string | null;
  source_id: string | null;
  evidence_url: string;
  title: string | null;
  source_name: string | null;
  source_type: string | null;
  quote: string | null;
  captured_at: string;
  content_hash: string | null;
  ledger_hash: string;
  citation_status: string;
  legal_use_policy: string;
  compliance_status: string;
  trust_score: number;
  relevance_score: number;
  supports_claims: string[];
  metadata_: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type EventCluster = {
  id: string;
  title: string;
  category: string;
  language: string;
  cross_language_key: string | null;
  merged_summary: string;
  source_diversity_score: number;
  confidence_score: number;
  importance_score: number;
  verification_status: string;
  metadata_: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type CrossLanguageCandidate = {
  id: string;
  cluster_id: string;
  candidate_cluster_id: string;
  source_language: string;
  target_language: string;
  similarity_score: number;
  shared_entities: string[];
  reason: string;
  status: string;
  metadata_: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};
