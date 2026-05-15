"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FilePlus2, FileText, Timer, TrendingUp } from "lucide-react";
import Link from "next/link";
import { ErrorState, LoadingState } from "@/components/data-state";
import { MetricCard, StatusBadge } from "@/components/insight-ui";
import { PageHeader } from "@/components/page-header";
import { Badge, Button, Panel, Table, Td, Th } from "@/components/ui";
import { api } from "@/lib/api";
import { fmtDate } from "@/lib/utils";

export default function ReportsPage() {
  const queryClient = useQueryClient();
  const { data, isLoading, error } = useQuery({ queryKey: ["reports"], queryFn: () => api.reports({ limit: 100 }) });
  const generate = useMutation({
    mutationFn: () => api.generateReport({ report_type: "daily", mode: "verified", limit: 10 }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["reports"] }),
  });

  const reports = data?.items ?? [];
  const dailyReports = reports.filter((report) => report.report_type === "daily").length;
  const avgGeneration =
    reports.length > 0 ? reports.reduce((sum, report) => sum + report.generation_seconds, 0) / reports.length : 0;

  return (
    <>
      <PageHeader
        title="Reports"
        description="Generated intelligence reports with report type, generation duration, and export-ready detail pages."
        actions={
          <Button disabled={generate.isPending} onClick={() => generate.mutate()}>
            <FilePlus2 className="h-4 w-4" aria-hidden="true" />
            Generate Verified
          </Button>
        }
      />

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard icon={FileText} label="Reports" value={data?.total ?? 0} detail="Report records returned by the backend" />
        <MetricCard icon={TrendingUp} label="Daily Reports" value={dailyReports} detail="Daily intelligence output" />
        <MetricCard icon={Timer} label="Avg Generation" value={`${avgGeneration.toFixed(1)}s`} detail="Average generation time across visible reports" />
        <MetricCard label="Export" value="MD / JSON" detail="Detail pages expose Markdown and JSON exports" />
      </div>

      {isLoading ? <LoadingState label="Loading reports" /> : null}
      {error ? <ErrorState error={error} /> : null}
      {data ? (
        <Panel className="mt-4 overflow-x-auto">
          {reports.length === 0 ? (
            <div className="text-sm text-muted">No reports yet.</div>
          ) : (
            <Table>
              <thead>
                <tr>
                  <Th>Title</Th>
                  <Th>Type / Mode</Th>
                  <Th>Period</Th>
                  <Th>Generated</Th>
                  <Th>Duration</Th>
                  <Th>Status</Th>
                </tr>
              </thead>
              <tbody>
                {reports.map((report) => (
                  <tr key={report.id}>
                    <Td>
                      <Link className="font-medium hover:text-accent" href={`/reports/${report.id}`}>
                        {report.title}
                      </Link>
                    </Td>
                    <Td>
                      <Badge>{report.report_type}</Badge>
                      <div className="mt-1 text-xs text-muted">{report.mode}</div>
                    </Td>
                    <Td>{fmtDate(report.period_start)} - {fmtDate(report.period_end)}</Td>
                    <Td>{fmtDate(report.created_at)}</Td>
                    <Td>{report.generation_seconds}s</Td>
                    <Td>
                      <StatusBadge status="completed" />
                    </Td>
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
