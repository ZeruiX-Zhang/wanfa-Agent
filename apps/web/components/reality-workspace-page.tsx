"use client";

import { usePreferences } from "@/components/preferences-provider";
import { Badge, Panel } from "@/components/ui";
import { workspaceConfig, type WorkspaceKey, type WorkspaceStatus } from "@/lib/reality-workspaces";
import { cn } from "@/lib/utils";

export function RealityWorkspacePage({
  configKey,
  referenceId,
}: {
  configKey: WorkspaceKey;
  referenceId?: string;
}) {
  const { preferences, t } = usePreferences();
  const config = workspaceConfig(configKey, preferences.language);
  const statusLabel: Record<WorkspaceStatus, string> = {
    ready: t("workspace.status.ready"),
    planned: t("workspace.status.planned"),
    "adapter-next": t("workspace.status.adapter-next"),
  };

  return (
    <div className="space-y-5">
      <header className="flex flex-col gap-3 border-b border-border pb-5 md:flex-row md:items-end md:justify-between">
        <div>
          <div className="text-xs font-semibold uppercase tracking-normal text-muted">{config.eyebrow}</div>
          <h1 className="mt-1 text-2xl font-bold tracking-normal text-foreground">{config.title}</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">{config.description}</p>
          {referenceId ? (
            <div className="mt-2 text-xs text-muted">
              {t("common.reference_id")}: {referenceId}
            </div>
          ) : null}
        </div>
        <Badge
          className={cn(
            "w-fit",
            config.status === "ready" && "border-success/40 bg-success/10 text-success",
            config.status === "adapter-next" && "border-accent/40 bg-accent-soft text-foreground",
            config.status === "planned" && "border-warning/40 bg-warning/10 text-warning",
          )}
        >
          {statusLabel[config.status]}
        </Badge>
      </header>

      <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <Panel>
          <h2 className="text-sm font-semibold text-foreground">{t("workspace.scope")}</h2>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            {config.currentScope.map((item) => (
              <div
                className="rounded-md border border-border bg-panel-muted p-3 text-sm leading-6 text-foreground/80"
                key={item}
              >
                {item}
              </div>
            ))}
          </div>
        </Panel>

        <Panel>
          <h2 className="text-sm font-semibold text-foreground">{t("workspace.legacy")}</h2>
          <ul className="mt-3 space-y-2 text-sm leading-6 text-muted">
            {config.legacySources.map((source) => (
              <li className="flex gap-2" key={source}>
                <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
                <span>{source}</span>
              </li>
            ))}
          </ul>
        </Panel>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Panel>
          <h2 className="text-sm font-semibold text-foreground">{t("workspace.next")}</h2>
          <ul className="mt-3 space-y-2 text-sm leading-6 text-muted">
            {config.nextAdapters.map((adapter) => (
              <li className="rounded-md border border-border px-3 py-2" key={adapter}>
                {adapter}
              </li>
            ))}
          </ul>
        </Panel>

        <Panel>
          <h2 className="text-sm font-semibold text-foreground">{t("workspace.acceptance")}</h2>
          <ul className="mt-3 space-y-2 text-sm leading-6 text-muted">
            {config.acceptance.map((item) => (
              <li className="flex gap-2" key={item}>
                <span className="mt-1.5 inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full border border-accent/40 text-[10px] text-accent">
                  ✓
                </span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </Panel>
      </div>
    </div>
  );
}
