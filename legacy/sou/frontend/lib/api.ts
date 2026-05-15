import type {
  DashboardOverview,
  Event,
  EventCluster,
  EventDetail,
  EvidenceLedgerEntry,
  ComplianceDecision,
  CrossLanguageCandidate,
  IntelligenceObject,
  Job,
  JobDetail,
  Page,
  ProductReview,
  ProductReviewDetail,
  Report,
  ReportDetail,
  Settings,
  Source,
  SourcePolicy,
  Watchlist,
} from "@/lib/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type Query = Record<string, string | number | boolean | null | undefined>;

function buildUrl(path: string, query?: Query) {
  const url = new URL(path, API_BASE_URL);
  Object.entries(query ?? {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(key, String(value));
    }
  });
  return url.toString();
}

export async function apiFetch<T>(path: string, init?: RequestInit, query?: Query): Promise<T> {
  const response = await fetch(buildUrl(path, query), {
    ...init,
    headers: {
      "content-type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = (await response.json()) as { detail?: string };
      detail = body.detail ?? detail;
    } catch {
      detail = response.statusText;
    }
    throw new Error(detail);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export const api = {
  dashboard: () => apiFetch<DashboardOverview>("/api/dashboard"),
  sources: (query?: Query) => apiFetch<Page<Source>>("/api/sources", undefined, query),
  createSource: (payload: Record<string, unknown>) =>
    apiFetch<Source>("/api/sources", { method: "POST", body: JSON.stringify(payload) }),
  patchSource: (id: string, payload: Record<string, unknown>) =>
    apiFetch<Source>(`/api/sources/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteSource: (id: string) => apiFetch<void>(`/api/sources/${id}`, { method: "DELETE" }),
  sourcePolicies: (query?: Query) => apiFetch<Page<SourcePolicy>>("/api/source-policies", undefined, query),
  sourcePolicy: (id: string) => apiFetch<SourcePolicy>(`/api/sources/${id}/policy`),
  patchSourcePolicy: (id: string, payload: Record<string, unknown>) =>
    apiFetch<SourcePolicy>(`/api/sources/${id}/policy`, { method: "PATCH", body: JSON.stringify(payload) }),
  evaluateSourceCompliance: (id: string, payload: { mode?: "speed" | "verified"; decided_by?: string }) =>
    apiFetch<ComplianceDecision>(`/api/sources/${id}/compliance/evaluate`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  complianceDecisions: (query?: Query) => apiFetch<Page<ComplianceDecision>>("/api/compliance-decisions", undefined, query),
  events: (query?: Query) => apiFetch<Page<Event>>("/api/events", undefined, query),
  event: (id: string) => apiFetch<EventDetail>(`/api/events/${id}`),
  intelligenceObjects: (query?: Query) => apiFetch<Page<IntelligenceObject>>("/api/intelligence-objects", undefined, query),
  syncIntelligenceObjects: (mode: "speed" | "verified" = "speed") =>
    apiFetch<IntelligenceObject[]>("/api/intelligence-objects/sync", { method: "POST" }, { mode }),
  intelligenceObject: (id: string) => apiFetch<IntelligenceObject & { ledger_entries: EvidenceLedgerEntry[] }>(`/api/intelligence-objects/${id}`),
  evidenceLedger: (query?: Query) => apiFetch<Page<EvidenceLedgerEntry>>("/api/evidence-ledger", undefined, query),
  clusters: (query?: Query) => apiFetch<Page<EventCluster>>("/api/clusters", undefined, query),
  crossLanguageCandidates: (query?: Query) =>
    apiFetch<Page<CrossLanguageCandidate>>("/api/cross-language-candidates", undefined, query),
  reports: (query?: Query) => apiFetch<Page<Report>>("/api/reports", undefined, query),
  report: (id: string) => apiFetch<ReportDetail>(`/api/reports/${id}`),
  generateReport: (payload: Record<string, unknown> = {}) =>
    apiFetch<ReportDetail>("/api/reports/generate", { method: "POST", body: JSON.stringify(payload) }),
  watchlists: (query?: Query) => apiFetch<Page<Watchlist>>("/api/watchlists", undefined, query),
  createWatchlist: (payload: Record<string, unknown>) =>
    apiFetch<Watchlist>("/api/watchlists", { method: "POST", body: JSON.stringify(payload) }),
  patchWatchlist: (id: string, payload: Record<string, unknown>) =>
    apiFetch<Watchlist>(`/api/watchlists/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteWatchlist: (id: string) => apiFetch<void>(`/api/watchlists/${id}`, { method: "DELETE" }),
  jobs: (query?: Query) => apiFetch<Page<Job>>("/api/jobs", undefined, query),
  job: (id: string) => apiFetch<JobDetail>(`/api/jobs/${id}`),
  createJob: (payload: Record<string, unknown>) => apiFetch<JobDetail>("/api/jobs", { method: "POST", body: JSON.stringify(payload) }),
  runJob: (id: string) => apiFetch<JobDetail>(`/api/jobs/${id}/run`, { method: "POST" }),
  runDaily: (mode: "speed" | "verified" = "verified") => apiFetch<JobDetail>("/api/jobs/run-daily", { method: "POST" }, { mode }),
  productReviews: (query?: Query) =>
    apiFetch<Page<ProductReview>>("/api/product-reviews", undefined, query),
  productReview: (id: string) => apiFetch<ProductReviewDetail>(`/api/product-reviews/${id}`),
  createProductReview: (payload: {
    product_name: string;
    official_url?: string;
    competitors: string[];
    target_users: string[];
  }) => apiFetch<ProductReviewDetail>("/api/product-reviews", { method: "POST", body: JSON.stringify(payload) }),
  settings: () => apiFetch<Settings>("/api/settings"),
  patchSettings: (payload: Record<string, unknown>) =>
    apiFetch<Settings>("/api/settings", { method: "PATCH", body: JSON.stringify(payload) }),
};
