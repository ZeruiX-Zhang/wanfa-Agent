"use client";

import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, ChevronDown, ChevronUp, Loader2, Shield, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { usePreferences } from "@/components/preferences-provider";
import { Badge, Button, Panel } from "@/components/ui";
import { api } from "@/lib/api";
import { translateDynamic } from "@/lib/i18n";
import type { SupervisorSurface } from "@/lib/reality-adapter-data";
import { cn } from "@/lib/utils";

type RawSnapshot = Parameters<typeof api.supervisorSummary>[0]["snapshot"];

export function SupervisorDigest({
  initialSnapshot,
}: {
  initialSnapshot: SupervisorSurface;
}) {
  const { preferences, t } = usePreferences();
  const [expandedRaw, setExpandedRaw] = useState(false);

  const mutation = useMutation({
    mutationFn: async () => {
      const snapshot = toPlainSnapshot(initialSnapshot);
      return api.supervisorSummary({ language: preferences.language, snapshot });
    },
  });

  useEffect(() => {
    mutation.mutate();
    // run on language change too so the digest text stays localized
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [preferences.language]);

  const digest = mutation.data;
  const riskEntries = useMemo(() => {
    if (!digest) return [] as Array<{ risk: string; count: number }>;
    return Object.entries(digest.risk_counts || {})
      .map(([risk, count]) => ({ risk, count }))
      .sort((a, b) => b.count - a.count);
  }, [digest]);

  return (
    <div className="space-y-4">
      <Panel className="border-accent/40">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-accent" aria-hidden="true" />
              <h2 className="text-sm font-semibold text-foreground">{t("supervisor.digest.title")}</h2>
              {mutation.isPending ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin text-muted" aria-hidden="true" />
              ) : null}
            </div>
            <p className="mt-1 text-sm leading-6 text-muted">{t("supervisor.digest.desc")}</p>
          </div>
          <Button variant="secondary" type="button" onClick={() => mutation.mutate()} disabled={mutation.isPending}>
            {t("supervisor.digest.refresh")}
          </Button>
        </div>

        {mutation.isError ? (
          <div className="mt-3 rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
            {(mutation.error as Error)?.message ?? "digest failed"}
          </div>
        ) : null}

        <div className="mt-4 grid gap-3 lg:grid-cols-2">
          <DigestField
            label={t("supervisor.digest.goal")}
            value={digest?.goal ?? (mutation.isPending ? t("supervisor.digest.loading") : "-")}
            icon="goal"
          />
          <DigestField
            label={t("supervisor.digest.next")}
            value={digest?.single_next_action ?? (mutation.isPending ? t("supervisor.digest.loading") : "-")}
            icon="next"
          />
          <DigestField
            label={t("supervisor.digest.drift")}
            value={digest?.drift_alert ?? (mutation.isPending ? t("supervisor.digest.loading") : "-")}
            icon="drift"
          />
          <DigestField
            label={t("supervisor.digest.waiting")}
            value={
              digest
                ? String(digest.approvals_waiting)
                : mutation.isPending
                ? t("supervisor.digest.loading")
                : "-"
            }
            icon="shield"
          />
        </div>

        {digest?.blocked_on?.length ? (
          <div className="mt-4 rounded-md border border-border bg-panel-muted p-3">
            <div className="text-xs font-semibold uppercase tracking-widest text-muted">
              {t("supervisor.digest.blocked")}
            </div>
            <ul className="mt-2 space-y-1 text-sm text-foreground/90">
              {digest.blocked_on.map((blocker) => (
                <li key={blocker} className="flex items-start gap-2">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" aria-hidden="true" />
                  <span>{blocker}</span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {riskEntries.length ? (
          <div className="mt-4">
            <div className="text-xs font-semibold uppercase tracking-widest text-muted">
              {t("supervisor.digest.risk")}
            </div>
            <div className="mt-2 flex flex-wrap gap-2">
              {riskEntries.map((entry) => (
                <Badge
                  key={entry.risk}
                  className={cn(
                    "whitespace-nowrap",
                    entry.risk === "high" && "border-danger/40 bg-danger/10 text-danger",
                    entry.risk === "medium" && "border-warning/40 bg-warning/10 text-warning",
                  )}
                >
                  {translateDynamic(preferences.language, entry.risk)} · {entry.count}
                </Badge>
              ))}
            </div>
          </div>
        ) : null}

        {digest?.generated_from?.length ? (
          <div className="mt-3 text-xs text-muted">
            {t("supervisor.digest.source")} {digest.generated_from.join(" · ")}
          </div>
        ) : null}
      </Panel>

      <Panel>
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-foreground">{t("supervisor.raw.title")}</h3>
            <p className="mt-1 text-sm leading-6 text-muted">{t("supervisor.raw.desc")}</p>
          </div>
          <Button variant="ghost" type="button" onClick={() => setExpandedRaw((v) => !v)}>
            {expandedRaw ? (
              <>
                <ChevronUp className="h-4 w-4" aria-hidden="true" />
                {t("supervisor.raw.hide")}
              </>
            ) : (
              <>
                <ChevronDown className="h-4 w-4" aria-hidden="true" />
                {t("supervisor.raw.show")}
              </>
            )}
          </Button>
        </div>

        {expandedRaw ? <RawBehaviour surface={initialSnapshot} /> : null}
      </Panel>
    </div>
  );
}

function DigestField({
  label,
  value,
  icon,
}: {
  label: string;
  value: string;
  icon: "goal" | "next" | "drift" | "shield";
}) {
  const Icon =
    icon === "goal"
      ? Sparkles
      : icon === "next"
      ? ChevronDown
      : icon === "drift"
      ? AlertTriangle
      : Shield;
  return (
    <div className="rounded-md border border-border bg-panel p-3">
      <div className="text-[11px] font-semibold uppercase tracking-widest text-muted">{label}</div>
      <div className="mt-2 flex items-start gap-2 text-sm leading-6 text-foreground">
        <Icon className="mt-0.5 h-4 w-4 shrink-0 text-accent" aria-hidden="true" />
        <span>{value}</span>
      </div>
    </div>
  );
}

function RawBehaviour({ surface }: { surface: SupervisorSurface }) {
  const { preferences, t } = usePreferences();
  const language = preferences.language;
  return (
    <div className="mt-4 grid gap-4 xl:grid-cols-2">
      <div>
        <h4 className="text-xs font-semibold uppercase tracking-widest text-muted">
          {t("supervisor.raw.tasks")}
        </h4>
        <div className="mt-2 space-y-2">
          {surface.agentTasks.map((task) => (
            <div key={task.id} className="rounded-md border border-border bg-panel-muted p-3">
              <div className="flex flex-wrap items-center gap-2">
                <div className="text-sm font-semibold text-foreground">{task.title}</div>
                <Badge>{translateDynamic(language, task.status)}</Badge>
                <Badge
                  className={cn(
                    task.risk === "high" && "border-danger/40 bg-danger/10 text-danger",
                    task.risk === "medium" && "border-warning/40 bg-warning/10 text-warning",
                  )}
                >
                  {translateDynamic(language, task.risk)}
                </Badge>
                {task.dryRun ? <Badge>{t("common.dry_run")}</Badge> : null}
              </div>
            </div>
          ))}
          {surface.agentTasks.length === 0 ? (
            <div className="rounded-md border border-dashed border-border bg-panel-muted px-3 py-2 text-sm text-muted">
              —
            </div>
          ) : null}
        </div>
      </div>

      <div>
        <h4 className="text-xs font-semibold uppercase tracking-widest text-muted">
          {t("supervisor.raw.approvals")}
        </h4>
        <div className="mt-2 space-y-2">
          {surface.approvalRequests.map((approval) => (
            <div key={approval.id} className="rounded-md border border-border bg-panel-muted p-3">
              <div className="flex flex-wrap items-center gap-2">
                <div className="text-sm font-semibold text-foreground">{approval.action}</div>
                <Badge
                  className={cn(
                    approval.risk === "high" && "border-danger/40 bg-danger/10 text-danger",
                    approval.risk === "medium" && "border-warning/40 bg-warning/10 text-warning",
                  )}
                >
                  {translateDynamic(language, approval.risk)}
                </Badge>
                <Badge>{translateDynamic(language, approval.status)}</Badge>
              </div>
              <Button className="mt-2" variant="secondary" disabled type="button">
                {t("supervisor.approval_required")}
              </Button>
            </div>
          ))}
          {surface.approvalRequests.length === 0 ? (
            <div className="rounded-md border border-dashed border-border bg-panel-muted px-3 py-2 text-sm text-muted">
              —
            </div>
          ) : null}
        </div>
      </div>

      <div>
        <h4 className="text-xs font-semibold uppercase tracking-widest text-muted">
          {t("supervisor.raw.tools")}
        </h4>
        <div className="mt-2 space-y-2">
          {surface.toolCalls.map((call) => (
            <div key={call.id} className="rounded-md border border-border bg-panel-muted p-3">
              <div className="flex flex-wrap items-center gap-2">
                <div className="text-sm font-semibold text-foreground">{call.tool}</div>
                <Badge>{translateDynamic(language, call.status)}</Badge>
                {call.dryRun ? <Badge>{t("common.dry_run")}</Badge> : null}
              </div>
              <div className="mt-2 text-xs leading-5 text-muted">{call.reason}</div>
            </div>
          ))}
          {surface.toolCalls.length === 0 ? (
            <div className="rounded-md border border-dashed border-border bg-panel-muted px-3 py-2 text-sm text-muted">
              —
            </div>
          ) : null}
        </div>
      </div>

      <div>
        <h4 className="text-xs font-semibold uppercase tracking-widest text-muted">
          {t("supervisor.raw.logs")}
        </h4>
        <div className="mt-2 space-y-2 text-sm leading-6 text-muted">
          {surface.logs.map((line) => (
            <div key={line} className="rounded-md border border-border bg-panel-muted px-3 py-2">
              {line}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function toPlainSnapshot(surface: SupervisorSurface): RawSnapshot {
  return {
    mode: surface.mode,
    workflow: { ...surface.workflow },
    agentTasks: surface.agentTasks.map((task) => ({ ...task })),
    steps: surface.steps.map((step) => ({ ...step })),
    toolCalls: surface.toolCalls.map((call) => ({ ...call })),
    approvalRequests: surface.approvalRequests.map((approval) => ({ ...approval })),
    logs: [...surface.logs],
  } as unknown as RawSnapshot;
}
