"use client";

import { usePreferences } from "@/components/preferences-provider";
import { EvidenceTable } from "@/components/reality-adapter-ui";
import { RealityWorkspacePage } from "@/components/reality-workspace-page";
import { Badge, Panel } from "@/components/ui";
import { translateDynamic } from "@/lib/i18n";
import type { DecisionCase } from "@/lib/reality-adapter-data";

export function DecisionView({ id, decision }: { id: string; decision: DecisionCase }) {
  const { preferences, t } = usePreferences();
  const language = preferences.language;
  const confidencePercent = Math.round(decision.memo.confidence * 100);
  return (
    <div className="space-y-5">
      <RealityWorkspacePage configKey="decision" referenceId={id} />
      <Panel>
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-sm font-semibold text-foreground">{decision.decisionCase.title}</h2>
          <Badge>{translateDynamic(language, decision.decisionCase.status)}</Badge>
          <Badge>{translateDynamic(language, decision.mode)}</Badge>
        </div>
        <p className="mt-3 text-sm leading-6 text-muted">{decision.decisionCase.rawInput}</p>
      </Panel>
      <Panel>
        <h2 className="text-sm font-semibold text-foreground">{t("decision.clarified.title")}</h2>
        <p className="mt-3 text-sm leading-6 text-muted">{decision.clarifiedProblem.question}</p>
        <div className="mt-3 rounded-md border border-border bg-panel-muted p-3 text-sm text-muted">
          {t("decision.clarified.scope").replace("{scope}", decision.clarifiedProblem.scope)}
        </div>
        <div className="mt-3 grid gap-2 md:grid-cols-3">
          {decision.clarifiedProblem.assumptions.map((item) => (
            <div className="rounded-md border border-border px-3 py-2 text-sm" key={item}>
              {item}
            </div>
          ))}
        </div>
      </Panel>
      <Panel>
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-sm font-semibold text-foreground">{t("decision.memo.title")}</h2>
          <Badge>{translateDynamic(language, decision.memo.status)}</Badge>
          <Badge>{t("decision.memo.confidence").replace("{percent}", String(confidencePercent))}</Badge>
        </div>
        {decision.memo.insufficientEvidence ? (
          <div className="mt-3 rounded-md border border-warning/40 bg-warning/10 p-3 text-sm font-medium text-warning">
            {t("decision.memo.insufficient")}
          </div>
        ) : null}
        <p className="mt-3 text-sm leading-6 text-muted">{decision.memo.recommendation}</p>
      </Panel>
      <Panel>
        <h2 className="text-sm font-semibold text-foreground">{t("decision.evidence.title")}</h2>
        <div className="mt-3">
          <EvidenceTable rows={decision.memo.evidence} />
        </div>
      </Panel>
      <div className="grid gap-4 xl:grid-cols-2">
        <Panel>
          <h2 className="text-sm font-semibold text-foreground">{t("decision.counterargs.title")}</h2>
          <ul className="mt-3 space-y-2 text-sm leading-6 text-muted">
            {decision.memo.counterarguments.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </Panel>
        <Panel>
          <h2 className="text-sm font-semibold text-foreground">{t("decision.risks.title")}</h2>
          <ul className="mt-3 space-y-2 text-sm leading-6 text-muted">
            {decision.memo.risks.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </Panel>
      </div>
    </div>
  );
}
