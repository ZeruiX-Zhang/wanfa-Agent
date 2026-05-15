"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, KeyRound, ShieldCheck, ShieldX } from "lucide-react";
import { ErrorState, LoadingState } from "@/components/data-state";
import { MetricCard, StatusBadge } from "@/components/insight-ui";
import { PageHeader } from "@/components/page-header";
import { Panel, Table, Td, Th } from "@/components/ui";
import { api } from "@/lib/api";
import { complianceForSettings, complianceForSource, jobFailureReason } from "@/lib/insights";
import { fmtDate } from "@/lib/utils";

export default function CompliancePage() {
  const settings = useQuery({ queryKey: ["settings", "compliance"], queryFn: api.settings });
  const sources = useQuery({ queryKey: ["sources", "compliance"], queryFn: () => api.sources({ limit: 200 }) });
  const policies = useQuery({ queryKey: ["source-policies", "compliance"], queryFn: () => api.sourcePolicies({ limit: 200 }) });
  const decisions = useQuery({ queryKey: ["compliance-decisions"], queryFn: () => api.complianceDecisions({ limit: 50 }) });
  const jobs = useQuery({ queryKey: ["jobs", "compliance"], queryFn: () => api.jobs({ limit: 50 }) });

  if (settings.isLoading || sources.isLoading || policies.isLoading || decisions.isLoading || jobs.isLoading) {
    return <LoadingState label="Loading compliance state" />;
  }
  if (settings.error) return <ErrorState error={settings.error} />;
  if (sources.error) return <ErrorState error={sources.error} />;
  if (policies.error) return <ErrorState error={policies.error} />;
  if (decisions.error) return <ErrorState error={decisions.error} />;
  if (jobs.error) return <ErrorState error={jobs.error} />;

  const policyBySource = new Map((policies.data?.items ?? []).map((policy) => [policy.source_id, policy]));
  const sourceChecks = (sources.data?.items ?? []).map((source) => ({
    source,
    policy: policyBySource.get(source.id),
    ...complianceForSource(source),
  }));
  const keyChecks = complianceForSettings(settings.data?.api_key_status ?? {});
  const failedJobs = (jobs.data?.items ?? []).filter((job) => job.status === "failed" || job.failure_count > 0);
  const warnings = sourceChecks.filter((check) => check.state !== "pass").length + keyChecks.filter((check) => check.state !== "pass").length;
  const recentDecisions = decisions.data?.items ?? [];

  return (
    <>
      <PageHeader
        title="Compliance"
        description="Operational compliance view for connector readiness, secret presence, source guardrails, and structured task failure reasons."
      />

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard icon={ShieldCheck} label="Policies" value={policies.data?.total ?? 0} detail="Legal Source Policy records" />
        <MetricCard icon={AlertTriangle} label="Warnings" value={warnings} detail="Missing keys, disabled sources, low trust, or connector issues" />
        <MetricCard icon={ShieldX} label="Failed Jobs" value={failedJobs.length} detail="Jobs with failure count or failed status" />
        <MetricCard icon={KeyRound} label="Decisions" value={decisions.data?.total ?? 0} detail="Recorded allow/block compliance decisions" />
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <Panel className="overflow-x-auto">
          <div className="mb-3 text-sm font-semibold">Provider Key Status</div>
          {keyChecks.length === 0 ? (
            <div className="text-sm text-muted">No provider key status returned by the backend.</div>
          ) : (
            <Table>
              <thead>
                <tr>
                  <Th>Provider</Th>
                  <Th>Status</Th>
                  <Th>Compliance Reason</Th>
                </tr>
              </thead>
              <tbody>
                {keyChecks.map((check) => (
                  <tr key={check.provider}>
                    <Td className="font-medium">{check.provider}</Td>
                    <Td>
                      <StatusBadge status={check.state === "pass" ? "configured" : "missing"} />
                    </Td>
                    <Td className="text-sm text-muted">{check.reason}</Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </Panel>

        <Panel className="overflow-x-auto">
          <div className="mb-3 text-sm font-semibold">Task Failure Reasons</div>
          {failedJobs.length === 0 ? (
            <div className="text-sm text-muted">No failed jobs in the latest job window.</div>
          ) : (
            <Table>
              <thead>
                <tr>
                  <Th>Job</Th>
                  <Th>Status</Th>
                  <Th>Failures</Th>
                  <Th>Reason</Th>
                </tr>
              </thead>
              <tbody>
                {failedJobs.map((job) => (
                  <tr key={job.id}>
                    <Td>
                      <div className="font-medium">{job.name}</div>
                      <div className="mt-1 text-xs text-muted">{fmtDate(job.started_at ?? job.created_at)}</div>
                    </Td>
                    <Td>
                      <StatusBadge status={job.status} />
                    </Td>
                    <Td>{job.failure_count}</Td>
                    <Td className="max-w-md text-sm text-muted">{jobFailureReason(job)}</Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </Panel>
      </div>

      <Panel className="mt-4 overflow-x-auto">
        <div className="mb-3 text-sm font-semibold">Recent Compliance Decisions</div>
        {recentDecisions.length === 0 ? (
          <div className="text-sm text-muted">No compliance decisions have been recorded yet.</div>
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>Source</Th>
                <Th>Mode</Th>
                <Th>Decision</Th>
                <Th>Reason</Th>
              </tr>
            </thead>
            <tbody>
              {recentDecisions.map((decision) => {
                const source = sources.data?.items.find((item) => item.id === decision.source_id);
                return (
                  <tr key={decision.id}>
                    <Td>{source?.name ?? decision.source_id}</Td>
                    <Td>{decision.mode}</Td>
                    <Td>
                      <StatusBadge status={decision.decision === "allow" ? "pass" : decision.decision === "block" ? "failed" : "needs_human_review"} />
                    </Td>
                    <Td className="max-w-2xl text-sm text-muted">{decision.reason}</Td>
                  </tr>
                );
              })}
            </tbody>
          </Table>
        )}
      </Panel>

      <Panel className="mt-4 overflow-x-auto">
        <div className="mb-3 text-sm font-semibold">Source Compliance</div>
        {sourceChecks.length === 0 ? (
          <div className="text-sm text-muted">No sources configured.</div>
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>Source</Th>
                <Th>Category</Th>
                <Th>Legal Policy</Th>
                <Th>Compliance</Th>
                <Th>Storage</Th>
                <Th>Last Fetch</Th>
              </tr>
            </thead>
            <tbody>
              {sourceChecks.map((check) => (
                <tr key={check.source.id}>
                  <Td>
                    <div className="font-medium">{check.source.name}</div>
                    <div className="mt-1 text-xs text-muted">{check.source.type} . {check.source.language}</div>
                  </Td>
                  <Td>{check.source.category}</Td>
                  <Td>
                    <div className="text-sm">{check.policy?.access_type ?? check.source.legal_use_policy}</div>
                    <div className="mt-1 text-xs text-muted">robots: {check.policy?.robots_txt_status ?? check.source.robots_policy}</div>
                  </Td>
                  <Td>
                    <StatusBadge status={check.policy?.compliance_status ?? check.source.compliance_status} />
                    <div className="mt-1 text-xs text-muted">{check.reason}</div>
                  </Td>
                  <Td className="text-xs text-muted">
                    {check.source.collection_mode}; retention {check.policy?.retention_days ?? "n/a"} days
                  </Td>
                  <Td>{fmtDate(check.source.last_fetched_at)}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Panel>
    </>
  );
}
