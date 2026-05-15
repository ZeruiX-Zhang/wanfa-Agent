"use client";

import { useMutation } from "@tanstack/react-query";
import {
  AlertTriangle,
  Beaker,
  BookOpen,
  Check,
  CheckCircle2,
  Compass,
  Gauge,
  Loader2,
  Lightbulb,
  Quote,
  Shield,
  Sparkles,
  Target,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { usePreferences } from "@/components/preferences-provider";
import { Badge, Button, Panel, Textarea } from "@/components/ui";
import { translateDynamic } from "@/lib/i18n";
import { v2, type AskResult, type DiagnosePipeline } from "@/lib/api-v2";
import { cn } from "@/lib/utils";

const ROOT_CAUSE_OPTIONS = ["fact_wrong", "model_wrong", "execution_wrong", "unknown"] as const;

export function AskView() {
  const { preferences, t } = usePreferences();
  const [question, setQuestion] = useState("");
  const [experimentSaved, setExperimentSaved] = useState<string | null>(null);

  const diagnoseMutation = useMutation({
    mutationFn: () => v2.diagnose({ question: question.trim(), language: preferences.language }),
  });

  const askMutation = useMutation({
    mutationFn: () => v2.ask({ question: question.trim(), language: preferences.language }),
  });

  const saveExperimentMutation = useMutation({
    mutationFn: async (result: DiagnosePipeline) => {
      // The diagnose call already persists the experiment; just update its
      // status to `running` so it shows up on the Learn page.
      return v2.updateExperiment(result.experiment.id, { status: "running" });
    },
    onSuccess: (exp) => setExperimentSaved(exp.id),
  });

  const run = () => {
    if (!question.trim()) return;
    setExperimentSaved(null);
    diagnoseMutation.mutate();
    askMutation.mutate();
  };

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-2 border-b border-border pb-5">
        <div className="text-xs font-semibold uppercase tracking-widest text-muted">Reality OS</div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">{t("ask.title")}</h1>
        <p className="max-w-3xl text-sm leading-6 text-muted">{t("ask.subtitle")}</p>
      </header>

      <Panel>
        <Textarea
          className="min-h-24"
          placeholder={t("ask.placeholder")}
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) run();
          }}
        />
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Button onClick={run} disabled={!question.trim() || diagnoseMutation.isPending || askMutation.isPending}>
            {diagnoseMutation.isPending || askMutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                {t("ask.diagnose.running")}
              </>
            ) : (
              <>
                <Compass className="h-4 w-4" aria-hidden="true" />
                {t("ask.diagnose.button")}
              </>
            )}
          </Button>
          <span className="text-xs text-muted">Ctrl/Cmd + Enter</span>
          {diagnoseMutation.isError ? (
            <span className="text-xs text-danger">
              {t("ask.error")}
              {(diagnoseMutation.error as Error)?.message}
            </span>
          ) : null}
        </div>
      </Panel>

      {diagnoseMutation.data ? (
        <DiagnosisPanel
          data={diagnoseMutation.data}
          saved={experimentSaved === diagnoseMutation.data.experiment.id}
          onSaveExperiment={() => saveExperimentMutation.mutate(diagnoseMutation.data!)}
          saving={saveExperimentMutation.isPending}
        />
      ) : null}

      {askMutation.data ? <AnswerPanel result={askMutation.data} /> : null}
    </div>
  );
}

function DiagnosisPanel({
  data,
  saved,
  saving,
  onSaveExperiment,
}: {
  data: DiagnosePipeline;
  saved: boolean;
  saving: boolean;
  onSaveExperiment: () => void;
}) {
  const { preferences, t } = usePreferences();
  const diag = data.diagnosis;
  const exp = data.experiment;

  return (
    <div className="space-y-4">
      <Panel className="border-accent/40">
        <div className="flex items-start gap-2">
          <Sparkles className="mt-0.5 h-4 w-4 text-accent" aria-hidden="true" />
          <div>
            <h2 className="text-sm font-semibold text-foreground">{t("ask.diagnose.title")}</h2>
            <p className="mt-1 text-sm leading-6 text-muted">{t("ask.diagnose.desc")}</p>
          </div>
        </div>

        <div className="mt-4 grid gap-3 lg:grid-cols-2">
          <DiagField
            icon={Target}
            label={t("ask.diagnose.real")}
            value={diag.real_question}
            tone="accent"
          />
          <DiagField
            icon={Compass}
            label={t("ask.diagnose.type")}
            value={translateDynamic(preferences.language, diag.problem_type) || diag.problem_type}
          />
          <DiagField
            icon={BookOpen}
            label={t("ask.diagnose.models")}
            value={diag.thinking_models_used.join(" · ")}
          />
          <DiagField
            icon={Gauge}
            label={t("ask.diagnose.expert")}
            value={diag.expert_first_look}
          />
        </div>

        <div className="mt-4">
          <SectionTitle icon={Lightbulb} label={t("ask.diagnose.variables")} />
          <ul className="mt-2 grid gap-2 sm:grid-cols-2">
            {diag.key_variables.map((variable) => (
              <li
                key={variable}
                className="rounded-md border border-border bg-panel-muted px-3 py-2 text-sm text-foreground/80"
              >
                {variable}
              </li>
            ))}
          </ul>
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <div>
            <SectionTitle icon={CheckCircle2} label={t("ask.diagnose.evidence")} />
            <ul className="mt-2 space-y-2">
              {diag.evidence_status.map((item, idx) => (
                <li
                  key={`${item.type}-${idx}`}
                  className={cn(
                    "flex items-start gap-2 rounded-md border bg-panel-muted px-3 py-2 text-sm",
                    item.status === "confirmed"
                      ? "border-success/40 text-foreground"
                      : "border-warning/40 text-foreground",
                  )}
                >
                  <Badge
                    className={cn(
                      "whitespace-nowrap",
                      item.status === "confirmed"
                        ? "border-success/40 bg-success/10 text-success"
                        : "border-warning/40 bg-warning/10 text-warning",
                    )}
                  >
                    {t(`ask.diagnose.evidence.${item.type}`) || item.type} ·{" "}
                    {t(`ask.diagnose.evidence.${item.status}`) || item.status}
                  </Badge>
                  <span className="flex-1 text-foreground/80">{item.content}</span>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <SectionTitle icon={AlertTriangle} label={t("ask.diagnose.subjective")} />
            <ul className="mt-2 space-y-2">
              {diag.subjective_judgments.map((item, idx) => (
                <li key={idx} className="rounded-md border border-border bg-panel-muted px-3 py-2 text-sm text-foreground/80">
                  {item}
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <div>
            <SectionTitle icon={Shield} label={t("ask.diagnose.external")} />
            <ul className="mt-2 space-y-1 text-sm text-foreground/80">
              {diag.needs_external_verification.map((item, idx) => (
                <li key={idx} className="flex gap-2">
                  <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
                  {item}
                </li>
              ))}
            </ul>
          </div>
          <div>
            <SectionTitle icon={AlertTriangle} label={t("ask.diagnose.failure")} />
            <ul className="mt-2 space-y-1 text-sm text-foreground/80">
              {diag.common_failure_reasons.map((item, idx) => (
                <li key={idx} className="flex gap-2">
                  <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-danger" />
                  {item}
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="mt-4 rounded-panel border border-accent/40 bg-accent-soft p-4">
          <SectionTitle icon={Target} label={t("ask.diagnose.mva")} />
          <p className="mt-2 text-sm font-medium text-foreground">{diag.minimum_verifiable_action}</p>
        </div>
      </Panel>

      <Panel>
        <div className="flex items-start gap-2">
          <Beaker className="mt-0.5 h-4 w-4 text-accent" aria-hidden="true" />
          <div className="flex-1">
            <h2 className="text-sm font-semibold text-foreground">{t("ask.experiment.title")}</h2>
            <p className="mt-1 text-sm leading-6 text-muted">{exp.hypothesis}</p>
          </div>
          <Button
            type="button"
            variant={saved ? "secondary" : "primary"}
            disabled={saved || saving}
            onClick={onSaveExperiment}
          >
            {saved ? (
              <>
                <Check className="h-4 w-4 text-success" aria-hidden="true" />
                {t("ask.experiment.saved")}
              </>
            ) : saving ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            ) : (
              t("ask.experiment.save")
            )}
          </Button>
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          <ExpField label={t("ask.experiment.experiment")} value={exp.experiment} />
          <ExpField
            label={t("ask.experiment.cost")}
            value={`${exp.cost.time ?? ""} · ${exp.cost.money ?? ""} · ${exp.cost.effort ?? ""}`}
          />
          <ExpField label={t("ask.experiment.review")} value={exp.review_date} />
          <ExpField label={t("ask.experiment.success")} value={exp.success_metric} tone="success" />
          <ExpField label={t("ask.experiment.failure")} value={exp.failure_signal} tone="danger" />
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <ExpField label={t("ask.experiment.next_success")} value={exp.next_if_success} tone="success" />
          <ExpField label={t("ask.experiment.next_failure")} value={exp.next_if_failure} tone="warning" />
        </div>
      </Panel>
    </div>
  );
}

function AnswerPanel({ result }: { result: AskResult }) {
  const { preferences, t } = usePreferences();
  const traceMutation = useMutation({
    mutationFn: (runId: string) => v2.run(runId),
  });
  const confidenceClass = {
    solid: "border-success/40 bg-success/10 text-success",
    probable: "border-accent/40 bg-accent-soft text-foreground",
    uncertain: "border-warning/40 bg-warning/10 text-warning",
    insufficient: "border-danger/40 bg-danger/10 text-danger",
  }[result.confidence_band];

  useEffect(() => {
    if (result.run_id) {
      traceMutation.mutate(result.run_id);
    }
  }, [result.run_id]);

  return (
    <Panel>
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-sm font-semibold text-foreground">{t("ask.answer.title")}</h2>
        <Badge className={cn("whitespace-nowrap", confidenceClass)}>
          {t(`ask.confidence.${result.confidence_band}`)}
        </Badge>
        <Badge>{result.thinking_model}</Badge>
        <Badge>
          {t("ask.result.prompt_strategy")}: {translateDynamic(preferences.language, result.prompt_strategy) || result.prompt_strategy}
        </Badge>
        {result.run_id ? <Badge>run_id: {result.run_id}</Badge> : null}
      </div>

      <div className="mt-3 whitespace-pre-wrap text-sm leading-6 text-foreground/90">{result.answer}</div>

      {result.run_id ? (
        <TraceSummary
          runId={result.run_id}
          isPending={traceMutation.isPending}
          isError={traceMutation.isError}
          trace={traceMutation.data}
        />
      ) : null}

      {result.citations.length > 0 ? (
        <div className="mt-4">
          <SectionTitle icon={Quote} label={t("ask.result.citations")} />
          <ul className="mt-2 space-y-2">
            {result.citations.map((c) => (
              <li key={c.item_id} className="rounded-md border border-border bg-panel-muted p-3 text-sm">
                <Link href={`/library/${c.item_id}`} className="font-medium text-accent hover:underline">
                  {c.title}
                </Link>
                <div className="mt-1 text-xs text-muted">{c.snippet}</div>
                <div className="mt-1 text-[11px] text-muted">
                  {t("common.relevance")} {Math.round(c.relevance * 100)}% · {t("library.card.quality")}{" "}
                  {Math.round(c.quality * 100)}%
                </div>
                <div className="mt-2 flex flex-wrap gap-1.5 text-[11px] text-muted">
                  {c.url ? (
                    <a
                      href={c.url}
                      target="_blank"
                      rel="noreferrer"
                      className="max-w-full truncate text-accent hover:underline"
                    >
                      URL: {c.url}
                    </a>
                  ) : (
                    <span>URL: none</span>
                  )}
                  <MetaChip label="content_role" value={c.content_role} />
                  <MetaChip
                    label="security_flags"
                    value={c.security_flags && c.security_flags.length > 0 ? c.security_flags.join(", ") : "none"}
                  />
                  <MetaChip label="snapshot_id" value={c.snapshot_id} />
                  <MetaChip label="excerpt_hash" value={c.excerpt_hash} />
                </div>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {result.knowledge_gaps.length > 0 ? (
        <div className="mt-4">
          <SectionTitle icon={AlertTriangle} label={t("ask.result.gaps")} />
          <div className="mt-2 flex flex-wrap gap-2">
            {result.knowledge_gaps.map((gap) => (
              <Badge key={gap} className="border-warning/40 bg-warning/10 text-warning">
                {gap}
              </Badge>
            ))}
          </div>
        </div>
      ) : null}

      {result.next_actions.length > 0 ? (
        <div className="mt-4">
          <SectionTitle icon={Target} label={t("ask.result.next_actions")} />
          <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm text-foreground/80">
            {result.next_actions.map((action) => (
              <li key={action}>{action}</li>
            ))}
          </ol>
        </div>
      ) : null}
    </Panel>
  );
}

function TraceSummary({
  runId,
  isPending,
  isError,
  trace,
}: {
  runId: string;
  isPending: boolean;
  isError: boolean;
  trace?: Awaited<ReturnType<typeof v2.run>>;
}) {
  const steps = trace?.steps ?? [];
  const visibleSteps = steps.slice(0, 4);

  return (
    <div className="mt-3 rounded-md border border-border bg-panel-muted p-3 text-xs text-muted">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-semibold text-foreground">Trace</span>
        <MetaChip label="run_id" value={trace?.run.run_id ?? runId} />
        {isPending ? <span>loading...</span> : null}
        {isError ? <span className="text-warning">trace unavailable</span> : null}
        {trace ? (
          <>
            <MetaChip label="status" value={trace.run.status} />
            <MetaChip label="steps" value={String(trace.steps.length)} />
            <MetaChip label="model_calls" value={String(trace.model_calls.length)} />
            <MetaChip label="acceptance_checks" value={String(trace.acceptance_checks.length)} />
          </>
        ) : null}
      </div>
      {visibleSteps.length > 0 ? (
        <ol className="mt-2 flex flex-wrap gap-1.5">
          {visibleSteps.map((step, idx) => (
            <li key={`${runId}-${idx}`}>
              <MetaChip
                label={String(step.step_type ?? step.type ?? `step_${idx + 1}`)}
                value={String(step.status ?? step.output_hash ?? "recorded")}
              />
            </li>
          ))}
        </ol>
      ) : null}
    </div>
  );
}

function MetaChip({ label, value }: { label: string; value?: string | null }) {
  return (
    <span className="inline-flex max-w-full items-center gap-1 rounded border border-border bg-panel px-1.5 py-0.5">
      <span className="shrink-0 text-muted">{label}:</span>
      <span className="truncate text-foreground/80">{value || "none"}</span>
    </span>
  );
}

function SectionTitle({ icon: Icon, label }: { icon: typeof Sparkles; label: string }) {
  return (
    <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-widest text-muted">
      <Icon className="h-3.5 w-3.5" aria-hidden="true" />
      {label}
    </div>
  );
}

function DiagField({
  icon: Icon,
  label,
  value,
  tone,
}: {
  icon: typeof Sparkles;
  label: string;
  value: string;
  tone?: "accent";
}) {
  return (
    <div
      className={cn(
        "rounded-panel border bg-panel p-3",
        tone === "accent" ? "border-accent/40" : "border-border",
      )}
    >
      <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-widest text-muted">
        <Icon className="h-3.5 w-3.5" aria-hidden="true" />
        {label}
      </div>
      <div className="mt-1 text-sm font-medium leading-6 text-foreground">{value}</div>
    </div>
  );
}

function ExpField({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "success" | "danger" | "warning";
}) {
  const toneClass =
    tone === "success"
      ? "border-success/40"
      : tone === "danger"
      ? "border-danger/40"
      : tone === "warning"
      ? "border-warning/40"
      : "border-border";
  return (
    <div className={cn("rounded-md border bg-panel-muted p-3", toneClass)}>
      <div className="text-[11px] font-semibold uppercase tracking-widest text-muted">{label}</div>
      <div className="mt-1 text-sm text-foreground/90">{value}</div>
    </div>
  );
}

// Unused, but suppress noUnusedParameters for ROOT_CAUSE_OPTIONS re-export pattern:
export const _askRootCauses = ROOT_CAUSE_OPTIONS;
