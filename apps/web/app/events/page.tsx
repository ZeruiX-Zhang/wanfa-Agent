"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { ErrorState, LoadingState } from "@/components/data-state";
import { EvidenceStrip, FactTrendLegend, SignalBadge, StatusBadge } from "@/components/insight-ui";
import { PageHeader } from "@/components/page-header";
import { Input, Panel, Select, Table, Td, Th } from "@/components/ui";
import { useEventDetails } from "@/components/use-event-details";
import { api } from "@/lib/api";
import { evidenceCount, eventLanguages, signalKind, sourceCount } from "@/lib/insights";
import { fmtDate, pct } from "@/lib/utils";

export default function EventsPage() {
  const [category, setCategory] = useState("");
  const [status, setStatus] = useState("");
  const [confidence, setConfidence] = useState("");
  const sources = useQuery({ queryKey: ["sources", "events"], queryFn: () => api.sources({ limit: 200 }) });
  const events = useQuery({
    queryKey: ["events", category, status, confidence],
    queryFn: () =>
      api.events({
        category,
        verification_status: status,
        min_confidence: confidence ? Number(confidence) : undefined,
        sort: "-importance_score",
      }),
  });
  const details = useEventDetails(events.data?.items, 20);

  return (
    <>
      <PageHeader title="Events" description="Full event browser with filters, fact/trend labels, source counts, evidence counts, and verification status." />
      <div className="mb-4">
        <FactTrendLegend />
      </div>
      <Panel className="mb-4 grid gap-3 md:grid-cols-3">
        <Input placeholder="category" value={category} onChange={(event) => setCategory(event.target.value)} />
        <Select value={status} onChange={(event) => setStatus(event.target.value)}>
          <option value="">All verification statuses</option>
          <option value="verified">verified</option>
          <option value="partially_verified">partially_verified</option>
          <option value="unverified">unverified</option>
          <option value="conflicting">conflicting</option>
          <option value="needs_human_review">needs_human_review</option>
          <option value="low_quality">low_quality</option>
        </Select>
        <Input placeholder="min confidence, e.g. 0.6" value={confidence} onChange={(event) => setConfidence(event.target.value)} />
      </Panel>
      {events.isLoading ? <LoadingState label="Loading events" /> : null}
      {events.error ? <ErrorState error={events.error} /> : null}
      {events.data ? (
        <Panel className="overflow-x-auto">
          {details.details.length === 0 ? (
            <div className="text-sm text-muted">No events match current filters.</div>
          ) : (
            <Table>
              <thead>
                <tr>
                  <Th>Event</Th>
                  <Th>Type</Th>
                  <Th>Evidence</Th>
                  <Th>Importance</Th>
                  <Th>Confidence</Th>
                  <Th>Status</Th>
                  <Th>Time</Th>
                </tr>
              </thead>
              <tbody>
                {details.details.map((event) => (
                  <tr key={event.id}>
                    <Td>
                      <Link className="font-medium hover:text-accent" href={`/events/${event.id}`}>
                        {event.title}
                      </Link>
                      <div className="mt-1 max-w-2xl text-xs text-muted">{event.summary}</div>
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
                    <Td>{pct(event.importance_score)}</Td>
                    <Td>{pct(event.confidence)}</Td>
                    <Td>
                      <StatusBadge status={event.verification_status} />
                    </Td>
                    <Td>{fmtDate(event.event_time ?? event.created_at)}</Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </Panel>
      ) : null}
    </>
  );
}
