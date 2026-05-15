"use client";

import { useQuery } from "@tanstack/react-query";
import { Gauge, TimerReset, TrendingUp, Zap } from "lucide-react";
import Link from "next/link";
import { ErrorState, LoadingState } from "@/components/data-state";
import { EvidenceStrip, FactTrendLegend, MetricCard, SignalBadge, StatusBadge } from "@/components/insight-ui";
import { PageHeader } from "@/components/page-header";
import { Panel, Table, Td, Th } from "@/components/ui";
import { useEventDetails } from "@/components/use-event-details";
import { api } from "@/lib/api";
import { evidenceCount, eventLanguages, signalKind, sourceCount } from "@/lib/insights";
import { fmtDate, pct } from "@/lib/utils";

export default function SpeedModePage() {
  const objects = useQuery({
    queryKey: ["intelligence-objects", "speed-mode"],
    queryFn: () => api.intelligenceObjects({ mode: "speed", limit: 30, sort: "-aggregate_score" }),
  });
  const events = useQuery({
    queryKey: ["events", "speed-mode"],
    queryFn: () => api.events({ limit: 40, sort: "-created_at" }),
  });
  const sources = useQuery({ queryKey: ["sources", "speed-mode"], queryFn: () => api.sources({ limit: 200, enabled: true }) });
  const details = useEventDetails(events.data?.items, 12);

  if (events.isLoading) return <LoadingState label="Loading speed-mode queue" />;
  if (events.error) return <ErrorState error={events.error} />;

  const queue = details.details;
  const trendItems = queue.filter((event) => signalKind(event) === "trend");
  const highVelocity = queue.filter((event) => event.importance_score >= 0.7 || event.novelty_score >= 0.7);
  const needsReview = queue.filter((event) => event.verification_status === "needs_human_review" || event.confidence < 0.6);
  const speedObjects = objects.data?.items ?? [];

  return (
    <>
      <PageHeader
        title="Speed Mode"
        description="Fast triage for fresh signals. Items here favor recency and novelty, so trend candidates are separated from fact candidates."
      />
      <div className="mb-4">
        <FactTrendLegend />
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard icon={TimerReset} label="Speed Objects" value={speedObjects.length} detail="Backend UIO records in speed mode" />
        <MetricCard icon={TrendingUp} label="Trend Queue" value={trendItems.length} detail="Emerging signals still seeking corroboration" />
        <MetricCard icon={Zap} label="High Velocity" value={highVelocity.length} detail="Novel or high-importance signals" />
        <MetricCard icon={Gauge} label="Needs Review" value={needsReview.length} detail="Low confidence or human-review status" />
      </div>

      <Panel className="mt-4 overflow-x-auto">
        <div className="mb-3 text-sm font-semibold">Universal Intelligence Objects</div>
        {objects.isLoading ? <div className="text-sm text-muted">Loading UIO records...</div> : null}
        {objects.error ? <ErrorState error={objects.error} /> : null}
        {!objects.isLoading && speedObjects.length === 0 ? (
          <div className="text-sm text-muted">No speed-mode objects yet. Run a speed job or sync objects from events.</div>
        ) : null}
        {speedObjects.length > 0 ? (
          <Table>
            <thead>
              <tr>
                <Th>Object</Th>
                <Th>Domain</Th>
                <Th>Sources</Th>
                <Th>Indices</Th>
                <Th>Compliance</Th>
              </tr>
            </thead>
            <tbody>
              {speedObjects.map((item) => (
                <tr key={item.id}>
                  <Td>
                    <div className="font-medium">{item.title}</div>
                    <div className="mt-1 max-w-2xl text-xs text-muted">{item.summary}</div>
                  </Td>
                  <Td>{item.domain}</Td>
                  <Td>
                    <EvidenceStrip sources={item.source_count} evidence={item.evidence_count} languages={[item.language]} />
                  </Td>
                  <Td className="text-xs">
                    Heat {pct(item.aggregate_score)} / Hype {pct(item.index_novelty)} / Uncertainty {pct(1 - item.index_credibility)}
                  </Td>
                  <Td>
                    <StatusBadge status={item.compliance_status} />
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        ) : null}
      </Panel>

      <div className="mt-4 grid gap-4 xl:grid-cols-[1fr_360px]">
        <Panel className="overflow-x-auto">
          <div className="mb-3 flex items-center justify-between gap-3">
            <div>
              <div className="text-sm font-semibold">Rapid Triage Queue</div>
              <div className="text-xs text-muted">Speed mode favors early awareness. Use Precision Mode before acting on uncertain items.</div>
            </div>
            {details.isFetching ? <span className="text-xs text-muted">Refreshing evidence...</span> : null}
          </div>
          {queue.length === 0 ? (
            <div className="text-sm text-muted">No fresh events found.</div>
          ) : (
            <Table>
              <thead>
                <tr>
                  <Th>Signal</Th>
                  <Th>Mode</Th>
                  <Th>Source / Evidence</Th>
                  <Th>Scores</Th>
                  <Th>Time</Th>
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
                      <div className="mt-1 max-w-xl text-xs leading-5 text-muted">{event.summary}</div>
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
                    <Td>
                      <div className="space-y-1 text-xs">
                        <div>Importance {pct(event.importance_score)}</div>
                        <div>Novelty {pct(event.novelty_score)}</div>
                        <div>Confidence {pct(event.confidence)}</div>
                      </div>
                    </Td>
                    <Td>{fmtDate(event.event_time ?? event.created_at)}</Td>
                    <Td>
                      <StatusBadge status={event.verification_status} />
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </Panel>

        <Panel>
          <div className="text-sm font-semibold">Speed Rules</div>
          <div className="mt-3 space-y-3 text-sm leading-6 text-slate-700">
            <div className="rounded-md border border-sky-200 bg-sky-50 p-3">
              <div className="mb-1 font-semibold text-sky-900">Trend first</div>
              Items with limited evidence remain visibly marked as trend candidates.
            </div>
            <div className="rounded-md border border-amber-200 bg-amber-50 p-3">
              <div className="mb-1 font-semibold text-amber-900">Do not promote on velocity alone</div>
              Confidence, source count, and verification status remain visible in every row.
            </div>
            <div className="rounded-md border border-slate-200 bg-white p-3">
              <div className="mb-1 font-semibold">Operational handoff</div>
              Send low-confidence or human-review items to Precision Mode for claim-level evidence checks.
            </div>
          </div>
        </Panel>
      </div>
    </>
  );
}
