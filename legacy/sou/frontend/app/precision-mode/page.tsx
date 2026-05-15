"use client";

import { useQuery } from "@tanstack/react-query";
import { Languages, Quote, ScanSearch, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { ErrorState, LoadingState } from "@/components/data-state";
import { Callout, EvidenceStrip, FactTrendLegend, MetricCard, ScoreBar, SignalBadge, StatusBadge } from "@/components/insight-ui";
import { PageHeader } from "@/components/page-header";
import { Panel, Table, Td, Th } from "@/components/ui";
import { useEventDetails } from "@/components/use-event-details";
import { api } from "@/lib/api";
import { crossLanguageCandidates, evidenceCount, eventLanguages, signalKind, sourceCount } from "@/lib/insights";
import { fmtDate, pct } from "@/lib/utils";

export default function PrecisionModePage() {
  const objects = useQuery({
    queryKey: ["intelligence-objects", "precision-mode"],
    queryFn: () => api.intelligenceObjects({ mode: "verified", limit: 30, sort: "-index_credibility" }),
  });
  const backendCandidates = useQuery({
    queryKey: ["cross-language-candidates", "precision-mode"],
    queryFn: () => api.crossLanguageCandidates({ limit: 20 }),
  });
  const ledger = useQuery({
    queryKey: ["evidence-ledger", "precision-mode"],
    queryFn: () => api.evidenceLedger({ limit: 50, sort: "-trust_score" }),
  });
  const events = useQuery({
    queryKey: ["events", "precision-mode"],
    queryFn: () => api.events({ limit: 40, sort: "-confidence", min_confidence: 0.5 }),
  });
  const sources = useQuery({ queryKey: ["sources", "precision-mode"], queryFn: () => api.sources({ limit: 200, enabled: true }) });
  const details = useEventDetails(events.data?.items, 16);

  if (events.isLoading) return <LoadingState label="Loading precision queue" />;
  if (events.error) return <ErrorState error={events.error} />;

  const queue = details.details;
  const facts = queue.filter((event) => signalKind(event) === "fact");
  const trends = queue.filter((event) => signalKind(event) === "trend");
  const crossLanguage = crossLanguageCandidates(queue, sources.data?.items ?? []);
  const claimCount = queue.reduce((sum, event) => sum + event.claims.length, 0);
  const verifiedObjects = objects.data?.items ?? [];

  return (
    <>
      <PageHeader
        title="Precision Mode"
        description="Claim-level review for high-confidence promotion. Facts require corroborated evidence; trends stay labeled until the evidence threshold is met."
      />
      <div className="mb-4">
        <FactTrendLegend />
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard icon={ShieldCheck} label="Verified Objects" value={verifiedObjects.length} detail="Backend UIO records in verified mode" />
        <MetricCard icon={ScanSearch} label="Trend Candidates" value={trends.length} detail="Still needs corroboration before promotion" />
        <MetricCard icon={Quote} label="Ledger Entries" value={ledger.data?.total ?? claimCount} detail="Evidence ledger entries available for audit" />
        <MetricCard
          icon={Languages}
          label="Cross-Language"
          value={backendCandidates.data?.total ?? crossLanguage.length}
          detail="Backend candidate links before fact merge"
        />
      </div>

      <Panel className="mt-4 overflow-x-auto">
        <div className="mb-3 text-sm font-semibold">Verified-Mode Intelligence Objects</div>
        {verifiedObjects.length === 0 ? (
          <div className="text-sm text-muted">No verified-mode objects yet. Run a verified job or sync objects after extraction.</div>
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>Object</Th>
                <Th>Evidence</Th>
                <Th>Five Indices</Th>
                <Th>Status</Th>
              </tr>
            </thead>
            <tbody>
              {verifiedObjects.map((item) => (
                <tr key={item.id}>
                  <Td>
                    <div className="font-medium">{item.title}</div>
                    <div className="mt-1 max-w-2xl text-xs text-muted">{item.summary}</div>
                  </Td>
                  <Td>
                    <EvidenceStrip sources={item.source_count} evidence={item.evidence_count} languages={[item.language]} />
                  </Td>
                  <Td className="min-w-60">
                    <div className="space-y-2">
                      <ScoreBar label="Fact Strength" value={item.index_credibility} />
                      <ScoreBar label="Heat" value={item.aggregate_score} />
                      <ScoreBar label="Uncertainty" value={1 - item.index_credibility} />
                    </div>
                  </Td>
                  <Td>
                    <StatusBadge status={item.verification_status} />
                    <div className="mt-2">
                      <StatusBadge status={item.compliance_status} />
                    </div>
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Panel>

      <div className="mt-4 grid gap-4 xl:grid-cols-[1fr_380px]">
        <Panel className="overflow-x-auto">
          <div className="mb-3 flex items-center justify-between gap-3">
            <div>
              <div className="text-sm font-semibold">Promotion Review</div>
              <div className="text-xs text-muted">Each item keeps fact/trend state, evidence count, source count, and compliance-visible status together.</div>
            </div>
            {details.isFetching ? <span className="text-xs text-muted">Checking evidence...</span> : null}
          </div>
          {queue.length === 0 ? (
            <div className="text-sm text-muted">No precision candidates found.</div>
          ) : (
            <Table>
              <thead>
                <tr>
                  <Th>Candidate</Th>
                  <Th>Type</Th>
                  <Th>Evidence</Th>
                  <Th>Score Profile</Th>
                  <Th>Status</Th>
                </tr>
              </thead>
              <tbody>
                {queue.map((event) => (
                  <tr key={event.id}>
                    <Td>
                      <Link className="font-medium hover:text-accent" href={`/events/${event.id}`}>
                        {event.title}
                      </Link>
                      <div className="mt-1 max-w-xl text-xs leading-5 text-muted">
                        {event.claims.length} claim(s) . {fmtDate(event.event_time ?? event.created_at)}
                      </div>
                    </Td>
                    <Td>
                      <SignalBadge kind={signalKind(event)} />
                    </Td>
                    <Td>
                      <EvidenceStrip
                        sources={sourceCount(event)}
                        evidence={evidenceCount(event)}
                        languages={eventLanguages(event, sources.data?.items ?? [])}
                      />
                    </Td>
                    <Td className="min-w-56">
                      <div className="space-y-2">
                        <ScoreBar label="Confidence" value={event.confidence} />
                        <ScoreBar label="Impact" value={event.impact_score} />
                        <ScoreBar label="Actionability" value={event.actionability_score} />
                      </div>
                    </Td>
                    <Td>
                      <StatusBadge status={event.verification_status} />
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </Panel>

        <div className="space-y-4">
          <Panel>
            <div className="text-sm font-semibold">Cross-Language Candidates</div>
            <div className="mt-3 space-y-3">
              {crossLanguage.length === 0 ? (
                <div className="text-sm text-muted">No cross-language candidates in this sample.</div>
              ) : (
                crossLanguage.slice(0, 5).map((event) => (
                  <div className="rounded-md border border-slate-200 p-3" key={event.id}>
                    <div className="text-sm font-medium">{event.title}</div>
                    <div className="mt-2 text-xs text-muted">{eventLanguages(event, sources.data?.items ?? []).join(", ")}</div>
                  </div>
                ))
              )}
            </div>
          </Panel>
          <Callout title="Precision threshold" tone="good">
            Promote to fact only when confidence, verification status, source count, and direct evidence all support the claim.
          </Callout>
          <Callout title="Residual risk" tone="warn">
            Trend candidates can still be operationally useful, but they should not be reported as established facts.
          </Callout>
        </div>
      </div>
    </>
  );
}
