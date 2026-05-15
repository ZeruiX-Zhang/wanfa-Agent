import type { Event, EventDetail, Job, ProductReview, Source, Watchlist } from "@/lib/types";
import { unique } from "@/lib/utils";

export type SignalKind = "fact" | "trend";
export type ComplianceState = "pass" | "warn" | "fail";

const LANGUAGE_KEYS = [
  "language",
  "languages",
  "source_language",
  "source_languages",
  "candidate_languages",
  "cross_language_candidates",
];

const SOURCE_COUNT_KEYS = ["source_count", "sources_count", "source_diversity", "source_diversity_score"];
const FAILURE_KEYS = ["failure_reason", "error", "last_error", "exception", "connector_error"];

export function getString(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

export function getNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

export function getStringList(value: unknown): string[] {
  if (typeof value === "string") {
    return value
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
  }
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => getString(item))
    .filter((item): item is string => item !== null);
}

export function metadataStrings(metadata: Record<string, unknown>, keys: string[]) {
  return unique(keys.flatMap((key) => getStringList(metadata[key])));
}

export function metadataNumber(metadata: Record<string, unknown>, keys: string[]) {
  for (const key of keys) {
    const value = getNumber(metadata[key]);
    if (value !== null) return value;
  }
  return null;
}

export function firstMetadataString(metadata: Record<string, unknown>, keys: string[]) {
  for (const key of keys) {
    const value = getString(metadata[key]);
    if (value) return value;
  }
  return null;
}

export function isEventDetail(event: Event | EventDetail): event is EventDetail {
  return "evidence" in event && Array.isArray(event.evidence);
}

export function evidenceCount(event: Event | EventDetail) {
  return isEventDetail(event) ? event.evidence.length : 0;
}

export function sourceCount(event: Event | EventDetail) {
  if (isEventDetail(event)) {
    const sources = event.evidence
      .map((item) => item.source_name ?? item.evidence_url)
      .filter((item): item is string => Boolean(item));
    return unique(sources).length;
  }
  return Math.max(0, Math.round(metadataNumber(event.metadata_, SOURCE_COUNT_KEYS) ?? 0));
}

export function signalKind(event: Event | EventDetail): SignalKind {
  const sources = sourceCount(event);
  const verified = event.verification_status === "verified" || event.verification_status === "partially_verified";
  if (verified && event.confidence >= 0.72 && (sources >= 2 || event.confidence >= 0.86)) return "fact";
  return "trend";
}

export function verificationLabel(status: string) {
  return status.replaceAll("_", " ");
}

export function statusTone(status: string): "good" | "warn" | "bad" | "neutral" {
  const normalized = status.toLowerCase();
  if (["verified", "completed", "success", "ok", "pass", "enabled", "configured", "approved", "allow", "captured"].includes(normalized)) {
    return "good";
  }
  if (
    [
      "partially_verified",
      "queued",
      "running",
      "needs_human_review",
      "unverified",
      "missing",
      "approved_limited",
      "allow_limited",
      "unreviewed",
      "needs_review",
    ].includes(normalized)
  ) {
    return "warn";
  }
  if (["failed", "low_quality", "conflicting", "disabled", "error", "blocked", "disallowed", "takedown_required"].includes(normalized)) {
    return "bad";
  }
  return "neutral";
}

export function eventLanguages(event: Event | EventDetail, sources: Source[] = []) {
  const fromMetadata = metadataStrings(event.metadata_, LANGUAGE_KEYS);
  if (fromMetadata.length > 0) return fromMetadata;

  const categorySources = sources.filter((source) => source.enabled && source.category === event.category);
  const sourceLanguages = unique(categorySources.map((source) => source.language).filter(Boolean));
  if (sourceLanguages.length > 0) return sourceLanguages;

  return /[\u4e00-\u9fff]/.test(event.title + event.summary) ? ["zh"] : ["en"];
}

export function crossLanguageCandidates(events: Array<Event | EventDetail>, sources: Source[]) {
  return events.filter((event) => eventLanguages(event, sources).length > 1);
}

export function categoryLabel(category: string) {
  return category.replaceAll("_", " ");
}

export function sourceCategoryMatches(source: Source, category: string) {
  if (source.category === category) return true;
  const sourceCategory = source.category.toLowerCase();
  const eventCategory = category.toLowerCase();
  return eventCategory.split("_").some((part) => part.length > 3 && sourceCategory.includes(part));
}

export function sourcesForCategory(sources: Source[], category: string) {
  return sources.filter((source) => sourceCategoryMatches(source, category));
}

export function complianceForSource(source: Source): { state: ComplianceState; reason: string } {
  if (!source.enabled) return { state: "warn", reason: "Source is disabled" };
  if (["blocked", "disallowed", "takedown_required"].includes(source.compliance_status)) {
    return { state: "fail", reason: `Source policy is ${source.compliance_status}` };
  }
  if (source.last_error) return { state: "fail", reason: source.last_error };
  if (source.trust_score < 0.45) return { state: "warn", reason: "Trust score is below precision threshold" };
  if (source.last_status === "connector_unconfigured") return { state: "warn", reason: "Connector key is not configured" };
  if (source.compliance_status === "approved_limited" || source.compliance_status === "unreviewed") {
    return { state: "warn", reason: `Limited use: ${source.legal_use_policy}` };
  }
  return { state: "pass", reason: "Source passes current legal and collection guardrails" };
}

export function complianceForSettings(apiKeyStatus: Record<string, boolean>) {
  return Object.entries(apiKeyStatus).map(([provider, configured]) => ({
    provider,
    state: configured ? "pass" : ("warn" as ComplianceState),
    reason: configured ? "Key present in environment" : "Key missing; connector will be skipped or mocked",
  }));
}

export function jobFailureReason(job: Job) {
  const metadataReason = firstMetadataString(job.metadata_, FAILURE_KEYS);
  if (metadataReason) return metadataReason;
  if (job.failure_count > 0) return `${job.failure_count} failed stage(s); select the job to inspect logs`;
  if (job.status === "failed") return "Job failed without a structured failure reason";
  return "No failure recorded";
}

export function watchlistCoverage(items: Watchlist[], type: string) {
  return items.filter((item) => item.enabled && item.type === type).length;
}

export function reviewRecommendation(review: ProductReview) {
  return getString(review.result.recommendation) ?? getString(review.result.verdict) ?? "monitor";
}

export type ClusterSummary = {
  id: string;
  title: string;
  category: string;
  events: Array<Event | EventDetail>;
  eventCount: number;
  sourceCount: number;
  evidenceCount: number;
  languages: string[];
  importance: number;
  confidence: number;
  status: string;
  kind: SignalKind;
};

export function buildClusters(events: Array<Event | EventDetail>, sources: Source[] = []): ClusterSummary[] {
  const groups = new Map<string, Array<Event | EventDetail>>();
  for (const event of events) {
    const key = event.cluster_id ?? `category:${event.category}`;
    groups.set(key, [...(groups.get(key) ?? []), event]);
  }

  return Array.from(groups.entries())
    .map(([id, groupedEvents]) => {
      const representative = groupedEvents.toSorted((a, b) => b.importance_score - a.importance_score)[0];
      const totalEvidence = groupedEvents.reduce((sum, event) => sum + evidenceCount(event), 0);
      const explicitSources = groupedEvents.reduce((sum, event) => sum + sourceCount(event), 0);
      const categorySources = sourcesForCategory(sources, representative.category).length;
      const languages = unique(groupedEvents.flatMap((event) => eventLanguages(event, sources)));
      const confidence = groupedEvents.reduce((sum, event) => sum + event.confidence, 0) / groupedEvents.length;
      return {
        id,
        title: representative.title,
        category: representative.category,
        events: groupedEvents,
        eventCount: groupedEvents.length,
        sourceCount: Math.max(explicitSources, categorySources),
        evidenceCount: totalEvidence,
        languages,
        importance: Math.max(...groupedEvents.map((event) => event.importance_score)),
        confidence,
        status: representative.verification_status,
        kind: signalKind(representative),
      };
    })
    .toSorted((a, b) => b.importance - a.importance);
}
