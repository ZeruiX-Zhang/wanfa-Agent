"use client";

import { useQuery } from "@tanstack/react-query";
import { Database, Languages, Network, Quote } from "lucide-react";
import Link from "next/link";
import { ErrorState, LoadingState } from "@/components/data-state";
import { EvidenceStrip, FactTrendLegend, MetricCard, SignalBadge, StatusBadge } from "@/components/insight-ui";
import { PageHeader } from "@/components/page-header";
import { Panel, Table, Td, Th } from "@/components/ui";
import { useEventDetails } from "@/components/use-event-details";
import { api } from "@/lib/api";
import { buildClusters, categoryLabel } from "@/lib/insights";
import { pct } from "@/lib/utils";

export default function ClustersPage() {
  const backendClusters = useQuery({ queryKey: ["backend-clusters"], queryFn: () => api.clusters({ limit: 80 }) });
  const backendCross = useQuery({ queryKey: ["backend-cross-language"], queryFn: () => api.crossLanguageCandidates({ limit: 50 }) });
  const events = useQuery({ queryKey: ["events", "clusters"], queryFn: () => api.events({ limit: 80, sort: "-importance_score" }) });
  const sources = useQuery({ queryKey: ["sources", "clusters"], queryFn: () => api.sources({ limit: 200, enabled: true }) });
  const details = useEventDetails(events.data?.items, 30);

  if (events.isLoading) return <LoadingState label="Loading clusters" />;
  if (events.error) return <ErrorState error={events.error} />;

  const clusters = buildClusters(details.details, sources.data?.items ?? []);
  const sourceTotal = clusters.reduce((sum, cluster) => sum + cluster.sourceCount, 0);
  const evidenceTotal = clusters.reduce((sum, cluster) => sum + cluster.evidenceCount, 0);
  const crossLanguage = backendCross.data?.total ?? clusters.filter((cluster) => cluster.languages.length > 1).length;
  const officialClusters = backendClusters.data?.items ?? [];

  return (
    <>
      <PageHeader
        title="Clusters"
        description="Grouped intelligence candidates with fact/trend state, source diversity, evidence counts, and cross-language indicators."
      />
      <div className="mb-4">
        <FactTrendLegend />
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard icon={Network} label="Backend Clusters" value={officialClusters.length || clusters.length} detail="Same-language clusters from the cluster engine" />
        <MetricCard icon={Database} label="Source Coverage" value={sourceTotal} detail="Summed source diversity across visible clusters" />
        <MetricCard icon={Quote} label="Evidence Items" value={evidenceTotal} detail="Direct event evidence attached to cluster members" />
        <MetricCard icon={Languages} label="Cross-Language" value={crossLanguage} detail="Clusters with more than one language candidate" />
      </div>

      <Panel className="mt-4 overflow-x-auto">
        <div className="mb-3 text-sm font-semibold">Cluster Engine Output</div>
        {backendClusters.isLoading ? <div className="text-sm text-muted">Loading backend clusters...</div> : null}
        {backendClusters.error ? <ErrorState error={backendClusters.error} /> : null}
        {!backendClusters.isLoading && officialClusters.length === 0 ? (
          <div className="text-sm text-muted">No backend cluster rows yet. Event-derived grouping is shown below as a fallback.</div>
        ) : null}
        {officialClusters.length > 0 ? (
          <Table>
            <thead>
              <tr>
                <Th>Cluster</Th>
                <Th>Language</Th>
                <Th>Scores</Th>
                <Th>Status</Th>
                <Th>Cross-Key</Th>
              </tr>
            </thead>
            <tbody>
              {officialClusters.map((cluster) => (
                <tr key={cluster.id}>
                  <Td>
                    <div className="font-medium">{cluster.title}</div>
                    <div className="mt-1 max-w-2xl text-xs text-muted">{cluster.merged_summary}</div>
                  </Td>
                  <Td>{cluster.language}</Td>
                  <Td className="text-xs">
                    Confidence {pct(cluster.confidence_score)} / Heat {pct(cluster.importance_score)} / Sources{" "}
                    {pct(cluster.source_diversity_score)}
                  </Td>
                  <Td>
                    <StatusBadge status={cluster.verification_status} />
                  </Td>
                  <Td className="text-xs text-muted">{cluster.cross_language_key ?? "candidate only"}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        ) : null}
      </Panel>

      <Panel className="mt-4 overflow-x-auto">
        <div className="mb-3 flex items-center justify-between gap-3">
          <div>
            <div className="text-sm font-semibold">Cluster Review</div>
            <div className="text-xs text-muted">Cluster rows preserve whether the group is an observed trend or evidence-backed fact.</div>
          </div>
          {details.isFetching ? <span className="text-xs text-muted">Refreshing member evidence...</span> : null}
        </div>

        {clusters.length === 0 ? (
          <div className="text-sm text-muted">No clusters found.</div>
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>Cluster</Th>
                <Th>Type</Th>
                <Th>Coverage</Th>
                <Th>Scores</Th>
                <Th>Status</Th>
                <Th>Members</Th>
              </tr>
            </thead>
            <tbody>
              {clusters.map((cluster) => (
                <tr key={cluster.id}>
                  <Td>
                    <div className="font-medium">{cluster.title}</div>
                    <div className="mt-1 text-xs text-muted">{categoryLabel(cluster.category)}</div>
                  </Td>
                  <Td>
                    <SignalBadge kind={cluster.kind} />
                  </Td>
                  <Td>
                    <EvidenceStrip sources={cluster.sourceCount} evidence={cluster.evidenceCount} languages={cluster.languages} />
                  </Td>
                  <Td>
                    <div className="space-y-1 text-xs">
                      <div>Importance {pct(cluster.importance)}</div>
                      <div>Confidence {pct(cluster.confidence)}</div>
                    </div>
                  </Td>
                  <Td>
                    <StatusBadge status={cluster.status} />
                  </Td>
                  <Td>
                    <div className="flex flex-col gap-1">
                      {cluster.events.slice(0, 3).map((event) => (
                        <Link className="text-xs text-accent hover:underline" href={`/events/${event.id}`} key={event.id}>
                          {event.title}
                        </Link>
                      ))}
                      {cluster.eventCount > 3 ? <span className="text-xs text-muted">+{cluster.eventCount - 3} more</span> : null}
                    </div>
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Panel>
    </>
  );
}
