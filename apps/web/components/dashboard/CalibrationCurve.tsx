"use client";

import { useEffect, useState } from "react";

import { usePreferences } from "@/components/preferences-provider";
import { Panel } from "@/components/ui";
import { dashboardApi, type DashboardCalibration } from "@/lib/api-v2";

export function CalibrationCurve({ detailed = false }: { detailed?: boolean }) {
  const { t } = usePreferences();
  const [data, setData] = useState<DashboardCalibration | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    dashboardApi
      .calibration()
      .then((result) => active && setData(result))
      .catch((err: unknown) => active && setError(String(err)));
    return () => {
      active = false;
    };
  }, []);

  return (
    <Panel>
      <div className="text-xs font-semibold uppercase tracking-normal text-muted">
        {t("dash.calibration")}
      </div>
      {error ? (
        <div className="mt-2 text-xs text-rose-300">{error}</div>
      ) : !data ? (
        <div className="mt-2 text-xs text-muted">{t("dash.empty")}</div>
      ) : (
        <div className="mt-3 space-y-2">
          <div className="text-2xl font-bold text-foreground">
            {Math.round(data.calibration_score * 100)}%
          </div>
          {/* Simple_Mode shows only the score; Professional_Mode adds bins. */}
          {detailed && (
            <>
              <div className="text-xs text-muted">
                Brier: {data.brier_score === null ? "—" : data.brier_score.toFixed(3)} ·
                {" "}
                {data.resolved_count}/{data.total_count}
              </div>
              <div className="flex items-end gap-1">
                {data.bins.map((bin) => (
                  <div
                    key={bin.lo}
                    title={`[${bin.lo.toFixed(1)}, ${bin.hi.toFixed(1)}] n=${bin.count}`}
                    className="w-5 rounded-t bg-sky-500/40"
                    style={{ height: `${Math.max(4, bin.empirical_freq * 60)}px` }}
                  />
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </Panel>
  );
}
