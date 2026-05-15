"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Clock, KeyRound, Save, Settings } from "lucide-react";
import type { FormEvent } from "react";
import { useEffect, useState } from "react";
import { ErrorState, LoadingState } from "@/components/data-state";
import { MetricCard, StatusBadge } from "@/components/insight-ui";
import { PageHeader } from "@/components/page-header";
import { Button, Input, Panel, Select, Table, Td, Th } from "@/components/ui";
import { api } from "@/lib/api";

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const { data, isLoading, error } = useQuery({ queryKey: ["settings"], queryFn: api.settings });
  const [form, setForm] = useState({
    llm_provider: "openai",
    llm_model: "gpt-4.1-mini",
    search_provider: "brave",
    report_time: "08:00",
    retention_days: "365",
  });

  useEffect(() => {
    if (data) {
      setForm({
        llm_provider: data.llm_provider,
        llm_model: data.llm_model,
        search_provider: data.search_provider,
        report_time: data.report_time,
        retention_days: String(data.retention_days),
      });
    }
  }, [data]);

  const patch = useMutation({
    mutationFn: () => api.patchSettings({ ...form, retention_days: Number(form.retention_days) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["settings"] }),
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    patch.mutate();
  }

  const keyEntries = Object.entries(data?.api_key_status ?? {});
  const configured = keyEntries.filter(([, value]) => value).length;

  return (
    <>
      <PageHeader
        title="Settings"
        description="Provider and report settings. API keys are displayed only as configured/missing status, never as plaintext secrets."
      />

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard icon={Settings} label="LLM Provider" value={form.llm_provider} detail={form.llm_model} />
        <MetricCard icon={Clock} label="Report Time" value={form.report_time} detail={`${form.retention_days} day retention`} />
        <MetricCard icon={KeyRound} label="Configured Keys" value={configured} detail={`${keyEntries.length} provider key checks`} />
        <MetricCard label="Search Provider" value={form.search_provider} detail="Used by collection and product review workflows" />
      </div>

      {isLoading ? <LoadingState label="Loading settings" /> : null}
      {error ? <ErrorState error={error} /> : null}
      {data ? (
        <div className="mt-4 grid gap-4 xl:grid-cols-2">
          <Panel>
            <form className="grid gap-3" onSubmit={submit}>
              <label className="text-sm font-medium" htmlFor="llm-provider">
                LLM provider
              </label>
              <Select
                id="llm-provider"
                value={form.llm_provider}
                onChange={(event) => setForm({ ...form, llm_provider: event.target.value })}
              >
                <option value="openai">OpenAI</option>
              </Select>
              <label className="text-sm font-medium" htmlFor="llm-model">
                LLM model
              </label>
              <Input id="llm-model" value={form.llm_model} onChange={(event) => setForm({ ...form, llm_model: event.target.value })} />
              <label className="text-sm font-medium" htmlFor="search-provider">
                Search provider
              </label>
              <Select
                id="search-provider"
                value={form.search_provider}
                onChange={(event) => setForm({ ...form, search_provider: event.target.value })}
              >
                <option value="brave">Brave</option>
                <option value="tavily">Tavily</option>
              </Select>
              <label className="text-sm font-medium" htmlFor="report-time">
                Report time
              </label>
              <Input id="report-time" value={form.report_time} onChange={(event) => setForm({ ...form, report_time: event.target.value })} />
              <label className="text-sm font-medium" htmlFor="retention-days">
                Retention days
              </label>
              <Input
                id="retention-days"
                value={form.retention_days}
                onChange={(event) => setForm({ ...form, retention_days: event.target.value })}
              />
              <Button disabled={patch.isPending} type="submit">
                <Save className="h-4 w-4" aria-hidden="true" />
                Save
              </Button>
            </form>
          </Panel>

          <Panel className="overflow-x-auto">
            <div className="mb-3 text-sm font-semibold">API Key Status</div>
            {keyEntries.length === 0 ? (
              <div className="text-sm text-muted">No API key status returned.</div>
            ) : (
              <Table>
                <thead>
                  <tr>
                    <Th>Provider</Th>
                    <Th>Status</Th>
                    <Th>Compliance Note</Th>
                  </tr>
                </thead>
                <tbody>
                  {keyEntries.map(([provider, isConfigured]) => (
                    <tr key={provider}>
                      <Td>{provider}</Td>
                      <Td>
                        <StatusBadge status={isConfigured ? "configured" : "missing"} />
                      </Td>
                      <Td className="text-sm text-muted">
                        {isConfigured ? "Key is present in environment." : "Connector should skip, mock, or report unconfigured status."}
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            )}
          </Panel>
        </div>
      ) : null}
    </>
  );
}
