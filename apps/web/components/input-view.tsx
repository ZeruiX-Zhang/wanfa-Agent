"use client";

import { usePreferences } from "@/components/preferences-provider";
import { RealityWorkspacePage } from "@/components/reality-workspace-page";
import { VisionInput } from "@/components/vision-input";
import { Badge, Panel } from "@/components/ui";
import { translateDynamic } from "@/lib/i18n";
import type { CaptureSummary } from "@/lib/reality-adapter-data";

export function InputView({ summary }: { summary: CaptureSummary }) {
  const { preferences, t } = usePreferences();
  const language = preferences.language;
  return (
    <div className="space-y-5">
      <RealityWorkspacePage configKey="input" />
      <VisionInput />
      <Panel>
        <h2 className="text-sm font-semibold text-foreground">{t("input.entry.title")}</h2>
        <div className="mt-3 grid gap-3 md:grid-cols-3">
          {summary.entryPoints.map((entry) => (
            <div className="rounded-md border border-border bg-panel-muted p-3" key={entry.id}>
              <div className="flex flex-wrap items-center gap-2">
                <div className="text-sm font-semibold text-foreground">{entry.label}</div>
                <Badge>{translateDynamic(language, entry.status)}</Badge>
              </div>
              <div className="mt-2 text-sm leading-6 text-muted">{entry.detail}</div>
            </div>
          ))}
        </div>
      </Panel>
      <Panel>
        <h2 className="text-sm font-semibold text-foreground">{t("input.clarification.title")}</h2>
        <div className="mt-3 space-y-2">
          {summary.clarificationQuestions.map((item) => (
            <div className="rounded-md border border-border px-3 py-2 text-sm" key={item.id}>
              {item.question}
              {item.required ? (
                <span className="ml-2 text-xs text-muted">{t("common.required")}</span>
              ) : (
                <span className="ml-2 text-xs text-muted">{t("common.optional")}</span>
              )}
            </div>
          ))}
        </div>
      </Panel>
      <Panel>
        <h2 className="text-sm font-semibold text-foreground">{t("input.knowledge_os.title")}</h2>
        <div className="mt-3 text-sm leading-6 text-muted">
          {t("input.knowledge_os.status")}: {translateDynamic(language, summary.knowledgeOsSummary.status)} ·{" "}
          {t("input.knowledge_os.domains")}: {summary.knowledgeOsSummary.domains.join("、")}。{" "}
          {t("input.knowledge_os.desc")}
        </div>
      </Panel>
    </div>
  );
}
