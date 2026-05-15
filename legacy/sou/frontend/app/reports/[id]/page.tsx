"use client";

import { useQuery } from "@tanstack/react-query";
import { Download, FileText, ListChecks, Timer } from "lucide-react";
import { useParams } from "next/navigation";
import { ErrorState, LoadingState } from "@/components/data-state";
import { MetricCard, StatusBadge } from "@/components/insight-ui";
import { PageHeader } from "@/components/page-header";
import { Button, Panel, Table, Td, Th } from "@/components/ui";
import { api } from "@/lib/api";
import { fmtDate } from "@/lib/utils";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function ReportDetailPage() {
  const params = useParams<{ id: string }>();
  const { data, isLoading, error } = useQuery({ queryKey: ["report", params.id], queryFn: () => api.report(params.id) });

  if (isLoading) return <LoadingState label="Loading report" />;
  if (error) return <ErrorState error={error} />;
  if (!data) return null;

  return (
    <>
      <PageHeader
        title={data.title}
        description={`Report type: ${data.report_type}`}
        actions={
          <>
            <a href={`${API_BASE}/api/reports/${data.id}/export?format=markdown`} rel="noreferrer" target="_blank">
              <Button variant="secondary">
                <Download className="h-4 w-4" aria-hidden="true" />
                Markdown
              </Button>
            </a>
            <a href={`${API_BASE}/api/reports/${data.id}/export?format=json`} rel="noreferrer" target="_blank">
              <Button variant="secondary">
                <Download className="h-4 w-4" aria-hidden="true" />
                JSON
              </Button>
            </a>
          </>
        }
      />

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard icon={FileText} label="Report Type" value={data.report_type} detail={`${fmtDate(data.period_start)} - ${fmtDate(data.period_end)}`} />
        <MetricCard icon={ListChecks} label="Items" value={data.items.length} detail="Ranked recommendations in this report" />
        <MetricCard icon={Timer} label="Generation" value={`${data.generation_seconds}s`} detail={fmtDate(data.created_at)} />
        <MetricCard label="Status" value={<StatusBadge status="completed" />} detail="Report is export ready" />
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[1fr_420px]">
        <Panel>
          <div className="mb-3 text-sm font-semibold">Markdown Preview</div>
          <pre className="whitespace-pre-wrap text-sm leading-6">{data.markdown}</pre>
        </Panel>
        <Panel className="overflow-x-auto">
          <div className="mb-3 text-sm font-semibold">Report Items</div>
          {data.items.length === 0 ? (
            <div className="text-sm text-muted">No report items returned.</div>
          ) : (
            <Table>
              <thead>
                <tr>
                  <Th>#</Th>
                  <Th>Title</Th>
                  <Th>Action</Th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((item) => (
                  <tr key={item.id}>
                    <Td>{item.rank}</Td>
                    <Td>
                      <div className="font-medium">{item.title}</div>
                      <div className="mt-1 text-xs leading-5 text-muted">{item.summary}</div>
                    </Td>
                    <Td className="max-w-xs text-xs leading-5 text-muted">{item.recommended_action}</Td>
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
