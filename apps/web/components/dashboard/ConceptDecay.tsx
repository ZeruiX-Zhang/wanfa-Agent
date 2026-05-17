"use client";

import { useEffect, useState } from "react";

import { usePreferences } from "@/components/preferences-provider";
import { Panel } from "@/components/ui";
import { dashboardApi, type DashboardDecay } from "@/lib/api-v2";

export function ConceptDecay() {
  const { t } = usePreferences();
  const [data, setData] = useState<DashboardDecay | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    dashboardApi
      .decay()
      .then((result) => active && setData(result))
      .catch((err: unknown) => active && setError(String(err)));
    return () => {
      active = false;
    };
  }, []);

  return (
    <Panel>
      <div className="text-xs font-semibold uppercase tracking-normal text-muted">
        {t("dash.decay")}
      </div>
      {error ? (
        <div className="mt-2 text-xs text-rose-300">{error}</div>
      ) : !data || data.curves.length === 0 ? (
        <div className="mt-2 text-xs text-muted">{t("dash.empty")}</div>
      ) : (
        <div className="mt-3 space-y-3">
          {data.curves.map((curve) => (
            <div key={curve.concept_id}>
              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold text-foreground">{curve.label}</span>
                <span className="text-muted">
                  {new Date(curve.last_practiced_at).toLocaleDateString()}
                </span>
              </div>
              <div className="mt-1 flex items-end gap-1">
                {curve.projection.map((point) => (
                  <div
                    key={point.day}
                    title={`day ${point.day}: ${Math.round(point.score * 100)}%`}
                    className="w-4 rounded-t bg-fuchsia-500/40"
                    style={{ height: `${Math.max(3, point.score * 56)}px` }}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
}
