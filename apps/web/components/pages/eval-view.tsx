"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, AlertTriangle, CheckCircle2, Loader2, RefreshCw } from "lucide-react";

import { usePreferences } from "@/components/preferences-provider";
import { Badge, Button, Panel } from "@/components/ui";
import { v2 } from "@/lib/api-v2";
import { cn } from "@/lib/utils";

export function EvalView() {
  const { preferences, t } = usePreferences();
  const queryClient = useQueryClient();
  const dashboardQuery = useQuery({
    queryKey: ["v2", "eval", "dashboard"],
    queryFn: () => v2.evalDashboard(),
  });

  const metrics = dashboardQuery.data?.metrics ?? [];
  const meaningful = metrics.filter((m) => m.tier !== "unknown");

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-2 border-b border-border pb-5 md:flex-row md:items-end md:justify-between">
        <div>
          <div className="text-xs font-semibold uppercase tracking-widest text-muted">Reality OS</div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">{t("eval.title")}</h1>
          <p className="max-w-3xl text-sm leading-6 text-muted">{t("eval.subtitle")}</p>
        </div>
        <Button
          variant="secondary"
          onClick={() => queryClient.invalidateQueries({ queryKey: ["v2", "eval"] })}
          disabled={dashboardQuery.isFetching}
        >
          {dashboardQuery.isFetching ? (
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          ) : (
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
          )}
          {t("eval.refresh")}
        </Button>
      </header>

      {meaningful.length === 0 && !dashboardQuery.isPending ? (
        <Panel className="text-sm text-muted">{t("eval.empty")}</Panel>
      ) : null}

      <div className="grid gap-3 md:grid-cols-2">
        {metrics.map((metric) => {
          const label = preferences.language === "zh-CN" ? metric.label_zh : metric.label_en;
          const description = preferences.language === "zh-CN" ? metric.description_zh : metric.description_en;
          return (
            <Panel key={metric.id}>
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="flex items-center gap-2">
                    <Activity className="h-4 w-4 text-accent" aria-hidden="true" />
                    <h2 className="text-sm font-semibold text-foreground">{label}</h2>
                  </div>
                  <p className="mt-1 max-w-md text-sm leading-6 text-muted">{description}</p>
                </div>
                <TierPill tier={metric.tier} label={t(`eval.tier.${metric.tier}`)} />
              </div>

              <div className="mt-4 flex items-end gap-4">
                <div className="text-3xl font-bold text-foreground">
                  {metric.sample_size === 0 ? "—" : `${Math.round(metric.value * 100)}%`}
                </div>
                <div className="flex-1">
                  <div className="h-2 overflow-hidden rounded-full bg-panel-muted">
                    <div
                      className={cn(
                        "h-full rounded-full transition-all",
                        metric.tier === "green" && "bg-success",
                        metric.tier === "amber" && "bg-warning",
                        metric.tier === "red" && "bg-danger",
                        metric.tier === "unknown" && "bg-border",
                      )}
                      style={{
                        width: `${Math.max(2, Math.min(100, Math.round(metric.value * 100)))}%`,
                      }}
                    />
                  </div>
                  <div className="mt-1 flex items-center justify-between text-xs text-muted">
                    <span>
                      {t("eval.sample_size")}: {metric.sample_size}
                    </span>
                    {metric.sample_size > 0 && metric.sample_size < 5 ? (
                      <span className="inline-flex items-center gap-1 text-warning">
                        <AlertTriangle className="h-3 w-3" aria-hidden="true" />
                        {t("eval.sample_low")}
                      </span>
                    ) : null}
                  </div>
                </div>
              </div>
            </Panel>
          );
        })}
      </div>
    </div>
  );
}

function TierPill({ tier, label }: { tier: string; label: string }) {
  const Icon = tier === "green" ? CheckCircle2 : tier === "amber" ? AlertTriangle : tier === "red" ? AlertTriangle : Activity;
  return (
    <Badge
      className={cn(
        "whitespace-nowrap",
        tier === "green" && "border-success/40 bg-success/10 text-success",
        tier === "amber" && "border-warning/40 bg-warning/10 text-warning",
        tier === "red" && "border-danger/40 bg-danger/10 text-danger",
        tier === "unknown" && "border-border bg-panel-muted text-muted",
      )}
    >
      <Icon className="h-3 w-3" aria-hidden="true" />
      {label}
    </Badge>
  );
}
