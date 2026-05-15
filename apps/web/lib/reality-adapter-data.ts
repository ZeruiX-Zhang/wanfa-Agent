import { api, apiFetch } from "@/lib/api";
import type { EvidenceLedgerEntry, IntelligenceObject, Job, Settings, Source } from "@/lib/types";

export type AdapterMode = "connected" | "partial" | "mock-safe" | "empty" | "blocked";

export type AdapterStatus = {
  name: string;
  mode: AdapterMode;
  detail: string;
};

export type KnowledgeSourceRow = {
  id: string;
  name: string;
  type: string;
  category: string;
  trustScore: number;
  enabled: boolean;
  complianceStatus: string;
  collectionMode: string;
  lastStatus: string;
  url: string | null;
};

export type EvidenceRow = {
  id: string;
  title: string;
  sourceName: string;
  url: string;
  quote: string;
  trustScore: number;
  relevanceScore: number;
  complianceStatus: string;
  legalUsePolicy: string;
  ledgerHash: string;
  capturedAt: string;
  supportsClaims: string[];
};

export type IntelligenceObjectRow = {
  id: string;
  title: string;
  summary: string;
  domain: string;
  status: string;
  verificationStatus: string;
  sourceCount: number;
  evidenceCount: number;
  aggregateScore: number;
  mode: string;
  complianceStatus: string;
};

export type SettingsSummary = {
  llmProvider: string;
  searchProvider: string;
  configuredServerKeys: number;
  missingServerKeys: number;
  serverOnly: true;
};

export type PendingKnowledgeWrite = {
  id: string;
  title: string;
  domain: string;
  source: string;
  summary: string;
  status: "pending_review" | "undo_requested";
  createdAt: string;
  undoAvailable: boolean;
};

export type SouSurface = {
  mode: AdapterMode;
  statuses: AdapterStatus[];
  sources: KnowledgeSourceRow[];
  evidence: EvidenceRow[];
  intelligenceObjects: IntelligenceObjectRow[];
  settings: SettingsSummary;
  pendingWrites: PendingKnowledgeWrite[];
};

export type RetrievalTraceStep = {
  id: string;
  stage: string;
  status: string;
  detail: string;
  dryRun: boolean;
};

export type SearchSurface = {
  mode: AdapterMode;
  query: string;
  results: IntelligenceObjectRow[];
  evidence: EvidenceRow[];
  trace: RetrievalTraceStep[];
  evalSummary: {
    status: string;
    precision: number;
    recall: number;
    notes: string;
  };
};

export type ClarificationQuestion = {
  id: string;
  question: string;
  required: boolean;
};

export type CaptureSummary = {
  mode: AdapterMode;
  entryPoints: Array<{
    id: string;
    label: string;
    status: string;
    detail: string;
  }>;
  clarificationQuestions: ClarificationQuestion[];
  knowledgeOsSummary: {
    status: string;
    domains: string[];
    pendingReviewRequired: true;
  };
};

export type DecisionCase = {
  id: string;
  mode: AdapterMode;
  decisionCase: {
    title: string;
    rawInput: string;
    status: string;
  };
  clarifiedProblem: {
    question: string;
    scope: string;
    assumptions: string[];
  };
  memo: {
    recommendation: string;
    confidence: number;
    insufficientEvidence: boolean;
    evidence: EvidenceRow[];
    counterarguments: string[];
    risks: string[];
    status: string;
  };
};

export type VerificationSurface = {
  id: string;
  mode: AdapterMode;
  claim: {
    text: string;
    status: string;
    confidence: number;
    insufficientEvidence: boolean;
  };
  evidence: EvidenceRow[];
  evalSummary: {
    status: string;
    passRate: number;
    failingChecks: string[];
  };
  trace: RetrievalTraceStep[];
};

export type SupervisorSurface = {
  mode: AdapterMode;
  workflow: {
    id: string;
    name: string;
    status: string;
  };
  agentTasks: Array<{
    id: string;
    title: string;
    status: string;
    risk: "low" | "medium" | "high";
    dryRun: boolean;
  }>;
  steps: Array<{
    id: string;
    taskId: string;
    label: string;
    status: string;
  }>;
  toolCalls: Array<{
    id: string;
    tool: string;
    status: string;
    dryRun: boolean;
    reason: string;
  }>;
  approvalRequests: Array<{
    id: string;
    action: string;
    risk: "low" | "medium" | "high";
    status: string;
    required: boolean;
  }>;
  logs: string[];
};

type SafeResult<T> = { ok: true; value: T } | { ok: false; error: string };

const MOCK_DATE = "2026-05-12T00:00:00.000Z";

const MOCK_SOURCES: KnowledgeSourceRow[] = [
  {
    id: "mock-source-sou-1",
    name: "SOu Source Registry",
    type: "adapter",
    category: "knowledge_search",
    trustScore: 0.72,
    enabled: true,
    complianceStatus: "approved_limited",
    collectionMode: "read_only",
    lastStatus: "mock_safe",
    url: null,
  },
  {
    id: "mock-source-work-1",
    name: "Work RAG Debug Index",
    type: "adapter",
    category: "verification",
    trustScore: 0.68,
    enabled: true,
    complianceStatus: "unreviewed",
    collectionMode: "read_only",
    lastStatus: "mock_safe",
    url: null,
  },
];

const MOCK_EVIDENCE: EvidenceRow[] = [
  {
    id: "mock-evidence-1",
    title: "Evidence ledger placeholder",
    sourceName: "sou.evidence-ledger",
    url: "about:blank",
    quote: "Mock-safe evidence row. Replace with backend adapter evidence before treating this as verified.",
    trustScore: 0.64,
    relevanceScore: 0.58,
    complianceStatus: "unreviewed",
    legalUsePolicy: "untrusted_external_content",
    ledgerHash: "mock-ledger-hash",
    capturedAt: MOCK_DATE,
    supportsClaims: ["Adapter surfaces must separate evidence from generated claims."],
  },
  {
    id: "mock-evidence-2",
    title: "Verification trace placeholder",
    sourceName: "work.verification",
    url: "about:blank",
    quote: "Mock-safe trace row. Tool execution remains disabled and dry-run in the web UI.",
    trustScore: 0.61,
    relevanceScore: 0.52,
    complianceStatus: "needs_review",
    legalUsePolicy: "pending_review_only",
    ledgerHash: "mock-trace-hash",
    capturedAt: MOCK_DATE,
    supportsClaims: ["High-risk actions require supervisor approval."],
  },
];

const MOCK_OBJECTS: IntelligenceObjectRow[] = [
  {
    id: "mock-io-1",
    title: "Unified knowledge adapter surface",
    summary: "Read-only SOu sources, evidence ledger rows, and intelligence objects are visible before formal knowledge writes.",
    domain: "knowledge",
    status: "mock_safe",
    verificationStatus: "needs_human_review",
    sourceCount: 2,
    evidenceCount: 2,
    aggregateScore: 0.62,
    mode: "adapter",
    complianceStatus: "unreviewed",
  },
  {
    id: "mock-io-2",
    title: "Decision memo closure slice",
    summary: "Clarification, retrieval, memo, verification, pending knowledge, and supervisor approval are represented as one UI flow.",
    domain: "decision",
    status: "mock_safe",
    verificationStatus: "unverified",
    sourceCount: 1,
    evidenceCount: 1,
    aggregateScore: 0.56,
    mode: "dry_run",
    complianceStatus: "needs_review",
  },
];

const MOCK_PENDING_WRITES: PendingKnowledgeWrite[] = [
  {
    id: "pending-reflection-1",
    title: "Decision review lesson",
    domain: "reflection",
    source: "ReflectionRecord",
    summary: "Captured learning is staged for human review and is not written to the formal knowledge base.",
    status: "pending_review",
    createdAt: MOCK_DATE,
    undoAvailable: true,
  },
  {
    id: "pending-knowledge-1",
    title: "Adapter evidence handling policy",
    domain: "knowledge",
    source: "Knowledge OS capture",
    summary: "External webpages and files remain untrusted until reviewed, cited, and approved.",
    status: "pending_review",
    createdAt: MOCK_DATE,
    undoAvailable: true,
  },
];

const MOCK_SETTINGS: SettingsSummary = {
  llmProvider: "server-configured",
  searchProvider: "server-configured",
  configuredServerKeys: 0,
  missingServerKeys: 0,
  serverOnly: true,
};

function strictAdapterMode() {
  const mode = process.env.REALITY_OS_ADAPTER_MODE ?? process.env.NEXT_PUBLIC_REALITY_OS_ADAPTER_MODE;
  return mode?.toLowerCase() === "production" || mode?.toLowerCase() === "strict";
}

async function safe<T>(loader: () => Promise<T>): Promise<SafeResult<T>> {
  try {
    return { ok: true, value: await loader() };
  } catch (error) {
    return {
      ok: false,
      error: error instanceof Error ? error.message : "Adapter request failed",
    };
  }
}

function modeFromResults(results: Array<SafeResult<unknown>>): AdapterMode {
  const successCount = results.filter((result) => result.ok).length;
  if (successCount === results.length) return "connected";
  if (successCount > 0) return "partial";
  return strictAdapterMode() ? "blocked" : "mock-safe";
}

function statusFor(name: string, result: SafeResult<unknown>, fallback: string): AdapterStatus {
  return result.ok
    ? { name, mode: "connected", detail: "Backend adapter data loaded." }
    : strictAdapterMode()
      ? { name, mode: "blocked", detail: `Backend adapter unavailable; strict mode blocks mock fallback: ${result.error}` }
    : { name, mode: "mock-safe", detail: `${fallback}: ${result.error}` };
}

function mapSource(source: Source): KnowledgeSourceRow {
  return {
    id: source.id,
    name: source.name,
    type: source.type,
    category: source.category,
    trustScore: source.trust_score,
    enabled: source.enabled,
    complianceStatus: source.compliance_status,
    collectionMode: source.collection_mode,
    lastStatus: source.last_status ?? (source.enabled ? "enabled" : "disabled"),
    url: source.url,
  };
}

function mapEvidence(entry: EvidenceLedgerEntry): EvidenceRow {
  return {
    id: entry.id,
    title: entry.title ?? entry.evidence_url,
    sourceName: entry.source_name ?? entry.source_type ?? "source n/a",
    url: entry.evidence_url,
    quote: entry.quote ?? "No quote captured.",
    trustScore: entry.trust_score,
    relevanceScore: entry.relevance_score,
    complianceStatus: entry.compliance_status,
    legalUsePolicy: entry.legal_use_policy,
    ledgerHash: entry.ledger_hash,
    capturedAt: entry.captured_at,
    supportsClaims: entry.supports_claims,
  };
}

function mapIntelligenceObject(item: IntelligenceObject): IntelligenceObjectRow {
  return {
    id: item.id,
    title: item.title,
    summary: item.summary,
    domain: item.domain,
    status: item.status,
    verificationStatus: item.verification_status,
    sourceCount: item.source_count,
    evidenceCount: item.evidence_count,
    aggregateScore: item.aggregate_score,
    mode: item.mode,
    complianceStatus: item.compliance_status,
  };
}

function mapSettings(settings: Settings): SettingsSummary {
  const keyStates = Object.values(settings.api_key_status);
  return {
    llmProvider: settings.llm_provider,
    searchProvider: settings.search_provider,
    configuredServerKeys: keyStates.filter(Boolean).length,
    missingServerKeys: keyStates.filter((configured) => !configured).length,
    serverOnly: true,
  };
}

function filterRows<T extends { title: string; summary?: string }>(rows: T[], query: string) {
  const normalized = query.trim().toLowerCase();
  if (!normalized) return rows;
  return rows.filter((row) => `${row.title} ${row.summary ?? ""}`.toLowerCase().includes(normalized));
}

function buildTrace(mode: AdapterMode): RetrievalTraceStep[] {
  return [
    {
      id: "trace-clarification",
      stage: "clarification",
      status: "ready",
      detail: "Problem framing is captured before retrieval.",
      dryRun: true,
    },
    {
      id: "trace-retrieval",
      stage: "retrieval",
      status: mode === "connected" ? "connected" : "mock_safe",
      detail: "Hybrid retrieval/debug trace is shown without executing external tools from the browser.",
      dryRun: true,
    },
    {
      id: "trace-verification",
      stage: "verification",
      status: "requires_evidence",
      detail: "Claims without bound evidence remain insufficient evidence.",
      dryRun: true,
    },
  ];
}

export async function getSouSurface(): Promise<SouSurface> {
  const [sources, evidence, objects, settings] = await Promise.all([
    safe(() => api.sources({ limit: 100 })),
    safe(() => api.evidenceLedger({ limit: 100 })),
    safe(() => api.intelligenceObjects({ limit: 100 })),
    safe(() => api.settings()),
  ]);

  const mode = modeFromResults([sources, evidence, objects, settings]);
  const strict = strictAdapterMode();
  return {
    mode,
    statuses: [
      statusFor("sources", sources, "Using read-only source mock-safe rows"),
      statusFor("evidence-ledger", evidence, "Using evidence ledger mock-safe rows"),
      statusFor("intelligence-objects", objects, "Using intelligence object mock-safe rows"),
      statusFor("settings", settings, "Using server-only settings summary"),
    ],
    sources: sources.ok ? sources.value.items.map(mapSource) : strict ? [] : MOCK_SOURCES,
    evidence: evidence.ok ? evidence.value.items.map(mapEvidence) : strict ? [] : MOCK_EVIDENCE,
    intelligenceObjects: objects.ok ? objects.value.items.map(mapIntelligenceObject) : strict ? [] : MOCK_OBJECTS,
    settings: settings.ok ? mapSettings(settings.value) : MOCK_SETTINGS,
    pendingWrites: strict ? [] : MOCK_PENDING_WRITES,
  };
}

export async function getDashboardSurface() {
  const [sou, dashboard, jobs] = await Promise.all([
    getSouSurface(),
    safe(() => api.dashboard()),
    safe(() => api.jobs({ limit: 10 })),
  ]);
  const jobItems: Job[] = jobs.ok ? jobs.value.items : [];
  const verifiedObjects = sou.intelligenceObjects.filter((item) => item.verificationStatus === "verified").length;
  return {
    mode: modeFromResults([{ ok: true, value: sou }, dashboard, jobs]),
    sou,
    metrics: {
      sources: sou.sources.length,
      evidence: sou.evidence.length,
      intelligenceObjects: sou.intelligenceObjects.length,
      pendingWrites: sou.pendingWrites.filter((item) => item.status === "pending_review").length,
      verifiedObjects,
      dryRunTasks: 1,
      backendEventsToday: dashboard.ok ? dashboard.value.total_events_today : null,
      backendJobs: jobItems.length,
    },
    recentActivity: [
      ...sou.intelligenceObjects.slice(0, 3).map((item) => ({
        id: item.id,
        label: item.title,
        status: item.verificationStatus,
        detail: item.summary,
      })),
      ...jobItems.slice(0, 2).map((job) => ({
        id: job.id,
        label: job.name,
        status: job.status,
        detail: `${job.type} / ${job.mode}`,
      })),
    ],
  };
}

export async function getSearchSurface(query: string): Promise<SearchSurface> {
  const sou = await getSouSurface();
  const results = filterRows(sou.intelligenceObjects, query);
  const evidence = filterRows(
    sou.evidence.map((row) => ({ ...row, summary: row.quote })),
    query,
  );
  return {
    mode: sou.mode,
    query,
    results,
    evidence,
    trace: buildTrace(sou.mode),
    evalSummary: {
      status: results.length > 0 || evidence.length > 0 ? "retrieved" : "empty",
      precision: results.length > 0 ? 0.72 : 0,
      recall: evidence.length > 0 ? 0.61 : 0,
      notes: "Search UI surfaces adapter data only; browser-side tool execution is disabled.",
    },
  };
}

export async function getCaptureSummary(): Promise<CaptureSummary> {
  const adapter = await safe(() => apiFetch<CaptureSummary>("/api/prompt/capture-summary"));
  if (adapter.ok) return adapter.value;
  if (strictAdapterMode()) {
    return {
      mode: "blocked",
      entryPoints: [],
      clarificationQuestions: [],
      knowledgeOsSummary: {
        status: "backend_required",
        domains: [],
        pendingReviewRequired: true,
      },
    };
  }
  return {
    mode: "mock-safe",
    entryPoints: [
      {
        id: "text",
        label: "Text",
        status: "ready",
        detail: "Captured locally for clarification; no formal knowledge write.",
      },
      {
        id: "webpage",
        label: "Webpage",
        status: "untrusted",
        detail: "External URLs are treated as untrusted until reviewed.",
      },
      {
        id: "extension",
        label: "Browser extension",
        status: "input_only",
        detail: "Lightweight capture entry; complex business logic remains server-side.",
      },
    ],
    clarificationQuestions: [
      { id: "goal", question: "What decision or judgment do you need to make?", required: true },
      { id: "scope", question: "What sources, time range, or tenant boundary should retrieval use?", required: true },
      { id: "risk", question: "What would make an answer unacceptable or unsafe?", required: false },
    ],
    knowledgeOsSummary: {
      status: "pending_review_only",
      domains: ["personal", "industry", "enterprise", "study"],
      pendingReviewRequired: true,
    },
  };
}

export async function getDecisionCase(id: string): Promise<DecisionCase> {
  const sou = await getSouSurface();
  const evidence = id.includes("empty") ? [] : sou.evidence.slice(0, 3);
  const insufficientEvidence = evidence.length === 0;
  return {
    id,
    mode: sou.mode,
    decisionCase: {
      title: `Decision case ${id}`,
      rawInput: "Should Reality OS promote this retrieved signal into a decision memo and pending knowledge write?",
      status: "draft",
    },
    clarifiedProblem: {
      question: "What evidence-backed decision can be made without writing unreviewed generated content into formal knowledge?",
      scope: "SOu evidence ledger, work verification trace, prompt clarification summary, tenant-local context only.",
      assumptions: [
        "Legacy projects remain independently runnable.",
        "External files and webpages are untrusted until reviewed.",
        "API keys are stored server-side and never rendered in the frontend.",
      ],
    },
    memo: {
      recommendation: insufficientEvidence
        ? "Do not decide yet. Gather reviewed evidence first."
        : "Proceed with a draft memo only, keep generated knowledge pending review, and require supervisor approval for high-risk actions.",
      confidence: insufficientEvidence ? 0.18 : 0.64,
      insufficientEvidence,
      evidence,
      counterarguments: [
        "Mock-safe adapter data can prove UI wiring but cannot verify real-world truth.",
        "A connected backend may still return stale or low-trust evidence.",
      ],
      risks: [
        "Treating generated summaries as source facts.",
        "Approving high-risk tool calls from the browser instead of the supervisor gate.",
        "Accidentally promoting ReflectionRecord content into formal knowledge before review.",
      ],
      status: insufficientEvidence ? "insufficient_evidence" : "draft_pending_review",
    },
  };
}

export async function getVerificationSurface(id: string): Promise<VerificationSurface> {
  const sou = await getSouSurface();
  const evidence = id.includes("empty") ? [] : sou.evidence.slice(0, 3);
  const insufficientEvidence = evidence.length === 0;
  return {
    id,
    mode: sou.mode,
    claim: {
      text: "High-risk tool execution requires explicit supervisor approval and remains dry-run by default.",
      status: insufficientEvidence ? "insufficient_evidence" : "needs_human_review",
      confidence: insufficientEvidence ? 0.12 : 0.67,
      insufficientEvidence,
    },
    evidence,
    evalSummary: {
      status: insufficientEvidence ? "blocked" : "mock_safe_eval",
      passRate: insufficientEvidence ? 0 : 0.7,
      failingChecks: insufficientEvidence ? ["no_bound_evidence"] : ["human_review_required"],
    },
    trace: buildTrace(sou.mode),
  };
}

export async function getReflectionSurface() {
  const sou = await getSouSurface();
  return {
    mode: sou.mode,
    pendingWrites: sou.pendingWrites,
    records: [
      {
        id: "reflection-record-1",
        title: "Decision memo review",
        status: "pending_review",
        detail: "ReflectionRecord is staged and not inserted into formal knowledge.",
      },
      {
        id: "reflection-record-2",
        title: "User outcome feedback",
        status: "capture_ready",
        detail: "Outcome feedback can be attached to the decision case after human review.",
      },
    ],
  };
}

export async function getSupervisorSurface(): Promise<SupervisorSurface> {
  const adapter = await safe(() => apiFetch<SupervisorSurface>("/api/work/supervisor"));
  if (adapter.ok) return adapter.value;
  if (strictAdapterMode()) {
    return {
      mode: "blocked",
      workflow: {
        id: "workflow-blocked",
        name: "Backend supervisor required",
        status: "backend_required",
      },
      agentTasks: [],
      steps: [],
      toolCalls: [],
      approvalRequests: [],
      logs: ["Strict adapter mode is enabled; mock supervisor fallback is blocked."],
    };
  }
  return {
    mode: "mock-safe",
    workflow: {
      id: "workflow-phase-9",
      name: "Judgment memo acceptance flow",
      status: "dry_run_disabled_tools",
    },
    agentTasks: [
      {
        id: "task-worker-2",
        title: "Render web adapter data surfaces",
        status: "in_review",
        risk: "medium",
        dryRun: true,
      },
      {
        id: "task-high-risk-tool",
        title: "Potential filesystem or network tool execution",
        status: "approval_required",
        risk: "high",
        dryRun: true,
      },
    ],
    steps: [
      { id: "step-plan", taskId: "task-worker-2", label: "Plan", status: "complete" },
      { id: "step-diff", taskId: "task-worker-2", label: "Diff placeholder", status: "pending_review" },
      { id: "step-test", taskId: "task-worker-2", label: "Test placeholder", status: "pending_review" },
    ],
    toolCalls: [
      {
        id: "tool-search",
        tool: "retrieval.query",
        status: "dry_run",
        dryRun: true,
        reason: "Browser UI can request adapter data but cannot execute privileged tools.",
      },
      {
        id: "tool-write",
        tool: "knowledge.write",
        status: "disabled",
        dryRun: true,
        reason: "All generated knowledge writes default to pending review.",
      },
    ],
    approvalRequests: [
      {
        id: "approval-high-risk",
        action: "Run high-risk external tool",
        risk: "high",
        status: "waiting_for_human",
        required: true,
      },
    ],
    logs: [
      "Tool gateway default: disabled/dry-run.",
      "High-risk actions require approval before execution.",
      "Diff and test artifacts are represented as review placeholders.",
    ],
  };
}
