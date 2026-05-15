"use client";

import { usePreferences } from "@/components/preferences-provider";
import { PendingKnowledgePanel } from "@/components/pending-knowledge-panel";
import { AdapterStatusPanel, EvidenceTable } from "@/components/reality-adapter-ui";
import { RealityWorkspacePage } from "@/components/reality-workspace-page";
import { Badge, Panel, Table, Td, Th } from "@/components/ui";
import { translateDynamic } from "@/lib/i18n";
import type { SouSurface } from "@/lib/reality-adapter-data";
import { pct } from "@/lib/utils";

export function KnowledgeView({ surface }: { surface: SouSurface }) {
  const { preferences, t } = usePreferences();
  const language = preferences.language;
  return (
    <div className="space-y-5">
      <RealityWorkspacePage configKey="knowledge" />
      <AdapterStatusPanel mode={surface.mode} statuses={surface.statuses} />
      <Panel>
        <h2 className="text-sm font-semibold text-foreground">{t("knowledge.sources.title")}</h2>
        <div className="mt-3 overflow-x-auto">
          <Table>
            <thead>
              <tr>
                <Th>{t("knowledge.sources.header.name")}</Th>
                <Th>{t("knowledge.sources.header.mode")}</Th>
                <Th>{t("knowledge.sources.header.compliance")}</Th>
                <Th>{t("knowledge.sources.header.trust")}</Th>
              </tr>
            </thead>
            <tbody>
              {surface.sources.map((source) => (
                <tr key={source.id}>
                  <Td>
                    <div className="font-medium text-foreground">{source.name}</div>
                    <div className="mt-1 text-xs text-muted">
                      {source.url ?? t("knowledge.sources.readonly_placeholder")}
                    </div>
                  </Td>
                  <Td>{translateDynamic(language, source.collectionMode)}</Td>
                  <Td>{translateDynamic(language, source.complianceStatus)}</Td>
                  <Td>{pct(source.trustScore, language)}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </div>
      </Panel>
      <Panel>
        <h2 className="text-sm font-semibold text-foreground">{t("knowledge.ledger.title")}</h2>
        <div className="mt-3">
          <EvidenceTable rows={surface.evidence} />
        </div>
      </Panel>
      <Panel>
        <h2 className="text-sm font-semibold text-foreground">{t("knowledge.objects.title")}</h2>
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          {surface.intelligenceObjects.map((item) => (
            <div className="rounded-md border border-border bg-panel-muted p-3" key={item.id}>
              <div className="flex flex-wrap items-center gap-2">
                <div className="text-sm font-semibold text-foreground">{item.title}</div>
                <Badge>{translateDynamic(language, item.verificationStatus)}</Badge>
              </div>
              <p className="mt-2 text-sm leading-6 text-muted">{item.summary}</p>
              <div className="mt-2 text-xs text-muted">
                {t("knowledge.objects.summary")
                  .replace("{count}", String(item.evidenceCount))
                  .replace("{score}", String(Math.round(item.aggregateScore * 100)))}
              </div>
            </div>
          ))}
        </div>
      </Panel>
      <Panel>
        <h2 className="text-sm font-semibold text-foreground">{t("knowledge.pending_queue.title")}</h2>
        <div className="mt-3">
          <PendingKnowledgePanel writes={surface.pendingWrites} />
        </div>
      </Panel>
    </div>
  );
}
