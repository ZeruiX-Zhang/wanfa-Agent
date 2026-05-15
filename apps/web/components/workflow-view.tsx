"use client";

import { usePreferences } from "@/components/preferences-provider";
import { RealityWorkspacePage } from "@/components/reality-workspace-page";
import { Badge, Panel } from "@/components/ui";
import { translateDynamic } from "@/lib/i18n";
import type { SupervisorSurface } from "@/lib/reality-adapter-data";

export function WorkflowView({ surface }: { surface: SupervisorSurface }) {
  const { preferences, t } = usePreferences();
  const language = preferences.language;
  return (
    <div className="space-y-5">
      <RealityWorkspacePage configKey="workflow" />
      <Panel>
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-sm font-semibold text-foreground">{surface.workflow.name}</h2>
          <Badge>{translateDynamic(language, surface.workflow.status)}</Badge>
          <Badge>{t("common.tool_gateway_disabled")}</Badge>
        </div>
      </Panel>
      <Panel>
        <h2 className="text-sm font-semibold text-foreground">{t("workflow.steps.title")}</h2>
        <div className="mt-3 grid gap-3 md:grid-cols-3">
          {surface.steps.map((step) => (
            <div className="rounded-md border border-border bg-panel-muted p-3" key={step.id}>
              <div className="text-sm font-semibold text-foreground">{step.label}</div>
              <div className="mt-2 text-xs text-muted">{translateDynamic(language, step.status)}</div>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}
