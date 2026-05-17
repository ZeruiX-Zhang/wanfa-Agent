"use client";

import { useEffect, useState } from "react";

import { usePreferences } from "@/components/preferences-provider";
import { Panel } from "@/components/ui";
import { dashboardApi, type DashboardMastery } from "@/lib/api-v2";

function masteryTone(score: number): string {
  if (score >= 0.75) return "bg-emerald-500/30 text-emerald-200";
  if (score >= 0.5) return "bg-amber-500/30 text-amber-100";
  return "bg-rose-500/30 text-rose-100";
}

export function MasteryHeatmap({ domainFilter }: { domainFilter?: string }) {
  const { t } = usePreferences();
  const [data, setData] = useState<DashboardMastery | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    dashboardApi
      .mastery()
      .then((result) => active && setData(result))
      .catch((err: unknown) => active && setError(String(err)));
    return () => {
      active = false;
    };
  }, []);

  const domains = (data?.domains ?? []).filter(
    (group) => !domainFilter || group.domain === domainFilter,
  );

  return (
    <Panel>
      <div className="text-xs font-semibold uppercase tracking-normal text-muted">
        {t("dash.mastery")}
      </div>
      {error ? (
        <div className="mt-2 text-xs text-rose-300">{error}</div>
      ) : !data || domains.length === 0 ? (
        <div className="mt-2 text-xs text-muted">{t("dash.empty")}</div>
      ) : (
        <div className="mt-3 space-y-3">
          {domains.map((group) => (
            <div key={group.domain}>
              <div className="flex items-center justify-between text-xs text-muted">
                <span className="font-semibold text-foreground">{group.domain}</span>
                <span>{Math.round(group.avg_mastery * 100)}%</span>
              </div>
              <div className="mt-1 flex flex-wrap gap-1">
                {group.concepts.map((concept) => (
                  <span
                    key={concept.id}
                    title={`${concept.label}: ${Math.round(concept.mastery_score * 100)}%`}
                    className={`rounded px-2 py-1 text-[11px] ${masteryTone(concept.mastery_score)}`}
                  >
                    {concept.label}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
}
