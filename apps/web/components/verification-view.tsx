"use client";

import { usePreferences } from "@/components/preferences-provider";
import { EvidenceTable, TraceList } from "@/components/reality-adapter-ui";
import { RealityWorkspacePage } from "@/components/reality-workspace-page";
import { Badge, Panel } from "@/components/ui";
import { translateDynamic } from "@/lib/i18n";
import type { VerificationSurface } from "@/lib/reality-adapter-data";

export function VerificationView({ id, surface }: { id: string; surface: VerificationSurface }) {
  const { preferences, t } = usePreferences();
  const language = preferences.language;
  const confidencePercent = Math.round(surface.claim.confidence * 100);
  const passPercent = Math.round(surface.evalSummary.passRate * 100);
  return (
    <div className="space-y-5">
      <RealityWorkspacePage configKey="verification" referenceId={id} />
      <Panel>
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-sm font-semibold text-foreground">{t("verification.claim.title")}</h2>
          <Badge>{translateDynamic(language, surface.claim.status)}</Badge>
          <Badge>{t("verification.claim.confidence").replace("{percent}", String(confidencePercent))}</Badge>
        </div>
        <p className="mt-3 text-sm leading-6 text-muted">{surface.claim.text}</p>
        {surface.claim.insufficientEvidence ? (
          <div className="mt-3 rounded-md border border-warning/40 bg-warning/10 p-3 text-sm text-warning">
            {t("verification.claim.insufficient")}
          </div>
        ) : null}
      </Panel>
      <Panel>
        <h2 className="text-sm font-semibold text-foreground">{t("verification.evidence.title")}</h2>
        <div className="mt-3">
          <EvidenceTable rows={surface.evidence} />
        </div>
      </Panel>
      <div className="grid gap-4 xl:grid-cols-2">
        <Panel>
          <h2 className="text-sm font-semibold text-foreground">{t("verification.eval.title")}</h2>
          <div className="mt-3 text-sm leading-6 text-muted">
            {t("verification.eval.detail")
              .replace("{status}", translateDynamic(language, surface.evalSummary.status))
              .replace("{pass}", String(passPercent))}
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {surface.evalSummary.failingChecks.map((item) => (
              <Badge key={item}>{translateDynamic(language, item)}</Badge>
            ))}
          </div>
        </Panel>
        <Panel>
          <h2 className="text-sm font-semibold text-foreground">{t("verification.trace.title")}</h2>
          <div className="mt-3">
            <TraceList trace={surface.trace} />
          </div>
        </Panel>
      </div>
    </div>
  );
}
