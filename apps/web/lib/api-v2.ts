/**
 * Typed client for the production `/api/v2/*` surface.
 *
 * Keep this isolated from the legacy `lib/api.ts` so the new product UI stays
 * small and the legacy compat routes can be retired without ripple damage.
 */

import { apiFetch } from "@/lib/api";

export type SourceKind =
  | "browser_capture"
  | "ai_answer_capture"
  | "direct_import"
  | "expert_search"
  | "enterprise_cleanse"
  | "memory_note";

export type QualityTier = "verified" | "needs_review" | "insufficient" | "rejected";

export type KnowledgeItem = {
  id: string;
  title: string;
  body: string;
  source_kind: SourceKind;
  source_url: string | null;
  created_at: string;
  updated_at: string;
  content_hash: string;
  quality_score: number;
  quality_tier: QualityTier;
  tags: string[];
  language: string;
  tenant_id: string;
  review_required: boolean;
  freshness_date: string | null;
  accuracy_score: number;
  veracity_score: number;
  relevance_score: number;
  concept_ids: string[];
  security_flags?: string[];
  content_role?: "evidence";
  snapshot_id?: string | null;
  excerpt_hash?: string | null;
};

export type EvidenceSnapshot = {
  snapshot_id: string;
  item_id?: string | null;
  title?: string | null;
  excerpt?: string | null;
  excerpt_hash?: string | null;
  source_url?: string | null;
  content_role?: "evidence" | string;
  security_flags?: string[];
  created_at?: string | null;
  metadata?: Record<string, unknown>;
};

export type LibraryStats = {
  total: number;
  verified: number;
  pending_review: number;
  insufficient: number;
  by_source: Array<{ source_kind: SourceKind; count: number }>;
  concepts: number;
  memory_notes: number;
};

export type AskResult = {
  run_id?: string | null;
  question: string;
  language: "zh-CN" | "en";
  answer: string;
  confidence: number;
  confidence_band: "solid" | "probable" | "uncertain" | "insufficient";
  thinking_model: string;
  prompt_strategy: string;
  citations: Array<{
    item_id: string;
    title: string;
    snippet: string;
    url: string | null;
    relevance: number;
    quality: number;
    security_flags?: string[];
    content_role?: "evidence";
    snapshot_id?: string | null;
    excerpt_hash?: string | null;
  }>;
  knowledge_gaps: string[];
  next_actions: string[];
  audit_id: string;
  answer_mode?: "scaffold" | "draft" | "final";
  candidate_angles?: string[];
  open_questions?: string[];
  key_tradeoffs?: string[];
  acceptance_check?: Record<string, unknown>;
};

export type MemoryNote = {
  id: string;
  text: string;
  kind: "preference" | "decision" | "journal";
  tenant_id: string;
  allow_into_knowledge_base: boolean;
  filter_reason: string;
  created_at: string;
};

export type LearnPlanItem = {
  concept_id: string;
  label: string;
  retrieved_count: number;
  item_count: number;
  gap_level: "no_knowledge" | "shallow" | "consolidate";
  recommendation: string;
};

export type Concept = {
  id: string;
  label: string;
  summary: string;
  item_ids: string[];
  neighbors: string[];
  created_at: string;
};

export type PromptOptimizeResult = {
  prompt_in: string;
  prompt_out: string;
  thinking_model: string;
  memory_lines: string[];
  audit_id: string;
};

export type AuditRow = {
  id: string;
  actor: string;
  action: string;
  subject: string | null;
  payload_json: string | null;
  created_at: string;
};

export const v2 = {
  absorb: (payload: {
    title?: string;
    body: string;
    source_kind?: SourceKind;
    source_url?: string | null;
    tags?: string[];
    freshness_date?: string | null;
    language?: string;
  }) =>
    apiFetch<KnowledgeItem>("/api/v2/absorb", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  ask: (payload: {
    question: string;
    language?: string;
    mode?: "simple" | "professional";
    model_tier?: "flagship" | "mid" | "basic" | "insufficient";
  }) =>
    apiFetch<AskResult>("/api/v2/ask", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  askScaffold: (payload: { language?: string; question?: string }) =>
    apiFetch<{ language: string; knowledge_gaps: string[]; next_actions: string[] }>(
      "/api/v2/ask/scaffold",
      undefined,
      payload as Record<string, string>,
    ),
  libraryStats: () => apiFetch<LibraryStats>("/api/v2/library/stats"),
  libraryList: (payload?: { limit?: number; offset?: number; source_kind?: SourceKind; tier?: QualityTier }) =>
    apiFetch<{ items: KnowledgeItem[] }>(
      "/api/v2/library",
      undefined,
      payload as Record<string, string | number | undefined>,
    ),
  libraryGet: (id: string) => apiFetch<KnowledgeItem>(`/api/v2/library/${id}`),
  libraryApprove: (id: string) =>
    apiFetch<KnowledgeItem>(`/api/v2/library/${id}/approve`, { method: "POST" }),
  libraryReject: (id: string, reason = "") =>
    apiFetch<KnowledgeItem>(`/api/v2/library/${id}/reject`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),
  listConcepts: (limit = 40) =>
    apiFetch<{ items: Concept[] }>("/api/v2/concepts", undefined, { limit }),
  promptOptimize: (payload: { prompt: string; language?: string; include_memory?: boolean }) =>
    apiFetch<PromptOptimizeResult>("/api/v2/prompt/optimize", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  memoryAdd: (payload: { text: string; kind?: "preference" | "decision" | "journal" }) =>
    apiFetch<MemoryNote>("/api/v2/memory", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  memoryList: (limit = 50) =>
    apiFetch<{ items: MemoryNote[] }>("/api/v2/memory", undefined, { limit }),
  learnPlan: (payload?: { language?: string; limit?: number }) =>
    apiFetch<{ items: LearnPlanItem[] }>(
      "/api/v2/learn/plan",
      undefined,
      payload as Record<string, string | number | undefined>,
    ),
  audit: (limit = 40) =>
    apiFetch<{ items: AuditRow[] }>("/api/v2/audit", undefined, { limit }),
  run: (runId: string) =>
    apiFetch<AgentRunTrace>(`/api/v2/runs/${runId}`),
  getEvidenceSnapshot: (snapshotId: string) =>
    apiFetch<EvidenceSnapshot>(`/api/v2/evidence/snapshots/${snapshotId}`),
  superviseDigest: (payload: { language?: string; snapshot?: Record<string, unknown> }) =>
    apiFetch<{
      language: "zh-CN" | "en";
      goal: string;
      single_next_action: string;
      blocked_on: string[];
      drift_alert: string;
      risk_counts: Record<string, number>;
      approvals_waiting: number;
      generated_from: string[];
    }>("/api/v2/supervise/digest", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  modelsProbe: (payload: { language?: string; provider?: string; model?: string }) =>
    apiFetch<{
      tier: "flagship" | "mid" | "basic" | "insufficient";
      aggregate_score: number;
      workflow_strategy: {
        prompt_strategy: string;
        description: string;
        planner_depth: number;
        retrieval_top_k: number;
        enable_self_consistency: boolean;
        enable_decompose_and_solve: boolean;
        quality_threshold: number;
      };
      recommendation: string;
      notes: string[];
      probes: Array<{ id: string; label: string; passed: boolean; score: number; detail: string }>;
    }>("/api/v2/models/probe", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // --- 8-layer product routes ---
  getProfile: () =>
    apiFetch<{ exists: boolean; profile?: UserProfile }>("/api/v2/profile"),
  saveProfile: (payload: {
    industry?: string;
    level?: "beginner" | "intermediate" | "independent" | "expert";
    resources?: Record<string, unknown>;
    goals?: string[];
    constraints?: string[];
    current_tasks?: string[];
    error_patterns?: string[];
  }) =>
    apiFetch<UserProfile>("/api/v2/profile", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  diagnose: (payload: { question: string; language?: string }) =>
    apiFetch<DiagnosePipeline>("/api/v2/diagnose", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  listExperiments: (limit = 20) =>
    apiFetch<{ items: Experiment[] }>("/api/v2/experiments", undefined, { limit }),
  updateExperiment: (id: string, payload: { status?: string; actual_result?: string }) =>
    apiFetch<Experiment>(`/api/v2/experiments/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  createReview: (payload: {
    experiment_id?: string | null;
    original_judgment?: string;
    actual_result?: string;
    gap?: string;
    root_cause?: "fact_wrong" | "model_wrong" | "execution_wrong" | "unknown";
    signal_for_next_time?: string;
    knowledge_card_title?: string;
    knowledge_card_body?: string;
  }) =>
    apiFetch<LearningReview>("/api/v2/reviews", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  listReviews: (limit = 20) =>
    apiFetch<{ items: LearningReview[] }>("/api/v2/reviews", undefined, { limit }),
  createDecision: (payload: {
    decision: string;
    reasoning?: string[];
    evidence?: string[];
    assumptions?: string[];
    risks?: string[];
    success_metric?: string;
    review_date?: string;
  }) =>
    apiFetch<DecisionLog>("/api/v2/decisions", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  evalDashboard: () =>
    apiFetch<{
      metrics: Array<{
        id: string;
        label_zh: string;
        label_en: string;
        value: number;
        sample_size: number;
        description_zh: string;
        description_en: string;
        tier: "green" | "amber" | "red" | "unknown";
      }>;
    }>("/api/v2/eval/dashboard"),
  listDecisions: (limit = 20) =>
    apiFetch<{ items: DecisionLog[] }>("/api/v2/decisions", undefined, { limit }),

  // --- Model Registry ---
  modelProviders: () =>
    apiFetch<{ providers: Array<{ id: string; label: string; base_url_hint: string; models_hint: string }> }>("/api/v2/models/providers"),
  modelConfigs: () =>
    apiFetch<{
      slots: Array<ModelSlotConfig>;
      available_slots: string[];
    }>("/api/v2/models/config"),
  saveModelConfig: (payload: {
    slot: string;
    provider_id: string;
    base_url: string;
    api_key?: string;
    model_name: string;
    enabled?: boolean;
    display_label?: string;
  }) =>
    apiFetch<ModelSlotConfig>("/api/v2/models/config", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  deleteModelConfig: (slot: string) =>
    apiFetch<{ deleted: string }>(`/api/v2/models/config/${slot}`, { method: "DELETE" }),
  testModelConfig: (slot: string) =>
    apiFetch<{ ok: boolean; error?: string; error_type?: string; health_status?: string; response?: string; model?: string; provider?: string }>(
      `/api/v2/models/config/${slot}/test`,
      { method: "POST" },
    ),
};

// ---------- 8-layer product types ----------

export type UserProfile = {
  id: string;
  tenant_id: string;
  industry: string;
  level: "beginner" | "intermediate" | "independent" | "expert";
  resources: Record<string, unknown>;
  goals: string[];
  constraints: string[];
  current_tasks: string[];
  decision_history: Array<Record<string, unknown>>;
  error_patterns: string[];
  created_at: string;
  updated_at: string;
};

export type Diagnosis = {
  id: string;
  tenant_id: string;
  surface_question: string;
  real_question: string;
  problem_type: string;
  key_variables: string[];
  evidence_status: Array<{ type: string; content: string; status: string }>;
  subjective_judgments: string[];
  needs_external_verification: string[];
  common_failure_reasons: string[];
  expert_first_look: string;
  minimum_verifiable_action: string;
  thinking_models_used: string[];
  created_at: string;
};

export type Experiment = {
  id: string;
  tenant_id: string;
  hypothesis: string;
  experiment: string;
  cost: { time?: string; money?: string; effort?: string };
  success_metric: string;
  failure_signal: string;
  review_date: string;
  next_if_success: string;
  next_if_failure: string;
  status: "planned" | "running" | "succeeded" | "failed" | "abandoned";
  actual_result: string;
  created_at: string;
  updated_at: string;
};

export type LearningReview = {
  id: string;
  tenant_id: string;
  experiment_id: string | null;
  original_judgment: string;
  actual_result: string;
  gap: string;
  root_cause: "fact_wrong" | "model_wrong" | "execution_wrong" | "unknown";
  signal_for_next_time: string;
  knowledge_card_title: string;
  knowledge_card_body: string;
  created_at: string;
};

export type DecisionLog = {
  id: string;
  tenant_id: string;
  decision: string;
  reasoning: string[];
  evidence: string[];
  assumptions: string[];
  risks: string[];
  success_metric: string;
  review_date: string;
  status: "active" | "succeeded" | "failed" | "revised";
  created_at: string;
};

export type DiagnosePipeline = {
  run_id?: string;
  diagnosis: Diagnosis;
  experiment: Experiment;
  review_template: LearningReview;
};

export type AgentRunTrace = {
  run: {
    run_id: string;
    tenant_id: string;
    user_id: string;
    entrypoint: string;
    status: string;
    input_hash?: string | null;
    output_hash?: string | null;
    started_at: string;
    ended_at?: string | null;
    error?: string | null;
    metadata?: Record<string, unknown>;
  };
  steps: Array<Record<string, unknown>>;
  model_calls: Array<Record<string, unknown>>;
  acceptance_checks: Array<Record<string, unknown>>;
  audit_results: Array<Record<string, unknown>>;
};

export type ModelSlotConfig = {
  slot: string;
  provider_id: string;
  base_url: string;
  api_key_configured: boolean;
  api_key_preview: string;
  model_name: string;
  enabled: boolean;
  display_label: string;
};
