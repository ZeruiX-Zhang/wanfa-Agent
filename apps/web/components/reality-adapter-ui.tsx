"use client";

import { AlertTriangle, Ban, RotateCcw } from "lucide-react";

import { usePreferences } from "@/components/preferences-provider";
import { StatusBadge } from "@/components/insight-ui";
import { Badge, Button, Panel, Table, Td, Th } from "@/components/ui";
import { translateDynamic } from "@/lib/i18n";
import type {
  AdapterMode,
  AdapterStatus,
  EvidenceRow,
  PendingKnowledgeWrite,
  RetrievalTraceStep,
} from "@/lib/reality-adapter-data";
import { fmtDate, pct } from "@/lib/utils";
import { cn } from "@/lib/utils";

export function AdapterModeBadge({ mode }: { mode: AdapterMode }) {
  const { t } = usePreferences();
  const label = t(`adapter.mode.${mode}`);
  return (
    <Badge
      className={cn(
        mode === "connected" && "border-success/40 bg-success/10 text-success",
        mode === "partial" && "border-warning/40 bg-warning/10 text-warning",
        (mode === "mock-safe" || mode === "empty") && "border-border bg-panel-muted text-foreground/80",
        mode === "blocked" && "border-danger/40 bg-danger/10 text-danger",
      )}
    >
      {label}
    </Badge>
  );
}

export function AdapterStatusPanel({
  mode,
  statuses,
}: {
  mode: AdapterMode;
  statuses: AdapterStatus[];
}) {
  const { preferences, t } = usePreferences();
  return (
    <Panel>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-foreground">{t("adapter.title")}</h2>
        <AdapterModeBadge mode={mode} />
      </div>
      <div className="grid gap-2 md:grid-cols-2">
        {statuses.map((status) => (
          <div className="rounded-md border border-border bg-panel-muted p-3" key={status.name}>
            <div className="flex items-center justify-between gap-2">
              <div className="text-sm font-medium text-foreground">{status.name}</div>
              <AdapterModeBadge mode={status.mode} />
            </div>
            <div className="mt-2 text-xs leading-5 text-muted">
              {localizeAdapterDetail(status.detail, preferences.language, t)}
            </div>
          </div>
        ))}
      </div>
    </Panel>
  );
}

const ADAPTER_DETAIL_MAP: Array<{ match: RegExp; key: string }> = [
  { match: /^Backend adapter data loaded\./i, key: "adapter.detail.loaded" },
  { match: /Using read-only source mock-safe rows/i, key: "adapter.detail.fallback.sources" },
  { match: /Using evidence ledger mock-safe rows/i, key: "adapter.detail.fallback.evidence" },
  { match: /Using intelligence object mock-safe rows/i, key: "adapter.detail.fallback.objects" },
  { match: /Using server-only settings summary/i, key: "adapter.detail.fallback.settings" },
  { match: /strict mode blocks mock fallback/i, key: "adapter.detail.blocked" },
  { match: /Search shows adapter data only/i, key: "search.adapter.detail" },
];

function localizeAdapterDetail(detail: string, language: string, t: (key: string) => string): string {
  for (const entry of ADAPTER_DETAIL_MAP) {
    if (entry.match.test(detail)) {
      return t(entry.key);
    }
  }
  // Bare-English adapter detail: pass through unchanged so operator output is still readable.
  return detail;
}

export function EvidenceTable({ rows }: { rows: EvidenceRow[] }) {
  const { preferences, t } = usePreferences();
  if (rows.length === 0) {
    return (
      <div className="rounded-md border border-warning/40 bg-warning/10 p-3 text-sm leading-6 text-warning">
        <div className="flex items-center gap-2 font-semibold">
          <AlertTriangle className="h-4 w-4" aria-hidden="true" />
          {t("evidence.empty.title")}
        </div>
        <div className="mt-1">{t("evidence.empty.desc")}</div>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <Table>
        <thead>
          <tr>
            <Th>{t("evidence.header.evidence")}</Th>
            <Th>{t("evidence.header.source")}</Th>
            <Th>{t("evidence.header.policy")}</Th>
            <Th>{t("evidence.header.scores")}</Th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <Td>
                <a className="font-medium text-accent hover:underline" href={row.url} rel="noreferrer" target="_blank">
                  {row.title}
                </a>
                <div className="mt-1 max-w-2xl text-xs leading-5 text-muted">{row.quote}</div>
                <div className="mt-1 text-xs text-muted">{fmtDate(row.capturedAt, preferences.language)}</div>
              </Td>
              <Td>{row.sourceName}</Td>
              <Td>
                <StatusBadge status={row.complianceStatus} />
                <div className="mt-1 text-xs text-muted">{translateDynamic(preferences.language, row.legalUsePolicy)}</div>
              </Td>
              <Td>
                <div className="text-xs text-muted">
                  {t("common.trust")} {pct(row.trustScore, preferences.language)}
                </div>
                <div className="text-xs text-muted">
                  {t("common.relevance")} {pct(row.relevanceScore, preferences.language)}
                </div>
              </Td>
            </tr>
          ))}
        </tbody>
      </Table>
    </div>
  );
}

export function PendingKnowledgeWrites({
  writes,
  onUndo,
}: {
  writes: PendingKnowledgeWrite[];
  onUndo: (id: string) => void;
}) {
  const { preferences, t } = usePreferences();
  if (writes.length === 0) {
    return <div className="text-sm text-muted">{t("pending.empty")}</div>;
  }

  return (
    <div className="space-y-3">
      {writes.map((write) => (
        <div className="rounded-md border border-border bg-panel-muted p-3" key={write.id}>
          <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <div className="text-sm font-semibold text-foreground">{write.title}</div>
                <StatusBadge status={write.status} />
                <Badge>{translateDynamic(preferences.language, write.domain)}</Badge>
              </div>
              <div className="mt-2 text-sm leading-6 text-muted">{write.summary}</div>
              <div className="mt-1 text-xs text-muted">
                {write.source} · {fmtDate(write.createdAt, preferences.language)}
              </div>
            </div>
            <Button
              aria-label={`${t("pending.undo")} ${write.title}`}
              disabled={!write.undoAvailable || write.status === "undo_requested"}
              onClick={() => onUndo(write.id)}
              type="button"
              variant="secondary"
            >
              <RotateCcw className="h-4 w-4" aria-hidden="true" />
              {t("pending.undo")}
            </Button>
          </div>
        </div>
      ))}
    </div>
  );
}

export function TraceList({ trace }: { trace: RetrievalTraceStep[] }) {
  const { preferences, t } = usePreferences();
  return (
    <div className="space-y-2">
      {trace.map((step) => (
        <div className="rounded-md border border-border bg-panel-muted p-3" key={step.id}>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="text-sm font-semibold text-foreground">
              {translateDynamic(preferences.language, step.stage) || step.stage}
            </div>
            <div className="flex items-center gap-2">
              {step.dryRun ? (
                <Badge className="border-border bg-panel text-foreground/80">
                  <Ban className="h-3.5 w-3.5" aria-hidden="true" />
                  {t("common.dry_run")}
                </Badge>
              ) : null}
              <StatusBadge status={step.status} />
            </div>
          </div>
          <div className="mt-2 text-xs leading-5 text-muted">{step.detail}</div>
        </div>
      ))}
    </div>
  );
}
