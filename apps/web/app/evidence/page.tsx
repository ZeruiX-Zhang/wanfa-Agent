"use client";

import { useQuery } from "@tanstack/react-query";
import { Database, Languages, Quote, ShieldQuestion } from "lucide-react";
import Link from "next/link";
import { ErrorState, LoadingState } from "@/components/data-state";
import { EvidenceStrip, MetricCard, SignalBadge, StatusBadge } from "@/components/insight-ui";
import { PageHeader } from "@/components/page-header";
import { Panel, Table, Td, Th } from "@/components/ui";
import { useEventDetails } from "@/components/use-event-details";
import { api } from "@/lib/api";
import { crossLanguageCandidates, evidenceCount, eventLanguages, signalKind, sourceCount } from "@/lib/insights";
import { fmtDate, pct, unique } from "@/lib/utils";

export default function EvidencePage() {
  const ledger = useQuery({ queryKey: ["evidence-ledger"], queryFn: () => api.evidenceLedger({ limit: 100 }) });
  const events = useQuery({ queryKey: ["events", "evidence"], queryFn: () => api.events({ limit: 50, sort: "-importance_score" }) });
  const sources = useQuery({ queryKey: ["sources", "evidence"], queryFn: () => api.sources({ limit: 200 }) });
  const details = useEventDetails(events.data?.items, 25);

  if (events.isLoading) return <LoadingState label="Loading evidence" />;
  if (events.error) return <ErrorState error={events.error} />;

  const sourceRows = details.details.flatMap((event) =>
    event.evidence.map((item) => ({
      event,
      item,
    })),
  );
  const claimRows = details.details.flatMap((event) => event.claims.map((claim) => ({ event, claim })));
  const distinctSources = unique(sourceRows.map((row) => row.item.source_name ?? row.item.evidence_url)).length;
  const crossLanguage = crossLanguageCandidates(details.details, sources.data?.items ?? []).length;
  const ledgerRows = ledger.data?.items ?? [];

  return (
    <>
      <PageHeader
        title="Evidence"
        description="Evidence ledger for top intelligence items. Facts and trends are separated, with source counts and quoted evidence visible."
      />

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard icon={Quote} label="Ledger Rows" value={ledger.data?.total ?? sourceRows.length} detail="Immutable evidence ledger entries from the backend" />
        <MetricCard icon={Database} label="Distinct Sources" value={distinctSources} detail="Unique source names or URLs in visible evidence" />
        <MetricCard icon={ShieldQuestion} label="Claims" value={claimRows.length} detail="Claim-level verification targets" />
        <MetricCard icon={Languages} label="Cross-Language Events" value={crossLanguage} detail="Evidence candidates spanning more than one language" />
      </div>

      <Panel className="mt-4 overflow-x-auto">
        <div className="mb-3 text-sm font-semibold">Evidence Ledger</div>
        {ledger.isLoading ? <div className="text-sm text-muted">Loading ledger...</div> : null}
        {ledger.error ? <ErrorState error={ledger.error} /> : null}
        {!ledger.isLoading && ledgerRows.length === 0 ? (
          <div className="text-sm text-muted">No ledger rows yet. Event evidence below remains visible as a fallback.</div>
        ) : null}
        {ledgerRows.length > 0 ? (
          <Table>
            <thead>
              <tr>
                <Th>Evidence</Th>
                <Th>Source</Th>
                <Th>Policy</Th>
                <Th>Trust</Th>
                <Th>Ledger Hash</Th>
              </tr>
            </thead>
            <tbody>
              {ledgerRows.map((entry) => (
                <tr key={entry.id}>
                  <Td>
                    <a className="font-medium text-accent hover:underline" href={entry.evidence_url} rel="noreferrer" target="_blank">
                      {entry.title ?? entry.evidence_url}
                    </a>
                    <div className="mt-1 max-w-2xl text-xs leading-5 text-muted">{entry.quote ?? "No quote captured"}</div>
                  </Td>
                  <Td>
                    <div>{entry.source_name ?? "source n/a"}</div>
                    <div className="mt-1 text-xs text-muted">{entry.source_type ?? "type n/a"}</div>
                  </Td>
                  <Td>
                    <StatusBadge status={entry.compliance_status} />
                    <div className="mt-1 text-xs text-muted">{entry.legal_use_policy}</div>
                  </Td>
                  <Td>{pct(entry.trust_score)}</Td>
                  <Td className="max-w-52 truncate text-xs text-muted" title={entry.ledger_hash}>
                    {entry.ledger_hash}
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        ) : null}
      </Panel>

      <Panel className="mt-4 overflow-x-auto">
        <div className="mb-3 flex items-center justify-between gap-3">
          <div>
            <div className="text-sm font-semibold">Event Evidence</div>
            <div className="text-xs text-muted">Rows without enough corroboration remain marked as trend candidates.</div>
          </div>
          {details.isFetching ? <span className="text-xs text-muted">Loading evidence details...</span> : null}
        </div>
        {sourceRows.length === 0 ? (
          <div className="text-sm text-muted">No evidence rows found for the visible events.</div>
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>Event</Th>
                <Th>Type</Th>
                <Th>Source</Th>
                <Th>Evidence</Th>
                <Th>Quote</Th>
                <Th>Status</Th>
              </tr>
            </thead>
            <tbody>
              {sourceRows.map(({ event, item }) => (
                <tr key={item.id}>
                  <Td>
                    <Link className="font-medium hover:text-accent" href={`/events/${event.id}`}>
                      {event.title}
                    </Link>
                    <div className="mt-2">
                      <EvidenceStrip
                        sources={sourceCount(event)}
                        evidence={evidenceCount(event)}
                        languages={eventLanguages(event, sources.data?.items ?? [])}
                      />
                    </div>
                  </Td>
                  <Td>
                    <SignalBadge kind={signalKind(event)} />
                  </Td>
                  <Td>{item.source_name ?? "source n/a"}</Td>
                  <Td>
                    <a className="text-accent hover:underline" href={item.evidence_url} rel="noreferrer" target="_blank">
                      {item.title ?? item.evidence_url}
                    </a>
                    <div className="mt-1 text-xs text-muted">{fmtDate(item.created_at)}</div>
                  </Td>
                  <Td className="max-w-xl text-xs leading-5 text-muted">{item.quote ?? "No quote captured"}</Td>
                  <Td>
                    <StatusBadge status={event.verification_status} />
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Panel>

      <Panel className="mt-4 overflow-x-auto">
        <div className="mb-3 text-sm font-semibold">Claim Verification Targets</div>
        {claimRows.length === 0 ? (
          <div className="text-sm text-muted">No claims found for visible events.</div>
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>Claim</Th>
                <Th>Event</Th>
                <Th>Confidence</Th>
                <Th>Needs Verification</Th>
                <Th>Evidence URL</Th>
              </tr>
            </thead>
            <tbody>
              {claimRows.map(({ event, claim }) => (
                <tr key={claim.id}>
                  <Td className="max-w-xl">{claim.text}</Td>
                  <Td>
                    <Link className="text-accent hover:underline" href={`/events/${event.id}`}>
                      {event.title}
                    </Link>
                  </Td>
                  <Td>{pct(claim.confidence)}</Td>
                  <Td>
                    <StatusBadge status={claim.needs_verification ? "needs_human_review" : "verified"} />
                  </Td>
                  <Td>
                    <a className="text-accent hover:underline" href={claim.evidence_url} rel="noreferrer" target="_blank">
                      open
                    </a>
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
