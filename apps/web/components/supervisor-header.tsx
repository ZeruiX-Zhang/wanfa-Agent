"use client";

import { usePreferences } from "@/components/preferences-provider";
import { Badge, Panel } from "@/components/ui";
import { translateDynamic } from "@/lib/i18n";
import type { SupervisorSurface } from "@/lib/reality-adapter-data";

export function SupervisorHeader({ surface }: { surface: SupervisorSurface }) {
  const { preferences } = usePreferences();
  const language = preferences.language;
  return (
    <Panel>
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-sm font-semibold text-foreground">{surface.workflow.name}</h2>
        <Badge>{translateDynamic(language, surface.workflow.status)}</Badge>
        <Badge>{translateDynamic(language, surface.mode)}</Badge>
      </div>
    </Panel>
  );
}
