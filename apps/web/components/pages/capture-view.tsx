"use client";

import { useMutation } from "@tanstack/react-query";
import { BadgeCheck, Check, Cloud, FileText, Globe, Inbox, Loader2, Wand2 } from "lucide-react";
import { useState } from "react";

import { usePreferences } from "@/components/preferences-provider";
import { Badge, Button, Input, Panel, Select, Textarea } from "@/components/ui";
import { translateDynamic } from "@/lib/i18n";
import { v2, type KnowledgeItem, type SourceKind } from "@/lib/api-v2";
import { cn } from "@/lib/utils";

const SOURCE_KINDS: Array<{ value: SourceKind; icon: typeof Inbox }> = [
  { value: "direct_import", icon: FileText },
  { value: "browser_capture", icon: Globe },
  { value: "ai_answer_capture", icon: Wand2 },
  { value: "expert_search", icon: BadgeCheck },
  { value: "enterprise_cleanse", icon: Cloud },
  { value: "memory_note", icon: Inbox },
];

export function CaptureView() {
  const { t } = usePreferences();
  const [form, setForm] = useState({
    title: "",
    body: "",
    source_kind: "direct_import" as SourceKind,
    source_url: "",
    tags: "",
    freshness_date: "",
  });
  const [result, setResult] = useState<KnowledgeItem | null>(null);

  const absorbMutation = useMutation({
    mutationFn: () =>
      v2.absorb({
        title: form.title || undefined,
        body: form.body.trim(),
        source_kind: form.source_kind,
        source_url: form.source_url.trim() || null,
        tags: form.tags
          .split(",")
          .map((tag) => tag.trim())
          .filter(Boolean),
        freshness_date: form.freshness_date.trim() || null,
      }),
    onSuccess: (data) => setResult(data),
  });

  const submit = () => {
    if (!form.body.trim()) return;
    absorbMutation.mutate();
  };

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-2 border-b border-border pb-5">
        <div className="text-xs font-semibold uppercase tracking-widest text-muted">Reality OS</div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">{t("capture.title")}</h1>
        <p className="max-w-3xl text-sm leading-6 text-muted">{t("capture.subtitle")}</p>
      </header>

      <Panel>
        <label className="text-[11px] font-semibold uppercase tracking-widest text-muted">
          {t("capture.kind.label")}
        </label>
        <div className="mt-2 grid gap-2 md:grid-cols-3">
          {SOURCE_KINDS.map((kind) => {
            const Icon = kind.icon;
            const active = form.source_kind === kind.value;
            return (
              <button
                key={kind.value}
                type="button"
                onClick={() => setForm({ ...form, source_kind: kind.value })}
                className={cn(
                  "flex items-center gap-2 rounded-md border px-3 py-2 text-sm transition",
                  active
                    ? "border-accent bg-accent-soft text-foreground"
                    : "border-border bg-panel text-foreground/80 hover:bg-panel-muted",
                )}
              >
                <Icon className={cn("h-4 w-4", active ? "text-accent" : "text-muted")} aria-hidden="true" />
                {t(`capture.kind.${kind.value}`)}
              </button>
            );
          })}
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <div>
            <label className="text-[11px] font-semibold uppercase tracking-widest text-muted">
              {t("capture.title_label")}
            </label>
            <Input
              className="mt-1"
              placeholder={t("capture.title_placeholder")}
              value={form.title}
              onChange={(event) => setForm({ ...form, title: event.target.value })}
            />
          </div>
          <div>
            <label className="text-[11px] font-semibold uppercase tracking-widest text-muted">
              {t("capture.url_label")}
            </label>
            <Input
              className="mt-1"
              placeholder={t("capture.url_placeholder")}
              value={form.source_url}
              onChange={(event) => setForm({ ...form, source_url: event.target.value })}
            />
          </div>
        </div>

        <div className="mt-3">
          <label className="text-[11px] font-semibold uppercase tracking-widest text-muted">
            {t("capture.body_label")}
          </label>
          <Textarea
            className="mt-1 min-h-48"
            placeholder={t("capture.body_placeholder")}
            value={form.body}
            onChange={(event) => setForm({ ...form, body: event.target.value })}
          />
        </div>

        <div className="mt-3 grid gap-3 md:grid-cols-2">
          <div>
            <label className="text-[11px] font-semibold uppercase tracking-widest text-muted">
              {t("capture.tags_label")}
            </label>
            <Input
              className="mt-1"
              placeholder={t("capture.tags_placeholder")}
              value={form.tags}
              onChange={(event) => setForm({ ...form, tags: event.target.value })}
            />
          </div>
          <div>
            <label className="text-[11px] font-semibold uppercase tracking-widest text-muted">
              {t("capture.freshness_label")}
            </label>
            <Input
              className="mt-1"
              placeholder="2026-01-15"
              value={form.freshness_date}
              onChange={(event) => setForm({ ...form, freshness_date: event.target.value })}
            />
          </div>
        </div>

        <div className="mt-4 flex items-center gap-2">
          <Button onClick={submit} disabled={!form.body.trim() || absorbMutation.isPending}>
            {absorbMutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                {t("capture.submitting")}
              </>
            ) : (
              <>
                <Cloud className="h-4 w-4" aria-hidden="true" />
                {t("capture.submit")}
              </>
            )}
          </Button>
          {absorbMutation.isError ? (
            <span className="text-xs text-danger">
              {t("capture.error")}
              {(absorbMutation.error as Error)?.message}
            </span>
          ) : null}
        </div>
      </Panel>

      {result ? <AbsorbedResult item={result} /> : null}

      <Panel>
        <h2 className="text-sm font-semibold text-foreground">{t("capture.shortcuts.heading")}</h2>
        <ul className="mt-3 space-y-2 text-sm text-foreground/80">
          <li className="flex gap-2">
            <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
            {t("capture.shortcuts.extension")}
          </li>
          <li className="flex gap-2">
            <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
            {t("capture.shortcuts.ai_answer")}
          </li>
          <li className="flex gap-2">
            <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
            {t("capture.shortcuts.direct")}
          </li>
          <li className="flex gap-2">
            <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
            {t("capture.shortcuts.memory")}
          </li>
        </ul>
      </Panel>
    </div>
  );
}

function AbsorbedResult({ item }: { item: KnowledgeItem }) {
  const { preferences, t } = usePreferences();
  const tierClass = {
    verified: "border-success/40 bg-success/10 text-success",
    needs_review: "border-warning/40 bg-warning/10 text-warning",
    insufficient: "border-danger/40 bg-danger/10 text-danger",
    rejected: "border-danger/40 bg-danger/10 text-danger",
  }[item.quality_tier];
  return (
    <Panel className="border-success/40">
      <div className="flex items-center gap-2">
        <Check className="h-5 w-5 text-success" aria-hidden="true" />
        <h2 className="text-sm font-semibold text-foreground">{t("capture.success.title")}</h2>
        <Badge className={cn("ml-auto whitespace-nowrap", tierClass)}>
          {t(`tier.${item.quality_tier}`)}
        </Badge>
      </div>
      <p className="mt-2 text-sm leading-6 text-muted">{t("capture.success.desc")}</p>

      <div className="mt-4 rounded-md border border-border bg-panel-muted p-3">
        <div className="text-sm font-semibold text-foreground">{item.title}</div>
        <div className="mt-1 text-xs text-muted">
          {translateDynamic(preferences.language, item.source_kind)}
          {item.source_url ? ` · ${item.source_url}` : ""}
        </div>
      </div>

      <div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        <ScoreTile label={t("library.card.quality")} value={item.quality_score} />
        <ScoreTile label={t("library.scores.accuracy")} value={item.accuracy_score} />
        <ScoreTile label={t("library.scores.veracity")} value={item.veracity_score} />
        <ScoreTile label={t("library.scores.relevance")} value={item.relevance_score} />
      </div>

      {item.concept_ids.length ? (
        <div className="mt-4">
          <div className="text-[11px] font-semibold uppercase tracking-widest text-muted">
            {t("library.card.concepts")}
          </div>
          <div className="mt-1 flex flex-wrap gap-2 text-xs text-foreground/80">
            {item.concept_ids.map((id) => (
              <code
                key={id}
                className="rounded-sm border border-border bg-panel px-1.5 py-0.5 font-mono text-[11px]"
              >
                {id}
              </code>
            ))}
          </div>
        </div>
      ) : null}
    </Panel>
  );
}

function ScoreTile({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border border-border bg-panel p-3">
      <div className="text-[11px] font-semibold uppercase tracking-widest text-muted">{label}</div>
      <div className="mt-1 text-lg font-bold text-foreground">{Math.round(value * 100)}%</div>
      <div className="mt-1 h-1 overflow-hidden rounded-full bg-panel-muted">
        <div
          className="h-full rounded-full bg-accent"
          style={{ width: `${Math.max(2, Math.round(value * 100))}%` }}
        />
      </div>
    </div>
  );
}
