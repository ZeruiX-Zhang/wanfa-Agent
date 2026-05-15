"use client";

import { usePreferences } from "@/components/preferences-provider";
import { AdapterStatusPanel } from "@/components/reality-adapter-ui";
import { RealityWorkspacePage } from "@/components/reality-workspace-page";
import { Panel } from "@/components/ui";
import type { Awaitable } from "@/lib/types-util";
import type { getDashboardSurface } from "@/lib/reality-adapter-data";

type DashboardSurface = Awaited<ReturnType<typeof getDashboardSurface>>;

export function DashboardView({ surface }: { surface: DashboardSurface }) {
  const { t } = usePreferences();
  const metrics = [
    {
      label: t("dashboard.metric.sources"),
      value: surface.metrics.sources,
      detail: t("dashboard.metric.sources.detail"),
    },
    {
      label: t("dashboard.metric.evidence"),
      value: surface.metrics.evidence,
      detail: t("dashboard.metric.evidence.detail"),
    },
    {
      label: t("dashboard.metric.objects"),
      value: surface.metrics.intelligenceObjects,
      detail: t("dashboard.metric.objects.detail"),
    },
    {
      label: t("dashboard.metric.pending"),
      value: surface.metrics.pendingWrites,
      detail: t("dashboard.metric.pending.detail"),
    },
  ];

  return (
    <div className="space-y-5">
      <RealityWorkspacePage configKey="dashboard" />
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {metrics.map((metric) => (
          <Panel key={metric.label}>
            <div className="text-xs font-semibold uppercase tracking-normal text-muted">{metric.label}</div>
            <div className="mt-2 text-2xl font-bold text-foreground">{metric.value}</div>
            <div className="mt-1 text-xs leading-5 text-muted">{metric.detail}</div>
          </Panel>
        ))}
      </div>
      <AdapterStatusPanel mode={surface.sou.mode} statuses={surface.sou.statuses} />
      <Panel>
        <h2 className="text-sm font-semibold text-foreground">{t("dashboard.safety.title")}</h2>
        <div className="mt-3 grid gap-3 text-sm leading-6 text-muted md:grid-cols-2">
          <div>{t("dashboard.safety.api_keys")}</div>
          <div>{t("dashboard.safety.tools")}</div>
          <div>{t("dashboard.safety.writes")}</div>
          <div>{t("dashboard.safety.external")}</div>
        </div>
      </Panel>
    </div>
  );
}

type _UnusedAwaitable = Awaitable<void>;
