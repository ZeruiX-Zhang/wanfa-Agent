"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Database, Power, Save, ShieldAlert, Trash2 } from "lucide-react";
import type { FormEvent } from "react";
import { useState } from "react";
import { ErrorState, LoadingState } from "@/components/data-state";
import { MetricCard, StatusBadge } from "@/components/insight-ui";
import { PageHeader } from "@/components/page-header";
import { Badge, Button, Input, Panel, Select, Table, Td, Th } from "@/components/ui";
import { api } from "@/lib/api";
import { complianceForSource } from "@/lib/insights";
import { fmtDate, pct } from "@/lib/utils";

const SOURCE_TYPES = [
  "rss",
  "brave_search",
  "tavily",
  "official_blog",
  "github",
  "arxiv",
  "coingecko",
  "defillama",
  "product_hunt",
  "amazon_sp_api",
  "custom_url",
  "manual",
];

const SOURCE_CATEGORIES = [
  "ai_news",
  "crypto_news",
  "tech_news",
  "ai_product_review",
  "ecommerce_market",
  "github_trending",
  "arxiv_research",
  "regulation",
];

export default function SourcesPage() {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    name: "",
    type: "rss",
    category: "ai_news",
    url: "",
    trust_score: "0.6",
    language: "en",
  });
  const { data, isLoading, error } = useQuery({ queryKey: ["sources"], queryFn: () => api.sources({ limit: 200 }) });
  const create = useMutation({
    mutationFn: () =>
      api.createSource({
        name: form.name,
        type: form.type,
        category: form.category,
        url: form.url || null,
        enabled: true,
        trust_score: Number(form.trust_score),
        language: form.language,
        country: null,
        fetch_interval_minutes: 1440,
        rate_limit_per_minute: 30,
        metadata: {},
      }),
    onSuccess: () => {
      setForm({ name: "", type: "rss", category: "ai_news", url: "", trust_score: "0.6", language: "en" });
      queryClient.invalidateQueries({ queryKey: ["sources"] });
    },
  });
  const patch = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Record<string, unknown> }) => api.patchSource(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["sources"] }),
  });
  const remove = useMutation({
    mutationFn: api.deleteSource,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["sources"] }),
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    create.mutate();
  }

  const sources = data?.items ?? [];
  const enabled = sources.filter((source) => source.enabled).length;
  const failing = sources.filter((source) => source.last_error || source.last_status === "connector_unconfigured").length;
  const lowTrust = sources.filter((source) => source.trust_score < 0.45).length;
  const languages = new Set(sources.map((source) => source.language).filter(Boolean)).size;

  return (
    <>
      <PageHeader
        title="Sources"
        description="Source registry with trust, language, fetch status, compliance state, and last error visible for each connector."
      />

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard icon={Database} label="Sources" value={data?.total ?? 0} detail={`${enabled} enabled`} />
        <MetricCard icon={Power} label="Enabled" value={enabled} detail="Connectors eligible for collection" />
        <MetricCard icon={ShieldAlert} label="Warnings" value={failing + lowTrust} detail={`${failing} connector issue(s), ${lowTrust} low-trust source(s)`} />
        <MetricCard label="Languages" value={languages} detail="Distinct source languages in registry" />
      </div>

      <Panel className="mt-4">
        <form className="grid gap-3 md:grid-cols-6" onSubmit={submit}>
          <Input
            className="md:col-span-2"
            required
            placeholder="Source name"
            value={form.name}
            onChange={(event) => setForm({ ...form, name: event.target.value })}
          />
          <Select value={form.type} onChange={(event) => setForm({ ...form, type: event.target.value })}>
            {SOURCE_TYPES.map((type) => (
              <option value={type} key={type}>
                {type}
              </option>
            ))}
          </Select>
          <Select value={form.category} onChange={(event) => setForm({ ...form, category: event.target.value })}>
            {SOURCE_CATEGORIES.map((category) => (
              <option value={category} key={category}>
                {category}
              </option>
            ))}
          </Select>
          <Input
            placeholder="trust score"
            value={form.trust_score}
            onChange={(event) => setForm({ ...form, trust_score: event.target.value })}
          />
          <Button disabled={create.isPending} type="submit">
            <Save className="h-4 w-4" aria-hidden="true" />
            Add
          </Button>
          <Input
            className="md:col-span-4"
            placeholder="URL, query endpoint, or manual identifier"
            value={form.url}
            onChange={(event) => setForm({ ...form, url: event.target.value })}
          />
          <Input
            className="md:col-span-2"
            placeholder="language, e.g. en or zh"
            value={form.language}
            onChange={(event) => setForm({ ...form, language: event.target.value })}
          />
        </form>
      </Panel>

      {isLoading ? <LoadingState label="Loading sources" /> : null}
      {error ? <ErrorState error={error} /> : null}
      {data ? (
        <Panel className="mt-4 overflow-x-auto">
          {sources.length === 0 ? (
            <div className="text-sm text-muted">No sources yet.</div>
          ) : (
            <Table>
              <thead>
                <tr>
                  <Th>Name</Th>
                  <Th>Type</Th>
                  <Th>Category</Th>
                  <Th>Trust</Th>
                  <Th>Compliance</Th>
                  <Th>Fetch Status</Th>
                  <Th>Last Error</Th>
                  <Th>Actions</Th>
                </tr>
              </thead>
              <tbody>
                {sources.map((source) => {
                  const compliance = complianceForSource(source);
                  return (
                    <tr key={source.id}>
                      <Td>
                        <div className="font-medium">{source.name}</div>
                        <div className="mt-1 text-xs text-muted">{source.url ?? "manual source"} . {source.language}</div>
                      </Td>
                      <Td>{source.type}</Td>
                      <Td>{source.category}</Td>
                      <Td>
                        <Input
                          className="w-20"
                          defaultValue={source.trust_score}
                          onBlur={(event) => patch.mutate({ id: source.id, payload: { trust_score: Number(event.target.value) } })}
                        />
                        <div className="mt-1 text-xs text-muted">{pct(source.trust_score)}</div>
                      </Td>
                      <Td>
                        <StatusBadge status={compliance.state === "pass" ? "pass" : compliance.state === "fail" ? "failed" : "needs_human_review"} />
                        <div className="mt-1 max-w-xs text-xs leading-5 text-muted">{compliance.reason}</div>
                      </Td>
                      <Td>
                        <Badge>{source.last_status ?? (source.enabled ? "enabled" : "disabled")}</Badge>
                        <div className="mt-1 text-xs text-muted">{fmtDate(source.last_fetched_at)}</div>
                      </Td>
                      <Td className="max-w-xs text-xs leading-5 text-muted">{source.last_error ?? "No error recorded"}</Td>
                      <Td>
                        <div className="flex gap-2">
                          <Button
                            variant="secondary"
                            title="Toggle source"
                            onClick={() => patch.mutate({ id: source.id, payload: { enabled: !source.enabled } })}
                          >
                            <Power className="h-4 w-4" aria-hidden="true" />
                          </Button>
                          <Button variant="danger" title="Delete source" onClick={() => remove.mutate(source.id)}>
                            <Trash2 className="h-4 w-4" aria-hidden="true" />
                          </Button>
                        </div>
                      </Td>
                    </tr>
                  );
                })}
              </tbody>
            </Table>
          )}
        </Panel>
      ) : null}
    </>
  );
}
