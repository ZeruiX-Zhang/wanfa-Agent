"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bitcoin, Save, ShoppingCart, Sparkles, Trash2 } from "lucide-react";
import type { FormEvent } from "react";
import { useState } from "react";
import { ErrorState, LoadingState } from "@/components/data-state";
import { MetricCard, StatusBadge } from "@/components/insight-ui";
import { PageHeader } from "@/components/page-header";
import { Button, Input, Panel, Select, Table, Td, Th } from "@/components/ui";
import { api } from "@/lib/api";
import { watchlistCoverage } from "@/lib/insights";

const WATCHLIST_TYPES = ["company", "product", "token", "ecommerce_category", "keyword", "brand", "protocol", "exchange", "competitor"];

export default function WatchlistsPage() {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ type: "company", name: "", value: "" });
  const { data, isLoading, error } = useQuery({ queryKey: ["watchlists"], queryFn: () => api.watchlists({ limit: 200 }) });
  const create = useMutation({
    mutationFn: () => api.createWatchlist({ ...form, enabled: true, metadata: {} }),
    onSuccess: () => {
      setForm({ type: "company", name: "", value: "" });
      queryClient.invalidateQueries({ queryKey: ["watchlists"] });
    },
  });
  const patch = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Record<string, unknown> }) => api.patchWatchlist(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["watchlists"] }),
  });
  const remove = useMutation({
    mutationFn: api.deleteWatchlist,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["watchlists"] }),
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    create.mutate();
  }

  const items = data?.items ?? [];
  const enabled = items.filter((item) => item.enabled).length;

  return (
    <>
      <PageHeader
        title="Watchlists"
        description="Inputs for query planning across AI products, crypto assets, ecommerce categories, competitors, brands, and keywords."
      />

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard icon={Sparkles} label="AI Coverage" value={watchlistCoverage(items, "product") + watchlistCoverage(items, "company")} detail="Companies and products feeding AI monitoring" />
        <MetricCard icon={Bitcoin} label="Crypto Coverage" value={watchlistCoverage(items, "token") + watchlistCoverage(items, "protocol")} detail="Tokens, protocols, and exchanges" />
        <MetricCard icon={ShoppingCart} label="Ecommerce Coverage" value={watchlistCoverage(items, "ecommerce_category") + watchlistCoverage(items, "brand")} detail="Categories and brands for market monitoring" />
        <MetricCard label="Enabled Items" value={enabled} detail={`${items.length} total watchlist records`} />
      </div>

      <Panel className="mt-4">
        <form className="grid gap-3 md:grid-cols-5" onSubmit={submit}>
          <Select value={form.type} onChange={(event) => setForm({ ...form, type: event.target.value })}>
            {WATCHLIST_TYPES.map((type) => (
              <option value={type} key={type}>
                {type}
              </option>
            ))}
          </Select>
          <Input
            className="md:col-span-2"
            required
            placeholder="name"
            value={form.name}
            onChange={(event) => setForm({ ...form, name: event.target.value })}
          />
          <Input required placeholder="value" value={form.value} onChange={(event) => setForm({ ...form, value: event.target.value })} />
          <Button disabled={create.isPending} type="submit">
            <Save className="h-4 w-4" aria-hidden="true" />
            Add
          </Button>
        </form>
      </Panel>

      {isLoading ? <LoadingState label="Loading watchlists" /> : null}
      {error ? <ErrorState error={error} /> : null}
      {data ? (
        <Panel className="mt-4 overflow-x-auto">
          {items.length === 0 ? (
            <div className="text-sm text-muted">No watchlists yet.</div>
          ) : (
            <Table>
              <thead>
                <tr>
                  <Th>Type</Th>
                  <Th>Name</Th>
                  <Th>Value</Th>
                  <Th>Query Planner Status</Th>
                  <Th>Actions</Th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id}>
                    <Td>{item.type}</Td>
                    <Td className="font-medium">{item.name}</Td>
                    <Td>{item.value}</Td>
                    <Td>
                      <StatusBadge status={item.enabled ? "enabled" : "disabled"} />
                      <div className="mt-1 text-xs text-muted">
                        {item.enabled ? "Eligible for daily query batches" : "Excluded from query planning"}
                      </div>
                    </Td>
                    <Td>
                      <div className="flex gap-2">
                        <Button variant="secondary" onClick={() => patch.mutate({ id: item.id, payload: { enabled: !item.enabled } })}>
                          {item.enabled ? "Disable" : "Enable"}
                        </Button>
                        <Button variant="danger" title="Delete" onClick={() => remove.mutate(item.id)}>
                          <Trash2 className="h-4 w-4" aria-hidden="true" />
                        </Button>
                      </div>
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
