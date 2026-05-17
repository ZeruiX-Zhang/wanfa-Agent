"use client";

import { useEffect, useState } from "react";

import { CalibrationCurve } from "@/components/dashboard/CalibrationCurve";
import { ConceptDecay } from "@/components/dashboard/ConceptDecay";
import { Filters } from "@/components/dashboard/Filters";
import { MasteryHeatmap } from "@/components/dashboard/MasteryHeatmap";
import { SkillChainCompletion } from "@/components/dashboard/SkillChainCompletion";
import { usePreferences } from "@/components/preferences-provider";
import { dashboardApi } from "@/lib/api-v2";

/**
 * Learning dashboard (R10).
 *
 * Simple_Mode renders at most three panels with no controls (R10.2,
 * R10.3); Professional_Mode adds the concept-decay panel plus the
 * domain filter (R10.4).
 */
export function LearningDashboard() {
  const { preferences, t } = usePreferences();
  const isPro = preferences.mode === "professional";
  const [domains, setDomains] = useState<string[]>([]);
  const [domainFilter, setDomainFilter] = useState("");

  useEffect(() => {
    if (!isPro) return;
    let active = true;
    dashboardApi
      .mastery()
      .then((result) => {
        if (active) setDomains(result.domains.map((group) => group.domain));
      })
      .catch(() => {
        if (active) setDomains([]);
      });
    return () => {
      active = false;
    };
  }, [isPro]);

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-foreground">{t("dash.title")}</h2>
        {isPro && (
          <Filters
            domains={domains}
            value={domainFilter}
            onChange={setDomainFilter}
          />
        )}
      </div>
      <div className="grid gap-3 lg:grid-cols-2">
        <MasteryHeatmap domainFilter={isPro ? domainFilter || undefined : undefined} />
        <CalibrationCurve detailed={isPro} />
        <SkillChainCompletion detailed={isPro} />
        {isPro && <ConceptDecay />}
      </div>
    </section>
  );
}
