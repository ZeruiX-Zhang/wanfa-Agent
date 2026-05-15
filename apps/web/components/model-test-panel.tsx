"use client";

import { useMutation } from "@tanstack/react-query";
import { Check, Cpu, Loader2, X } from "lucide-react";
import { useMemo, useState } from "react";

import { usePreferences } from "@/components/preferences-provider";
import { Badge, Button, Input, Panel } from "@/components/ui";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

export function ModelTestPanel() {
  const { preferences, setProfessionalValue, t } = usePreferences();
  const language = preferences.language;
  const [provider, setProvider] = useState("server-configured");
  const [model, setModel] = useState("server-configured");
  const [applied, setApplied] = useState(false);

  const mutation = useMutation({
    mutationFn: () => api.testModel({ language, provider, model }),
    onSuccess: () => setApplied(false),
  });

  const report = mutation.data;

  const tierBadgeClass = useMemo(() => {
    if (!report) return "";
    if (report.tier === "flagship") return "border-success/40 bg-success/10 text-success";
    if (report.tier === "mid") return "border-accent/40 bg-accent-soft text-foreground";
    if (report.tier === "basic") return "border-warning/40 bg-warning/10 text-warning";
    return "border-danger/40 bg-danger/10 text-danger";
  }, [report]);

  const aggregatePercent = report ? Math.round(report.aggregate_score * 100) : 0;

  const apply = () => {
    if (!report) return;
    const strategy = report.workflow_strategy;
    setProfessionalValue("planner_depth", strategy.planner_depth);
    setProfessionalValue("top_k", strategy.retrieval_top_k);
    setProfessionalValue("quality_threshold", strategy.quality_threshold);
    setApplied(true);
  };

  return (
    <Panel>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Cpu className="h-4 w-4 text-accent" aria-hidden="true" />
            <h2 className="text-sm font-semibold text-foreground">{t("settings.section.model_test.title")}</h2>
          </div>
          <p className="mt-1 max-w-3xl text-sm leading-6 text-muted">
            {t("settings.section.model_test.desc")}
          </p>
        </div>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]">
        <div>
          <label className="text-[11px] font-semibold uppercase tracking-widest text-muted">
            {t("settings.section.model_test.provider")}
          </label>
          <Input
            className="mt-1"
            value={provider}
            onChange={(event) => setProvider(event.target.value)}
            disabled={mutation.isPending}
          />
        </div>
        <div>
          <label className="text-[11px] font-semibold uppercase tracking-widest text-muted">
            {t("settings.section.model_test.model")}
          </label>
          <Input
            className="mt-1"
            value={model}
            onChange={(event) => setModel(event.target.value)}
            disabled={mutation.isPending}
          />
        </div>
        <div className="flex items-end">
          <Button type="button" onClick={() => mutation.mutate()} disabled={mutation.isPending} className="w-full md:w-auto">
            {mutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                {t("settings.section.model_test.running")}
              </>
            ) : (
              t("settings.section.model_test.run")
            )}
          </Button>
        </div>
      </div>

      {mutation.isError ? (
        <div className="mt-3 rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
          {(mutation.error as Error)?.message ?? "failed"}
        </div>
      ) : null}

      {report ? (
        <div className="mt-5 space-y-4">
          <div className="flex flex-wrap items-center gap-3">
            <div className="text-xs font-semibold uppercase tracking-widest text-muted">
              {t("settings.section.model_test.aggregate")}
            </div>
            <div className="text-xl font-bold text-foreground">{aggregatePercent}%</div>
            <div className="flex flex-1 min-w-32 max-w-sm overflow-hidden rounded-full bg-panel-muted">
              <div
                className="h-2 rounded-full bg-accent"
                style={{ width: `${Math.max(4, aggregatePercent)}%` }}
                aria-hidden="true"
              />
            </div>
            <Badge className={cn("uppercase", tierBadgeClass)}>
              {t(`settings.section.model_test.tier.${report.tier}`)}
            </Badge>
          </div>

          <div className="rounded-panel border border-border bg-panel p-4">
            <div className="text-xs font-semibold uppercase tracking-widest text-muted">
              {t("settings.section.model_test.strategy.title")}
            </div>
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              <StrategyField
                label={t("settings.section.model_test.strategy.prompt_strategy")}
                value={report.workflow_strategy.prompt_strategy}
              />
              <StrategyField
                label={t("settings.section.model_test.strategy.quality_threshold")}
                value={String(report.workflow_strategy.quality_threshold)}
              />
              <StrategyField
                label={t("settings.section.model_test.strategy.planner_depth")}
                value={String(report.workflow_strategy.planner_depth)}
              />
              <StrategyField
                label={t("settings.section.model_test.strategy.retrieval_top_k")}
                value={String(report.workflow_strategy.retrieval_top_k)}
              />
              <StrategyToggle
                label={t("settings.section.model_test.strategy.self_consistency")}
                value={report.workflow_strategy.enable_self_consistency}
              />
              <StrategyToggle
                label={t("settings.section.model_test.strategy.decompose")}
                value={report.workflow_strategy.enable_decompose_and_solve}
              />
            </div>
            <p className="mt-4 rounded-md border border-dashed border-border bg-panel-muted px-3 py-2 text-sm leading-6 text-muted">
              {report.workflow_strategy.description}
            </p>
            <p className="mt-3 text-sm leading-6 text-foreground">{report.recommendation}</p>
            <div className="mt-3 flex items-center gap-2">
              <Button type="button" variant="secondary" onClick={apply} disabled={report.tier === "insufficient"}>
                {applied ? (
                  <>
                    <Check className="h-4 w-4 text-success" aria-hidden="true" />
                    {t("settings.section.model_test.applied")}
                  </>
                ) : (
                  t("settings.section.model_test.apply")
                )}
              </Button>
            </div>
          </div>

          <div>
            <div className="text-xs font-semibold uppercase tracking-widest text-muted">
              {t("settings.section.model_test.probes")}
            </div>
            <div className="mt-2 grid gap-2">
              {report.probes.map((probe) => (
                <div key={probe.id} className="rounded-md border border-border bg-panel p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-semibold text-foreground">{probe.label}</span>
                    <Badge
                      className={cn(
                        probe.passed
                          ? "border-success/40 bg-success/10 text-success"
                          : "border-warning/40 bg-warning/10 text-warning",
                      )}
                    >
                      {probe.passed ? (
                        <>
                          <Check className="h-3 w-3" aria-hidden="true" />
                          {Math.round(probe.score * 100)}%
                        </>
                      ) : (
                        <>
                          <X className="h-3 w-3" aria-hidden="true" />
                          {Math.round(probe.score * 100)}%
                        </>
                      )}
                    </Badge>
                  </div>
                  <div className="mt-1 text-xs leading-5 text-muted">{probe.detail}</div>
                </div>
              ))}
            </div>
          </div>

          {report.notes.length ? (
            <div>
              <div className="text-xs font-semibold uppercase tracking-widest text-muted">
                {t("settings.section.model_test.notes")}
              </div>
              <ul className="mt-2 space-y-1 text-xs text-muted">
                {report.notes.map((note) => (
                  <li key={note}>{note}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}
    </Panel>
  );
}

function StrategyField({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border bg-panel-muted p-3">
      <div className="text-[11px] font-semibold uppercase tracking-widest text-muted">{label}</div>
      <div className="mt-1 text-sm font-semibold text-foreground">{value}</div>
    </div>
  );
}

function StrategyToggle({ label, value }: { label: string; value: boolean }) {
  const { t } = usePreferences();
  return (
    <div className="rounded-md border border-border bg-panel-muted p-3">
      <div className="text-[11px] font-semibold uppercase tracking-widest text-muted">{label}</div>
      <div className="mt-2 flex items-center gap-2 text-sm font-semibold text-foreground">
        <span
          className={cn(
            "inline-block h-2 w-2 rounded-full",
            value ? "bg-success" : "bg-muted",
          )}
          aria-hidden="true"
        />
        {value ? t("dyn.on") : t("dyn.off")}
      </div>
    </div>
  );
}
