"use client";

import { usePreferences } from "@/components/preferences-provider";
import { AdapterStatusPanel, EvidenceTable, TraceList } from "@/components/reality-adapter-ui";
import { RealityWorkspacePage } from "@/components/reality-workspace-page";
import { Badge, Panel } from "@/components/ui";
import { translateDynamic } from "@/lib/i18n";
import type { SearchSurface } from "@/lib/reality-adapter-data";

export function SearchView({ surface }: { surface: SearchSurface }) {
  const { preferences, t } = usePreferences();
  const language = preferences.language;
  return (
    <div className="space-y-5">
      <RealityWorkspacePage configKey="search" />
      <AdapterStatusPanel
        mode={surface.mode}
        statuses={[
          {
            name: t("search.adapter.name"),
            mode: surface.mode,
            detail: t("search.adapter.detail"),
          },
        ]}
      />
      <Panel>
        <h2 className="text-sm font-semibold text-foreground">{t("search.adapter.title")}</h2>
        <div className="mt-3 grid gap-3 text-sm leading-6 text-muted md:grid-cols-3">
          <div>{t("search.adapter.mode_label")}</div>
          <div>
            {t("search.adapter.eval_label")} {translateDynamic(language, surface.evalSummary.status)}
          </div>
          <div>{t("search.adapter.empty_policy")}</div>
        </div>
      </Panel>
      <Panel>
        <h2 className="text-sm font-semibold text-foreground">{t("search.results.title")}</h2>
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          {surface.results.length === 0 ? (
            <div className="rounded-md border border-warning/40 bg-warning/10 p-3 text-sm text-warning">
              {t("search.results.empty")}
            </div>
          ) : (
            surface.results.map((result) => (
              <div className="rounded-md border border-border bg-panel-muted p-3" key={result.id}>
                <div className="flex flex-wrap items-center gap-2">
                  <div className="text-sm font-semibold text-foreground">{result.title}</div>
                  <Badge>{translateDynamic(language, result.verificationStatus)}</Badge>
                </div>
                <p className="mt-2 text-sm leading-6 text-muted">{result.summary}</p>
              </div>
            ))
          )}
        </div>
      </Panel>
      <Panel>
        <h2 className="text-sm font-semibold text-foreground">{t("search.evidence.title")}</h2>
        <div className="mt-3">
          <EvidenceTable rows={surface.evidence} />
        </div>
      </Panel>
      <Panel>
        <h2 className="text-sm font-semibold text-foreground">{t("search.trace.title")}</h2>
        <div className="mt-3">
          <TraceList trace={surface.trace} />
        </div>
      </Panel>
    </div>
  );
}
