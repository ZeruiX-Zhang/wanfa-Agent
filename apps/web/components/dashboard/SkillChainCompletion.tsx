"use client";

import { useEffect, useState } from "react";

import { usePreferences } from "@/components/preferences-provider";
import { Panel } from "@/components/ui";
import { dashboardApi, type DashboardSkillChain } from "@/lib/api-v2";

export function SkillChainCompletion({ detailed = false }: { detailed?: boolean }) {
  const { t } = usePreferences();
  const [data, setData] = useState<DashboardSkillChain | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    dashboardApi
      .skillChain()
      .then((result) => active && setData(result))
      .catch((err: unknown) => active && setError(String(err)));
    return () => {
      active = false;
    };
  }, []);

  return (
    <Panel>
      <div className="text-xs font-semibold uppercase tracking-normal text-muted">
        {t("dash.skill_chain")}
      </div>
      {error ? (
        <div className="mt-2 text-xs text-rose-300">{error}</div>
      ) : !data || data.problem_types.length === 0 ? (
        <div className="mt-2 text-xs text-muted">{t("dash.empty")}</div>
      ) : (
        <div className="mt-3 space-y-3">
          {data.problem_types.map((entry) => (
            <div key={entry.problem_type}>
              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold text-foreground">
                  {entry.problem_type}
                </span>
                <span className="text-muted">
                  {Math.round(entry.avg_completion * 100)}%
                </span>
              </div>
              <div className="mt-1 h-2 rounded bg-white/10">
                <div
                  className="h-2 rounded bg-indigo-500/70"
                  style={{ width: `${entry.avg_completion * 100}%` }}
                />
              </div>
              {/* Professional_Mode adds per-step retention. */}
              {detailed && (
                <div className="mt-1 flex gap-1">
                  {entry.step_retention.map((retention, index) => (
                    <span
                      key={index}
                      className="text-[10px] text-muted"
                      title={`step ${index + 1}`}
                    >
                      {Math.round(retention * 100)}%
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
}
