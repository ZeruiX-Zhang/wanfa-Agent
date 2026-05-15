"use client";

import { useQuery } from "@tanstack/react-query";
import { Database, PackageSearch, ShoppingCart, TrendingUp } from "lucide-react";
import Link from "next/link";
import { ErrorState, LoadingState } from "@/components/data-state";
import { EvidenceStrip, FactTrendLegend, MetricCard, SignalBadge, StatusBadge } from "@/components/insight-ui";
import { PageHeader } from "@/components/page-header";
import { Panel, Table, Td, Th } from "@/components/ui";
import { useEventDetails } from "@/components/use-event-details";
import { api } from "@/lib/api";
import { evidenceCount, eventLanguages, signalKind, sourceCount, watchlistCoverage } from "@/lib/insights";
import { fmtDate, pct } from "@/lib/utils";

export default function EcommerceMonitorPage() {
  const events = useQuery({ queryKey: ["events", "ecommerce"], queryFn: () => api.events({ limit: 100, sort: "-importance_score" }) });
  const sources = useQuery({ queryKey: ["sources", "ecommerce"], queryFn: () => api.sources({ limit: 200 }) });
  const watchlists = useQuery({ queryKey: ["watchlists", "ecommerce"], queryFn: () => api.watchlists({ limit: 200 }) });

  const ecommerceEvents = (events.data?.items ?? []).filter((event) => event.category === "ecommerce_market");
  const details = useEventDetails(ecommerceEvents, 20);

  if (events.isLoading) return <LoadingState label="Loading ecommerce monitor" />;
  if (events.error) return <ErrorState error={events.error} />;

  const sourceItems = sources.data?.items ?? [];
  const ecommerceSources = sourceItems.filter(
    (source) => source.category === "ecommerce_market" || ["amazon_sp_api", "product_hunt"].includes(source.type),
  );
  const trendEvents = details.details.filter((event) => signalKind(event) === "trend");
  const coverage = watchlistCoverage(watchlists.data?.items ?? [], "ecommerce_category") + watchlistCoverage(watchlists.data?.items ?? [], "brand");

  return (
    <>
      <PageHeader
        title="Ecommerce Monitor"
        description="Marketplace and ecommerce category monitoring with trend/fact labeling, source coverage, evidence, and watchlist readiness."
      />
      <div className="mb-4">
        <FactTrendLegend />
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard icon={ShoppingCart} label="Market Signals" value={ecommerceEvents.length} detail="Events categorized as ecommerce market intelligence" />
        <MetricCard icon={Database} label="Commerce Sources" value={ecommerceSources.length} detail="Amazon, Product Hunt, and commerce-oriented sources" />
        <MetricCard icon={PackageSearch} label="Watchlist Coverage" value={coverage} detail="Enabled ecommerce categories and brands" />
        <MetricCard icon={TrendingUp} label="Trend Candidates" value={trendEvents.length} detail="Items requiring further corroboration" />
      </div>

      <Panel className="mt-4 overflow-x-auto">
        <div className="mb-3 text-sm font-semibold">Ecommerce Intelligence Queue</div>
        {details.details.length === 0 ? (
          <div className="text-sm text-muted">No ecommerce signals found.</div>
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>Signal</Th>
                <Th>Type</Th>
                <Th>Evidence</Th>
                <Th>Scores</Th>
                <Th>Status</Th>
              </tr>
            </thead>
            <tbody>
              {details.details.map((event) => (
                <tr key={event.id}>
                  <Td>
                    <Link className="font-medium hover:text-accent" href={`/events/${event.id}`}>
                      {event.title}
                    </Link>
                    <div className="mt-1 text-xs text-muted">{fmtDate(event.event_time ?? event.created_at)}</div>
                  </Td>
                  <Td>
                    <SignalBadge kind={signalKind(event)} />
                  </Td>
                  <Td>
                    <EvidenceStrip
                      sources={sourceCount(event)}
                      evidence={evidenceCount(event)}
                      languages={eventLanguages(event, sourceItems)}
                    />
                  </Td>
                  <Td>
                    <div className="space-y-1 text-xs">
                      <div>Importance {pct(event.importance_score)}</div>
                      <div>Actionability {pct(event.actionability_score)}</div>
                      <div>Confidence {pct(event.confidence)}</div>
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
    </>
  );
}
