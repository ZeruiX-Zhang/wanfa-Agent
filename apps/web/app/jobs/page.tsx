"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Play, TimerReset } from "lucide-react";
import { useState } from "react";
import { ErrorState, LoadingState } from "@/components/data-state";
import { MetricCard, StatusBadge } from "@/components/insight-ui";
import { PageHeader } from "@/components/page-header";
import { Badge, Button, Panel, Table, Td, Th } from "@/components/ui";
import { api } from "@/lib/api";
import { jobFailureReason } from "@/lib/insights";
import { fmtDate } from "@/lib/utils";

export default function JobsPage() {
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<string | null>(null);
  const jobs = useQuery({ queryKey: ["jobs"], queryFn: () => api.jobs({ limit: 100 }) });
  const detail = useQuery({ queryKey: ["job", selected], queryFn: () => api.job(selected as string), enabled: Boolean(selected) });
  const run = useMutation({
    mutationFn: () => api.runDaily("verified"),
    onSuccess: (job) => {
      setSelected(job.id);
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });

  const items = jobs.data?.items ?? [];
  const successes = items.filter((job) => job.status === "completed" || job.status === "success").length;
  const failures = items.filter((job) => job.status === "failed" || job.failure_count > 0).length;
  const running = items.filter((job) => ["queued", "running"].includes(job.status)).length;

  return (
    <>
      <PageHeader
        title="Jobs"
        description="Task execution history with success/failure counts, structured failure reasons, and log detail for selected runs."
        actions={
          <Button disabled={run.isPending} onClick={() => run.mutate()}>
            <Play className="h-4 w-4" aria-hidden="true" />
            Run Verified Daily
          </Button>
        }
      />

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard icon={TimerReset} label="Jobs" value={jobs.data?.total ?? 0} detail="Recent job records" />
        <MetricCard icon={CheckCircle2} label="Successful" value={successes} detail="Completed or success status" />
        <MetricCard icon={AlertTriangle} label="Failed" value={failures} detail="Failed status or nonzero failure count" />
        <MetricCard label="In Flight" value={running} detail="Queued or running jobs" />
      </div>

      {jobs.isLoading ? <LoadingState label="Loading jobs" /> : null}
      {jobs.error ? <ErrorState error={jobs.error} /> : null}
      <div className="mt-4 grid gap-4 xl:grid-cols-[1fr_460px]">
        <Panel className="overflow-x-auto">
          {items.length === 0 ? (
            <div className="text-sm text-muted">No jobs yet.</div>
          ) : (
            <Table>
              <thead>
                <tr>
                  <Th>Name</Th>
                  <Th>Type / Mode</Th>
                  <Th>Status</Th>
                  <Th>Success</Th>
                  <Th>Failure</Th>
                  <Th>Failure Reason</Th>
                  <Th>Started</Th>
                </tr>
              </thead>
              <tbody>
                {items.map((job) => (
                  <tr className="cursor-pointer hover:bg-slate-50" key={job.id} onClick={() => setSelected(job.id)}>
                    <Td className="font-medium">{job.name}</Td>
                    <Td>
                      <div>{job.type}</div>
                      <div className="mt-1 text-xs text-muted">{job.mode}</div>
                    </Td>
                    <Td>
                      <StatusBadge status={job.status} />
                    </Td>
                    <Td>{job.success_count}</Td>
                    <Td>{job.failure_count}</Td>
                    <Td className="max-w-sm text-xs leading-5 text-muted">{jobFailureReason(job)}</Td>
                    <Td>{fmtDate(job.started_at ?? job.created_at)}</Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </Panel>

        <Panel className="overflow-x-auto">
          <div className="mb-3 text-sm font-semibold">Logs</div>
          {!selected ? <div className="text-sm text-muted">Select a job to inspect stage logs and failure details.</div> : null}
          {detail.isLoading ? <LoadingState label="Loading logs" /> : null}
          {detail.error ? <ErrorState error={detail.error} /> : null}
          {detail.data ? (
            <Table>
              <thead>
                <tr>
                  <Th>Time</Th>
                  <Th>Stage</Th>
                  <Th>Level</Th>
                  <Th>Message</Th>
                </tr>
              </thead>
              <tbody>
                {detail.data.logs.map((log) => (
                  <tr key={log.id}>
                    <Td>{fmtDate(log.created_at)}</Td>
                    <Td>{log.stage}</Td>
                    <Td>
                      <Badge>{log.level}</Badge>
                    </Td>
                    <Td className="max-w-sm">
                      <div>{log.message}</div>
                      {Object.keys(log.details).length > 0 ? (
                        <pre className="mt-2 max-h-40 overflow-auto rounded-md bg-slate-50 p-2 text-xs text-muted">
                          {JSON.stringify(log.details, null, 2)}
                        </pre>
                      ) : null}
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          ) : null}
        </Panel>
      </div>
    </>
  );
}
