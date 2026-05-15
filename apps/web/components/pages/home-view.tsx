"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  BookOpen,
  Bot,
  Compass,
  Inbox,
  LifeBuoy,
  Sparkles,
  Wand2,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { usePreferences } from "@/components/preferences-provider";
import { Badge, Button, Input, Panel } from "@/components/ui";
import { translateDynamic } from "@/lib/i18n";
import { v2 } from "@/lib/api-v2";
import { fmtDate } from "@/lib/utils";

export function HomeView() {
  const router = useRouter();
  const { preferences, t } = usePreferences();

  const statsQuery = useQuery({
    queryKey: ["v2", "stats"],
    queryFn: () => v2.libraryStats(),
    staleTime: 10_000,
  });
  const recentQuery = useQuery({
    queryKey: ["v2", "recent"],
    queryFn: () => v2.libraryList({ limit: 6 }),
    staleTime: 10_000,
  });

  const [quickAsk, setQuickAsk] = useState("");
  const askMutation = useMutation({
    mutationFn: () => v2.ask({ question: quickAsk, language: preferences.language }),
    onSuccess: (data) => {
      sessionStorage.setItem("reality-os:last-ask", JSON.stringify(data));
      router.push(`/ask?q=${encodeURIComponent(quickAsk)}`);
    },
  });

  const stats = statsQuery.data;
  const recent = recentQuery.data?.items ?? [];
  const isEmpty = (stats?.total ?? 0) === 0;

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-2 border-b border-border pb-5">
        <div className="text-xs font-semibold uppercase tracking-widest text-muted">Reality OS</div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">{t("home.title")}</h1>
        <p className="max-w-3xl text-sm leading-6 text-muted">{t("home.subtitle")}</p>
      </header>

      {isEmpty ? <EmptyCallout /> : null}

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label={t("home.metric.total")} value={stats?.total ?? 0} />
        <Metric label={t("home.metric.verified")} value={stats?.verified ?? 0} tone="success" />
        <Metric label={t("home.metric.pending")} value={stats?.pending_review ?? 0} tone="warning" />
        <Metric label={t("home.metric.insufficient")} value={stats?.insufficient ?? 0} tone="danger" />
      </section>
      <section className="grid gap-3 sm:grid-cols-2">
        <Metric label={t("home.metric.concepts")} value={stats?.concepts ?? 0} />
        <Metric label={t("home.metric.memory")} value={stats?.memory_notes ?? 0} />
      </section>

      <Panel>
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <h2 className="text-sm font-semibold text-foreground">{t("home.quick_ask.title")}</h2>
            <p className="mt-1 text-sm leading-6 text-muted">{t("home.quick_ask.hint")}</p>
          </div>
          <Badge className="border-accent/40 bg-accent-soft text-foreground">
            {preferences.language === "zh-CN" ? "简中" : "EN"}
          </Badge>
        </div>
        <div className="mt-4 flex flex-col gap-2 sm:flex-row">
          <Input
            placeholder={t("ask.placeholder")}
            value={quickAsk}
            onChange={(event) => setQuickAsk(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && quickAsk.trim()) askMutation.mutate();
            }}
          />
          <Button
            type="button"
            onClick={() => quickAsk.trim() && askMutation.mutate()}
            disabled={askMutation.isPending || !quickAsk.trim()}
          >
            <Compass className="h-4 w-4" aria-hidden="true" />
            {askMutation.isPending ? t("ask.submitting") : t("ask.submit")}
          </Button>
        </div>
        {askMutation.isError ? (
          <div className="mt-2 text-xs text-danger">
            {t("ask.error")}
            {(askMutation.error as Error)?.message}
          </div>
        ) : null}
      </Panel>

      <section>
        <h2 className="mb-3 text-sm font-semibold text-foreground">{t("home.shortcuts.title")}</h2>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
          <ShortcutTile icon={Compass} href="/ask" title={t("home.shortcuts.ask")} />
          <ShortcutTile icon={Inbox} href="/capture" title={t("home.shortcuts.capture")} />
          <ShortcutTile icon={Wand2} href="/prompt" title={t("home.shortcuts.prompt")} />
          <ShortcutTile icon={Bot} href="/supervise" title={t("home.shortcuts.supervise")} />
          <ShortcutTile icon={LifeBuoy} href="/learn" title={t("home.shortcuts.learn")} />
        </div>
      </section>

      <Panel>
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-foreground">{t("home.recent.title")}</h2>
          <Link href="/library" className="text-xs text-accent hover:underline">
            {t("library.title")} <ArrowRight className="ml-0.5 inline h-3 w-3" aria-hidden="true" />
          </Link>
        </div>
        {recent.length === 0 ? (
          <div className="mt-3 rounded-md border border-dashed border-border bg-panel-muted px-3 py-6 text-center text-sm text-muted">
            {t("home.recent.empty")}
          </div>
        ) : (
          <ul className="mt-3 divide-y divide-border">
            {recent.map((item) => (
              <li key={item.id} className="flex items-start justify-between gap-3 py-2">
                <div className="min-w-0">
                  <Link href={`/library/${item.id}`} className="block truncate text-sm font-medium text-foreground hover:underline">
                    {item.title}
                  </Link>
                  <div className="mt-0.5 text-xs text-muted">
                    {fmtDate(item.created_at, preferences.language)} ·{" "}
                    {translateDynamic(preferences.language, item.source_kind)}
                  </div>
                </div>
                <Badge className="whitespace-nowrap">
                  {t(`tier.${item.quality_tier}`)}
                </Badge>
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}

function Metric({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone?: "success" | "warning" | "danger";
}) {
  const toneClass =
    tone === "success"
      ? "text-success"
      : tone === "warning"
      ? "text-warning"
      : tone === "danger"
      ? "text-danger"
      : "text-foreground";
  return (
    <Panel>
      <div className="text-xs font-semibold uppercase tracking-widest text-muted">{label}</div>
      <div className={`mt-2 text-2xl font-bold ${toneClass}`}>{value}</div>
    </Panel>
  );
}

function ShortcutTile({
  icon: Icon,
  href,
  title,
}: {
  icon: typeof Sparkles;
  href: string;
  title: string;
}) {
  return (
    <Link
      href={href}
      className="flex items-center gap-3 rounded-panel border border-border bg-panel p-4 text-sm text-foreground/90 shadow-panel transition hover:border-accent hover:bg-panel-muted"
    >
      <span className="flex h-8 w-8 items-center justify-center rounded-md bg-accent-soft text-accent">
        <Icon className="h-4 w-4" aria-hidden="true" />
      </span>
      <span className="flex-1 leading-5">{title}</span>
      <ArrowRight className="h-4 w-4 text-muted" aria-hidden="true" />
    </Link>
  );
}

function EmptyCallout() {
  const { t } = usePreferences();
  return (
    <Panel className="border-accent/40 bg-accent-soft">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <BookOpen className="h-4 w-4 text-accent" aria-hidden="true" />
            <h2 className="text-sm font-semibold text-foreground">{t("home.empty.title")}</h2>
          </div>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-muted">{t("home.empty.desc")}</p>
        </div>
        <div className="flex gap-2">
          <Button type="button" onClick={() => (window.location.href = "/capture")}>
            <Inbox className="h-4 w-4" aria-hidden="true" />
            {t("home.empty.cta_capture")}
          </Button>
          <Button type="button" variant="secondary" onClick={() => (window.location.href = "/ask")}>
            <Compass className="h-4 w-4" aria-hidden="true" />
            {t("home.empty.cta_ask")}
          </Button>
        </div>
      </div>
    </Panel>
  );
}
