"use client";

import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, Bot, Cpu, Loader2, Shield, Sparkles } from "lucide-react";
import { useState } from "react";

import { usePreferences } from "@/components/preferences-provider";
import { Badge, Button, Input, Panel } from "@/components/ui";
import { translateDynamic } from "@/lib/i18n";
import { v2 } from "@/lib/api-v2";
import { cn } from "@/lib/utils";

export function SuperviseView() {
  const { preferences, t } = usePreferences();
  const [provider, setProvider] = useState("server-configured");
  const [model, setModel] = useState("server-configured");

  const digestMutation = useMutation({
    mutationFn: () =>
      v2.superviseDigest({
        language: preferences.language,
        snapshot: {
          workflow: { id: "local", name: "Local supervisor", status: "idle" },
          agentTasks: [],
          steps: [],
          approvalRequests: [],
          toolCalls: [],
          logs: [],
          mode: "mock-safe",
        },
      }),
  });

  const probeMutation = useMutation({
    mutationFn: () => v2.modelsProbe({ language: preferences.language, provider, model }),
  });

  const digest = digestMutation.data;
  const probe = probeMutation.data;

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-2 border-b border-border pb-5">
        <div className="text-xs font-semibold uppercase tracking-widest text-muted">Reality OS</div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">{t("supervise.title")}</h1>
        <p className="max-w-3xl text-sm leading-6 text-muted">{t("supervise.subtitle")}</p>
      </header>

      <Panel className="border-accent/40">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-accent" aria-hidden="true" />
            <h2 className="text-sm font-semibold text-foreground">{t("supervise.digest.goal")}</h2>
          </div>
          <Button variant="secondary" onClick={() => digestMutation.mutate()} disabled={digestMutation.isPending}>
            {digestMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            ) : (
              <Bot className="h-4 w-4" aria-hidden="true" />
            )}
            {t("supervise.digest.refresh")}
          </Button>
        </div>
        {digest ? (
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <DigestField label={t("supervise.digest.goal")} value={digest.goal} />
            <DigestField label={t("supervise.digest.next")} value={digest.single_next_action} />
            <DigestField label={t("supervise.digest.drift")} value={digest.drift_alert} />
            <DigestField label={t("supervise.digest.waiting")} value={String(digest.approvals_waiting)} />
          </div>
        ) : (
          <div className="mt-4 rounded-md border border-dashed border-border bg-panel-muted px-3 py-6 text-sm text-muted">
            {t("supervise.digest.empty")}
          </div>
        )}

        {digest?.blocked_on.length ? (
          <div className="mt-4">
            <div className="text-[11px] font-semibold uppercase tracking-widest text-muted">
              {t("supervise.digest.blocked")}
            </div>
            <ul className="mt-2 space-y-1 text-sm text-foreground/90">
              {digest.blocked_on.map((b) => (
                <li key={b} className="flex items-start gap-2">
                  <AlertTriangle className="mt-0.5 h-4 w-4 text-warning" aria-hidden="true" />
                  <span>{b}</span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </Panel>

      <Panel>
        <div className="flex items-center gap-2">
          <Cpu className="h-4 w-4 text-accent" aria-hidden="true" />
          <h2 className="text-sm font-semibold text-foreground">{t("supervise.probe.title")}</h2>
        </div>
        <p className="mt-1 text-sm text-muted">{t("supervise.probe.desc")}</p>

        <div className="mt-4 grid gap-3 md:grid-cols-3">
          <Input value={provider} onChange={(e) => setProvider(e.target.value)} placeholder="openai" />
          <Input value={model} onChange={(e) => setModel(e.target.value)} placeholder="gpt-4.1" />
          <Button onClick={() => probeMutation.mutate()} disabled={probeMutation.isPending}>
            {probeMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            ) : (
              <Shield className="h-4 w-4" aria-hidden="true" />
            )}
            {t("supervise.probe.current")}
          </Button>
        </div>

        {probe ? (
          <div className="mt-4 space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <Badge
                className={cn(
                  "uppercase",
                  probe.tier === "flagship" && "border-success/40 bg-success/10 text-success",
                  probe.tier === "mid" && "border-accent/40 bg-accent-soft text-foreground",
                  probe.tier === "basic" && "border-warning/40 bg-warning/10 text-warning",
                  probe.tier === "insufficient" && "border-danger/40 bg-danger/10 text-danger",
                )}
              >
                {t(`settings.section.model_test.tier.${probe.tier}`)}
              </Badge>
              <span className="text-sm text-muted">
                {t("supervise.probe.tier")}: {Math.round(probe.aggregate_score * 100)}%
              </span>
            </div>
            <div className="rounded-md border border-border bg-panel-muted p-3 text-sm text-foreground/90">
              <div className="text-[11px] font-semibold uppercase tracking-widest text-muted">
                {t("supervise.probe.recommendation")}
              </div>
              <div className="mt-1">{probe.recommendation}</div>
              <div className="mt-2 text-xs text-muted">
                {t("settings.section.model_test.strategy.prompt_strategy")}:{" "}
                {translateDynamic(preferences.language, probe.workflow_strategy.prompt_strategy) ||
                  probe.workflow_strategy.prompt_strategy}
              </div>
            </div>
          </div>
        ) : null}
      </Panel>
    </div>
  );
}

function DigestField({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border bg-panel p-3">
      <div className="text-[11px] font-semibold uppercase tracking-widest text-muted">{label}</div>
      <div className="mt-1 text-sm text-foreground">{value}</div>
    </div>
  );
}
