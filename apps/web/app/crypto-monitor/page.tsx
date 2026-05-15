"use client";

import { useQuery } from "@tanstack/react-query";
import { Bitcoin, Database, ShieldAlert, TrendingUp } from "lucide-react";
import Link from "next/link";
import { ErrorState, LoadingState } from "@/components/data-state";
import { EvidenceStrip, FactTrendLegend, MetricCard, SignalBadge, StatusBadge } from "@/components/insight-ui";
import { PageHeader } from "@/components/page-header";
import { Panel, Table, Td, Th } from "@/components/ui";
import { useEventDetails } from "@/components/use-event-details";
import { api } from "@/lib/api";
import { evidenceCount, eventLanguages, signalKind, sourceCount, watchlistCoverage } from "@/lib/insights";
import { fmtDate, pct } from "@/lib/utils";

const CRYPTO_CATEGORIES = new Set(["crypto_market", "crypto_security", "defi"]);

export default function CryptoMonitorPage() {
  const events = useQuery({ queryKey: ["events", "crypto"], queryFn: () => api.events({ limit: 100, sort: "-importance_score" }) });
  const sources = useQuery({ queryKey: ["sources", "crypto"], queryFn: () => api.sources({ limit: 200 }) });
  const watchlists = useQuery({ queryKey: ["watchlists", "crypto"], queryFn: () => api.watchlists({ limit: 200 }) });

  const cryptoEvents = (events.data?.items ?? []).filter((event) => CRYPTO_CATEGORIES.has(event.category));
  const details = useEventDetails(cryptoEvents, 20);

  if (events.isLoading) return <LoadingState label="Loading crypto monitor" />;
  if (events.error) return <ErrorState error={events.error} />;

  const sourceItems = sources.data?.items ?? [];
  const cryptoSources = sourceItems.filter((source) => source.category.includes("crypto") || ["coingecko", "defillama"].includes(source.type));
  const securityEvents = details.details.filter((event) => event.category === "crypto_security");
  const trendEvents = details.details.filter((event) => signalKind(event) === "trend");
  const coverage = watchlistCoverage(watchlists.data?.items ?? [], "token") + watchlistCoverage(watchlists.data?.items ?? [], "protocol");

  return (
    <>
      <PageHeader
        title="Crypto Monitor"
        description="Crypto market, DeFi, and security monitoring with fact/trend labels, market source coverage, evidence, and watchlist context."
      />
      <div className="mb-4">
        <FactTrendLegend />
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard icon={Bitcoin} label="Crypto Signals" value={cryptoEvents.length} detail="Market, security, and DeFi event categories" />
        <MetricCard icon={Database} label="Crypto Sources" value={cryptoSources.length} detail="CoinGecko, DefiLlama, and crypto news sources" />
        <MetricCard icon={ShieldAlert} label="Security Items" value={securityEvents.length} detail="Security-specific crypto events" />
        <MetricCard icon={TrendingUp} label="Trend Candidates" value={trendEvents.length} detail={`${coverage} enabled token/protocol watchlist item(s)`} />
      </div>

      <Panel className="mt-4 overflow-x-auto">
        <div className="mb-3 text-sm font-semibold">Crypto Intelligence Queue</div>
        {details.details.length === 0 ? (
          <div className="text-sm text-muted">No crypto signals found.</div>
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>Signal</Th>
                <Th>Type</Th>
                <Th>Category</Th>
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
                  <Td>{event.category}</Td>
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
