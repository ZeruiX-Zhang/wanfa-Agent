"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Loader2, Network, X } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { usePreferences } from "@/components/preferences-provider";
import { Badge, Button, Panel } from "@/components/ui";
import { translateDynamic } from "@/lib/i18n";
import { v2, type KnowledgeItem, type QualityTier } from "@/lib/api-v2";
import { cn, fmtDate } from "@/lib/utils";

type Filter = "all" | QualityTier;

const FILTERS: Array<Filter> = ["all", "verified", "needs_review", "insufficient", "rejected"];

export function LibraryView() {
  const { preferences, t } = usePreferences();
  const [filter, setFilter] = useState<Filter>("all");
  const queryClient = useQueryClient();

  const listQuery = useQuery({
    queryKey: ["v2", "library", filter],
    queryFn: () =>
      v2.libraryList({
        limit: 50,
        tier: filter === "all" ? undefined : filter,
      }),
  });

  const conceptsQuery = useQuery({
    queryKey: ["v2", "concepts"],
    queryFn: () => v2.listConcepts(40),
  });

  const approveMutation = useMutation({
    mutationFn: (id: string) => v2.libraryApprove(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["v2", "library"] });
      queryClient.invalidateQueries({ queryKey: ["v2", "stats"] });
    },
  });
  const rejectMutation = useMutation({
    mutationFn: (id: string) => v2.libraryReject(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["v2", "library"] });
      queryClient.invalidateQueries({ queryKey: ["v2", "stats"] });
    },
  });

  const items = listQuery.data?.items ?? [];
  const concepts = conceptsQuery.data?.items ?? [];

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-2 border-b border-border pb-5">
        <div className="text-xs font-semibold uppercase tracking-widest text-muted">Reality OS</div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">{t("library.title")}</h1>
        <p className="max-w-3xl text-sm leading-6 text-muted">{t("library.subtitle")}</p>
      </header>

      <div className="flex flex-wrap gap-2">
        {FILTERS.map((f) => (
          <button
            key={f}
            type="button"
            onClick={() => setFilter(f)}
            className={cn(
              "rounded-md border px-3 py-1 text-xs font-semibold transition",
              filter === f
                ? "border-accent bg-accent-soft text-foreground"
                : "border-border bg-panel text-foreground/80 hover:bg-panel-muted",
            )}
          >
            {t(`library.filter.${f}`)}
          </button>
        ))}
      </div>

      {listQuery.isPending ? (
        <Panel className="flex items-center gap-2 text-sm text-muted">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          {t("common.loading")}
        </Panel>
      ) : items.length === 0 ? (
        <Panel className="text-sm text-muted">{t("library.empty")}</Panel>
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {items.map((item) => (
            <LibraryCard
              key={item.id}
              item={item}
              onApprove={() => approveMutation.mutate(item.id)}
              onReject={() => rejectMutation.mutate(item.id)}
              busy={approveMutation.isPending || rejectMutation.isPending}
            />
          ))}
        </div>
      )}

      {concepts.length ? (
        <Panel>
          <div className="flex items-center gap-2">
            <Network className="h-4 w-4 text-accent" aria-hidden="true" />
            <h2 className="text-sm font-semibold text-foreground">{t("library.concepts.title")}</h2>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {concepts.map((c) => (
              <Badge
                key={c.id}
                className="whitespace-nowrap"
                title={c.summary}
              >
                {c.label} · {c.item_ids.length}
              </Badge>
            ))}
          </div>
        </Panel>
      ) : null}
    </div>
  );
}

function LibraryCard({
  item,
  onApprove,
  onReject,
  busy,
}: {
  item: KnowledgeItem;
  onApprove: () => void;
  onReject: () => void;
  busy: boolean;
}) {
  const { preferences, t } = usePreferences();
  const tierClass = {
    verified: "border-success/40 bg-success/10 text-success",
    needs_review: "border-warning/40 bg-warning/10 text-warning",
    insufficient: "border-danger/40 bg-danger/10 text-danger",
    rejected: "border-danger/40 bg-danger/10 text-danger",
  }[item.quality_tier];

  return (
    <Panel>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <Link href={`/library/${item.id}`} className="block text-sm font-semibold text-foreground hover:underline">
            {item.title}
          </Link>
          <div className="mt-1 text-xs text-muted">
            {fmtDate(item.created_at, preferences.language)} ·{" "}
            {translateDynamic(preferences.language, item.source_kind)}
            {item.source_url ? ` · ${new URL(item.source_url).hostname}` : ""}
          </div>
        </div>
        <Badge className={cn("whitespace-nowrap", tierClass)}>{t(`tier.${item.quality_tier}`)}</Badge>
      </div>

      <p className="mt-2 line-clamp-3 text-sm text-foreground/80">{item.body}</p>

      <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted">
        <span>
          {t("library.card.quality")} {Math.round(item.quality_score * 100)}%
        </span>
        <span>·</span>
        <span>
          {t("library.card.concepts")} {item.concept_ids.length}
        </span>
        {item.tags.length ? (
          <>
            <span>·</span>
            {item.tags.slice(0, 3).map((tag) => (
              <Badge key={tag} className="text-[10px]">
                {tag}
              </Badge>
            ))}
          </>
        ) : null}
      </div>

      {item.review_required ? (
        <div className="mt-3 flex gap-2">
          <Button type="button" variant="secondary" disabled={busy} onClick={onApprove}>
            <Check className="h-4 w-4 text-success" aria-hidden="true" />
            {t("library.card.approve")}
          </Button>
          <Button type="button" variant="ghost" disabled={busy} onClick={onReject}>
            <X className="h-4 w-4 text-danger" aria-hidden="true" />
            {t("library.card.reject")}
          </Button>
        </div>
      ) : null}
    </Panel>
  );
}
