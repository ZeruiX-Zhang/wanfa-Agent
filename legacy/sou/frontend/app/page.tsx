"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Database, Quote, ShieldCheck, TrendingUp } from "lucide-react";
import Link from "next/link";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ErrorState, LoadingState } from "@/components/data-state";
import { EvidenceStrip, FactTrendLegend, MetricCard, SignalBadge, StatusBadge } from "@/components/insight-ui";
import { PageHeader } from "@/components/page-header";
import { Panel, Table, Td, Th } from "@/components/ui";
import { useEventDetails } from "@/components/use-event-details";
import { api } from "@/lib/api";
import { evidenceCount, eventLanguages, signalKind, sourceCount } from "@/lib/insights";
import { pct } from "@/lib/utils";

export default function OverviewPage() {
  const dashboard = useQuery({ queryKey: ["dashboard"], queryFn: api.dashboard });
  const events = useQuery({ queryKey: ["events", "overview"], queryFn: () => api.events({ limit: 12, sort: "-importance_score" }) });
  const sources = useQuery({ queryKey: ["sources", "overview"], queryFn: () => api.sources({ limit: 200 }) });
  const objects = useQuery({ queryKey: ["intelligence-objects", "overview"], queryFn: () => api.intelligenceObjects({ limit: 50 }) });
  const ledger = useQuery({ queryKey: ["evidence-ledger", "overview"], queryFn: () => api.evidenceLedger({ limit: 50 }) });
  const policies = useQuery({ queryKey: ["source-policies", "overview"], queryFn: () => api.sourcePolicies({ limit: 200 }) });
  const settings = useQuery({ queryKey: ["settings", "overview"], queryFn: api.settings });
  const eventDetails = useEventDetails(events.data?.items, 8);

  if (dashboard.isLoading) return <LoadingState label="Loading overview" />;
  if (dashboard.error) return <ErrorState error={dashboard.error} />;
  if (!dashboard.data) return null;

  const details = eventDetails.details;
  const factCount = details.filter((event) => signalKind(event) === "fact").length;
  const trendCount = details.length - factCount;
  const evidenceTotal = ledger.data?.total ?? details.reduce((sum, event) => sum + evidenceCount(event), 0);
  const sourceTotal = sources.data?.total ?? 0;
  const configuredKeys = Object.values(settings.data?.api_key_status ?? {}).filter(Boolean).length;
  const missingKeys = Math.max(0, Object.values(settings.data?.api_key_status ?? {}).length - configuredKeys);

  return (
    <>
      <PageHeader
        title="Overview"
        description="A fact/trend split for the daily intelligence pipeline with source coverage, evidence, and compliance health visible at a glance."
      />

      <div className="mb-4">
        <FactTrendLegend />
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          icon={CheckCircle2}
          label="Fact Objects"
          value={objects.data?.items.filter((item) => item.verification_status === "verified").length ?? factCount}
          detail={`${dashboard.data.verified_events} backend events are marked verified`}
        />
        <MetricCard
          icon={TrendingUp}
          label="Trends"
          value={trendCount}
          detail={`${dashboard.data.high_impact_events} high-impact signals in current data`}
        />
        <MetricCard icon={Database} label="Sources" value={sourceTotal} detail="Enabled and disabled sources tracked in the source registry" />
        <MetricCard
          icon={Quote}
          label="Ledger"
          value={evidenceTotal}
          detail={ledger.isFetching ? "Ledger counts are still refreshing" : "Evidence ledger entries"}
        />
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[1fr_420px]">
        <Panel>
          <div className="mb-3 flex items-center justify-between gap-3">
            <div>
              <div className="text-sm font-semibold">Trend Volume</div>
              <div className="text-xs text-muted">Time-series signal count. This chart is trend evidence, not verified fact.</div>
            </div>
            <SignalBadge kind="trend" />
          </div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={dashboard.data.trend}>
                <CartesianGrid stroke="#e5e7eb" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Line type="monotone" dataKey="events" stroke="#0284c7" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        <Panel>
          <div className="mb-3 flex items-center justify-between gap-3">
            <div>
              <div className="text-sm font-semibold">Fact Health</div>
              <div className="text-xs text-muted">Operational facts from source, verification, and key status.</div>
            </div>
            <SignalBadge kind="fact" />
          </div>
          <div className="space-y-3">
            <div className="flex items-center justify-between rounded-md border border-slate-200 p-3">
              <span className="text-sm text-muted">Legal source policies</span>
              <span className="font-semibold">{policies.data?.total ?? 0}</span>
            </div>
            <div className="flex items-center justify-between rounded-md border border-slate-200 p-3">
              <span className="text-sm text-muted">Configured API keys</span>
              <span className="font-semibold">{configuredKeys}</span>
            </div>
            <div className="flex items-center justify-between rounded-md border border-slate-200 p-3">
              <span className="text-sm text-muted">Missing API keys</span>
              <span className="font-semibold">{missingKeys}</span>
            </div>
            {missingKeys > 0 ? (
              <div className="flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 p-3 text-xs leading-5 text-amber-900">
                <AlertTriangle className="mt-0.5 h-4 w-4" aria-hidden="true" />
                Missing keys are surfaced as compliance warnings and connector skips, not hidden failures.
              </div>
            ) : (
              <div className="flex items-start gap-2 rounded-md border border-emerald-200 bg-emerald-50 p-3 text-xs leading-5 text-emerald-900">
                <ShieldCheck className="mt-0.5 h-4 w-4" aria-hidden="true" />
                All configured providers report a present key.
              </div>
            )}
          </div>
        </Panel>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[380px_1fr]">
        <Panel>
          <div className="mb-3 text-sm font-semibold">Category Distribution</div>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={dashboard.data.category_distribution}>
                <CartesianGrid stroke="#e5e7eb" />
                <XAxis dataKey="category" tick={{ fontSize: 11 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="count" fill="#334155" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        <Panel className="overflow-x-auto">
          <div className="mb-3 text-sm font-semibold">Top Evidence-Backed Items</div>
          {details.length === 0 ? (
            <div className="text-sm text-muted">No events yet. Run a daily job or seed data to populate this table.</div>
          ) : (
            <Table>
              <thead>
                <tr>
                  <Th>Signal</Th>
                  <Th>Type</Th>
                  <Th>Evidence</Th>
                  <Th>Confidence</Th>
                  <Th>Status</Th>
                </tr>
              </thead>
              <tbody>
                {details.map((event) => (
                  <tr key={event.id}>
                    <Td>
                      <Link className="font-medium hover:text-accent" href={`/events/${event.id}`}>
                        {event.title}
                      </Link>
                      <div className="mt-1 max-w-2xl text-xs leading-5 text-muted">{event.summary}</div>
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
                    <Td>{pct(event.confidence)}</Td>
                    <Td>
                      <StatusBadge status={event.verification_status} />
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </Panel>
      </div>
    </>
  );
}
