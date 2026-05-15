"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ErrorState, LoadingState } from "@/components/data-state";
import { EvidenceStrip, MetricCard, ScoreBar, SignalBadge, StatusBadge } from "@/components/insight-ui";
import { PageHeader } from "@/components/page-header";
import { Badge, Panel, Table, Td, Th } from "@/components/ui";
import { api } from "@/lib/api";
import { evidenceCount, eventLanguages, signalKind, sourceCount } from "@/lib/insights";
import { fmtDate, pct } from "@/lib/utils";

export default function EventDetailPage() {
  const params = useParams<{ id: string }>();
  const event = useQuery({
    queryKey: ["event", params.id],
    queryFn: () => api.event(params.id),
  });
  const sources = useQuery({ queryKey: ["sources", "event-detail"], queryFn: () => api.sources({ limit: 200 }) });

  if (event.isLoading) return <LoadingState label="Loading event" />;
  if (event.error) return <ErrorState error={event.error} />;
  if (!event.data) return null;

  const data = event.data;

  return (
    <>
      <PageHeader title={data.title} description={data.summary} />
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Type" value={<SignalBadge kind={signalKind(data)} />} detail={data.category} />
        <MetricCard label="Sources" value={sourceCount(data)} detail="Distinct evidence sources" />
        <MetricCard label="Evidence" value={evidenceCount(data)} detail={`${data.claims.length} claim(s)`} />
        <MetricCard label="Status" value={<StatusBadge status={data.verification_status} />} detail={data.extraction_status} />
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[1fr_360px]">
        <Panel>
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <SignalBadge kind={signalKind(data)} />
            <StatusBadge status={data.verification_status} />
            <StatusBadge status={data.extraction_status} />
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <ScoreBar label="Importance" value={data.importance_score} />
            <ScoreBar label="Confidence" value={data.confidence} />
            <ScoreBar label="Novelty" value={data.novelty_score} />
            <ScoreBar label="Actionability" value={data.actionability_score} />
          </div>
          <div className="mt-4">
            <div className="text-xs font-semibold uppercase text-muted">Why it matters</div>
            <p className="mt-1 text-sm leading-6">{data.why_it_matters}</p>
          </div>
          <div className="mt-4">
            <EvidenceStrip sources={sourceCount(data)} evidence={evidenceCount(data)} languages={eventLanguages(data, sources.data?.items ?? [])} />
          </div>
        </Panel>

        <Panel>
          <div className="text-sm font-semibold">Context</div>
          <div className="mt-3 space-y-3 text-sm">
            <div>
              <div className="text-xs uppercase text-muted">Event time</div>
              <div className="mt-1 font-medium">{fmtDate(data.event_time ?? data.created_at)}</div>
            </div>
            <div>
              <div className="text-xs uppercase text-muted">Entities</div>
              <div className="mt-2 flex flex-wrap gap-2">
                {data.entities.length ? data.entities.map((entity) => <Badge key={entity}>{entity}</Badge>) : <span className="text-muted">none</span>}
              </div>
            </div>
            <div>
              <div className="text-xs uppercase text-muted">Affected parties</div>
              <div className="mt-2 flex flex-wrap gap-2">
                {data.affected_parties.length ? (
                  data.affected_parties.map((party) => <Badge key={party}>{party}</Badge>)
                ) : (
                  <span className="text-muted">none</span>
                )}
              </div>
            </div>
          </div>
        </Panel>
      </div>

      <Panel className="mt-4 overflow-x-auto">
        <div className="mb-3 text-sm font-semibold">Claims</div>
        {data.claims.length === 0 ? (
          <div className="text-sm text-muted">No claims captured for this event.</div>
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>Claim</Th>
                <Th>Evidence Quote</Th>
                <Th>Confidence</Th>
                <Th>Needs Verification</Th>
              </tr>
            </thead>
            <tbody>
              {data.claims.map((claim) => (
                <tr key={claim.id}>
                  <Td>{claim.text}</Td>
                  <Td className="max-w-xl text-xs leading-5 text-muted">{claim.evidence_quote ?? "No quote captured"}</Td>
                  <Td>{pct(claim.confidence)}</Td>
                  <Td>
                    <StatusBadge status={claim.needs_verification ? "needs_human_review" : "verified"} />
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Panel>

      <Panel className="mt-4 overflow-x-auto">
        <div className="mb-3 text-sm font-semibold">Evidence</div>
        {data.evidence.length === 0 ? (
          <div className="text-sm text-muted">No evidence captured for this event.</div>
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>Source</Th>
                <Th>Title</Th>
                <Th>Quote</Th>
              </tr>
            </thead>
            <tbody>
              {data.evidence.map((item) => (
                <tr key={item.id}>
                  <Td>{item.source_name ?? "source n/a"}</Td>
                  <Td>
                    <a className="text-accent hover:underline" href={item.evidence_url} rel="noreferrer" target="_blank">
                      {item.title ?? item.evidence_url}
                    </a>
                  </Td>
                  <Td className="max-w-xl text-xs leading-5 text-muted">{item.quote ?? "No quote captured"}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Panel>

      <Link className="mt-4 inline-block text-sm text-accent" href="/events">
        Back to events
      </Link>
    </>
  );
}
