"use client";

import { useQuery } from "@tanstack/react-query";
import { Database, Quote, Sparkles, Target } from "lucide-react";
import { useParams } from "next/navigation";
import { ErrorState, LoadingState } from "@/components/data-state";
import { MetricCard, StatusBadge } from "@/components/insight-ui";
import { PageHeader } from "@/components/page-header";
import { Badge, Panel, Table, Td, Th } from "@/components/ui";
import { api } from "@/lib/api";
import { getStringList, reviewRecommendation } from "@/lib/insights";
import { pct, unique } from "@/lib/utils";

type ComparisonRow = Record<string, unknown>;

function comparisonRows(value: unknown): ComparisonRow[] {
  if (!Array.isArray(value)) return [];
  return value.filter((row): row is ComparisonRow => typeof row === "object" && row !== null && !Array.isArray(row));
}

export default function AIProductReviewDetailPage() {
  const params = useParams<{ id: string }>();
  const { data, isLoading, error } = useQuery({
    queryKey: ["product-review", params.id],
    queryFn: () => api.productReview(params.id),
  });

  if (isLoading) return <LoadingState label="Loading product review" />;
  if (error) return <ErrorState error={error} />;
  if (!data) return null;

  const rows = comparisonRows(data.result.comparison_table);
  const sourceCount = unique(data.evidence.map((item) => item.source_type || item.url)).length;
  const strengths = getStringList(data.result.strengths);
  const weaknesses = getStringList(data.result.weaknesses);

  return (
    <>
      <PageHeader
        title={data.product_name}
        description={typeof data.result.positioning === "string" ? data.result.positioning : "AI product review detail"}
      />

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard icon={Sparkles} label="Recommendation" value={<Badge>{reviewRecommendation(data)}</Badge>} detail={data.status} />
        <MetricCard icon={Target} label="Confidence" value={pct(data.confidence)} detail="Model confidence in the review result" />
        <MetricCard icon={Database} label="Sources" value={sourceCount} detail="Distinct source types or URLs" />
        <MetricCard icon={Quote} label="Evidence" value={data.evidence.length} detail="Snippets attached to this review" />
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[1fr_360px]">
        <Panel className="overflow-x-auto">
          <div className="mb-3 text-sm font-semibold">Comparison Table</div>
          {rows.length === 0 ? (
            <div className="text-sm text-muted">No comparison table returned.</div>
          ) : (
            <Table>
              <thead>
                <tr>
                  {Object.keys(rows[0]).map((key) => (
                    <Th key={key}>{key}</Th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row, index) => (
                  <tr key={`${data.id}-${index}`}>
                    {Object.entries(row).map(([key, value]) => (
                      <Td key={key}>{String(value)}</Td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </Panel>

        <Panel>
          <div className="text-sm font-semibold">Review Notes</div>
          <div className="mt-3 space-y-4">
            <div>
              <div className="mb-2 text-xs font-semibold uppercase text-muted">Strengths</div>
              {strengths.length === 0 ? (
                <div className="text-sm text-muted">No strengths listed.</div>
              ) : (
                <ul className="space-y-2 text-sm leading-6">
                  {strengths.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              )}
            </div>
            <div>
              <div className="mb-2 text-xs font-semibold uppercase text-muted">Weaknesses</div>
              {weaknesses.length === 0 ? (
                <div className="text-sm text-muted">No weaknesses listed.</div>
              ) : (
                <ul className="space-y-2 text-sm leading-6">
                  {weaknesses.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </Panel>
      </div>

      <Panel className="mt-4 overflow-x-auto">
        <div className="mb-3 text-sm font-semibold">Evidence</div>
        {data.evidence.length === 0 ? (
          <div className="text-sm text-muted">No evidence captured for this review.</div>
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>Type</Th>
                <Th>Title</Th>
                <Th>Snippet</Th>
                <Th>Confidence</Th>
                <Th>Status</Th>
              </tr>
            </thead>
            <tbody>
              {data.evidence.map((item) => (
                <tr key={item.id}>
                  <Td>{item.source_type}</Td>
                  <Td>
                    <a className="text-accent hover:underline" href={item.url} rel="noreferrer" target="_blank">
                      {item.title ?? item.url}
                    </a>
                  </Td>
                  <Td className="max-w-xl text-xs leading-5 text-muted">{item.snippet ?? "No snippet captured"}</Td>
                  <Td>{pct(item.confidence)}</Td>
                  <Td>
                    <StatusBadge status={item.confidence >= 0.7 ? "verified" : "needs_human_review"} />
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
