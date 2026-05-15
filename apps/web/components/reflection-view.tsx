"use client";

import { usePreferences } from "@/components/preferences-provider";
import { PendingKnowledgePanel } from "@/components/pending-knowledge-panel";
import { RealityWorkspacePage } from "@/components/reality-workspace-page";
import { Badge, Panel } from "@/components/ui";
import { translateDynamic } from "@/lib/i18n";
import type { getReflectionSurface } from "@/lib/reality-adapter-data";

type ReflectionSurface = Awaited<ReturnType<typeof getReflectionSurface>>;

export function ReflectionView({ surface }: { surface: ReflectionSurface }) {
  const { preferences, t } = usePreferences();
  const language = preferences.language;
  return (
    <div className="space-y-5">
      <RealityWorkspacePage configKey="reflection" />
      <Panel>
        <h2 className="text-sm font-semibold text-foreground">{t("reflection.records.title")}</h2>
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          {surface.records.map((record) => (
            <div className="rounded-md border border-border bg-panel-muted p-3" key={record.id}>
              <div className="flex flex-wrap items-center gap-2">
                <div className="text-sm font-semibold text-foreground">{record.title}</div>
                <Badge>{translateDynamic(language, record.status)}</Badge>
              </div>
              <div className="mt-2 text-sm leading-6 text-muted">{record.detail}</div>
            </div>
          ))}
        </div>
      </Panel>
      <Panel>
        <h2 className="text-sm font-semibold text-foreground">{t("reflection.pending.title")}</h2>
        <div className="mt-3">
          <PendingKnowledgePanel writes={surface.pendingWrites} />
        </div>
      </Panel>
    </div>
  );
}
