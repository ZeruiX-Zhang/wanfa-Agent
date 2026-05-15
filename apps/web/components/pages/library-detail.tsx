"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Loader2 } from "lucide-react";
import Link from "next/link";

import { usePreferences } from "@/components/preferences-provider";
import { Badge, Panel } from "@/components/ui";
import { translateDynamic } from "@/lib/i18n";
import { v2 } from "@/lib/api-v2";
import { cn, fmtDate } from "@/lib/utils";

export function LibraryDetail({ id }: { id: string }) {
  const { preferences, t } = usePreferences();
  const query = useQuery({
    queryKey: ["v2", "library-item", id],
    queryFn: () => v2.libraryGet(id),
  });

  if (query.isPending) {
    return (
      <Panel className="flex items-center gap-2 text-sm text-muted">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
        {t("common.loading")}
      </Panel>
    );
  }

  if (query.isError || !query.data) {
    return (
      <Panel className="text-sm text-danger">
        {(query.error as Error)?.message ?? "not found"}
      </Panel>
    );
  }

  const item = query.data;
  const tierClass = {
    verified: "border-success/40 bg-success/10 text-success",
    needs_review: "border-warning/40 bg-warning/10 text-warning",
    insufficient: "border-danger/40 bg-danger/10 text-danger",
    rejected: "border-danger/40 bg-danger/10 text-danger",
  }[item.quality_tier];

  return (
    <div className="space-y-4">
      <Link href="/library" className="inline-flex items-center gap-1 text-sm text-muted hover:text-foreground">
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        {t("library.detail.back")}
      </Link>

      <Panel>
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-xl font-bold tracking-tight text-foreground">{item.title}</h1>
          <Badge className={cn("whitespace-nowrap", tierClass)}>{t(`tier.${item.quality_tier}`)}</Badge>
        </div>
        <div className="mt-2 text-xs text-muted">
          {fmtDate(item.created_at, preferences.language)} ·{" "}
          {translateDynamic(preferences.language, item.source_kind)}
          {item.source_url ? (
            <>
              {" · "}
              <a href={item.source_url} target="_blank" rel="noreferrer" className="text-accent hover:underline">
                {new URL(item.source_url).hostname}
              </a>
            </>
          ) : null}
        </div>
      </Panel>

      <Panel>
        <h2 className="text-sm font-semibold text-foreground">{t("library.detail.scores")}</h2>
        <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
          <ScoreTile label={t("library.card.quality")} value={item.quality_score} />
          <ScoreTile label={t("library.scores.accuracy")} value={item.accuracy_score} />
          <ScoreTile label={t("library.scores.veracity")} value={item.veracity_score} />
          <ScoreTile label={t("library.scores.relevance")} value={item.relevance_score} />
        </div>
      </Panel>

      <Panel>
        <h2 className="text-sm font-semibold text-foreground">{t("library.detail.body")}</h2>
        <div className="markdown-preview mt-3 whitespace-pre-wrap text-sm leading-7 text-foreground/90">
          {item.body}
        </div>
      </Panel>

      {item.tags.length ? (
        <Panel>
          <h2 className="text-sm font-semibold text-foreground">{t("library.detail.meta")}</h2>
          <div className="mt-3 flex flex-wrap gap-2">
            {item.tags.map((tag) => (
              <Badge key={tag}>{tag}</Badge>
            ))}
          </div>
        </Panel>
      ) : null}
    </div>
  );
}

function ScoreTile({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border border-border bg-panel-muted p-3">
      <div className="text-[11px] font-semibold uppercase tracking-widest text-muted">{label}</div>
      <div className="mt-1 text-lg font-bold text-foreground">{Math.round(value * 100)}%</div>
      <div className="mt-1 h-1 overflow-hidden rounded-full bg-panel">
        <div
          className="h-full rounded-full bg-accent"
          style={{ width: `${Math.max(2, Math.round(value * 100))}%` }}
        />
      </div>
    </div>
  );
}
