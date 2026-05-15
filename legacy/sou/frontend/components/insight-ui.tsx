import type { LucideIcon } from "lucide-react";
import { CheckCircle2, CircleAlert, CircleDot, GitBranch, Quote, TrendingUp } from "lucide-react";
import type { ReactNode } from "react";
import { Badge, Panel } from "@/components/ui";
import type { SignalKind } from "@/lib/insights";
import { statusTone, verificationLabel } from "@/lib/insights";
import { cn } from "@/lib/utils";

export function MetricCard({
  label,
  value,
  detail,
  icon: Icon,
}: {
  label: string;
  value: ReactNode;
  detail?: ReactNode;
  icon?: LucideIcon;
}) {
  return (
    <Panel className="min-h-28">
      <div className="flex items-start justify-between gap-3">
        <div className="text-xs font-semibold uppercase text-muted">{label}</div>
        {Icon ? <Icon className="h-4 w-4 text-accent" aria-hidden="true" /> : null}
      </div>
      <div className="mt-3 text-2xl font-bold text-foreground">{value}</div>
      {detail ? <div className="mt-2 text-xs leading-5 text-muted">{detail}</div> : null}
    </Panel>
  );
}

export function StatusBadge({ status, className }: { status: string; className?: string }) {
  const tone = statusTone(status);
  return (
    <Badge
      className={cn(
        tone === "good" && "border-emerald-200 bg-emerald-50 text-emerald-800",
        tone === "warn" && "border-amber-200 bg-amber-50 text-amber-800",
        tone === "bad" && "border-rose-200 bg-rose-50 text-rose-800",
        tone === "neutral" && "border-slate-200 bg-slate-50 text-slate-700",
        className,
      )}
    >
      {verificationLabel(status)}
    </Badge>
  );
}

export function SignalBadge({ kind }: { kind: SignalKind }) {
  const Icon = kind === "fact" ? CheckCircle2 : TrendingUp;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-semibold uppercase",
        kind === "fact" && "border-emerald-200 bg-emerald-50 text-emerald-800",
        kind === "trend" && "border-sky-200 bg-sky-50 text-sky-800",
      )}
    >
      <Icon className="h-3.5 w-3.5" aria-hidden="true" />
      {kind}
    </span>
  );
}

export function FactTrendLegend() {
  return (
    <div className="flex flex-wrap gap-2 text-xs text-muted">
      <span className="inline-flex items-center gap-1">
        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-700" aria-hidden="true" />
        Fact: verified, high confidence, evidence-backed
      </span>
      <span className="inline-flex items-center gap-1">
        <TrendingUp className="h-3.5 w-3.5 text-sky-700" aria-hidden="true" />
        Trend: emerging signal that still needs corroboration
      </span>
    </div>
  );
}

export function ScoreBar({ label, value }: { label: string; value: number }) {
  const width = `${Math.max(0, Math.min(100, Math.round(value * 100)))}%`;
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className="text-muted">{label}</span>
        <span className="font-semibold">{width}</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-slate-100">
        <div className="h-full rounded-full bg-accent" style={{ width }} />
      </div>
    </div>
  );
}

export function EvidenceStrip({
  sources,
  evidence,
  languages,
}: {
  sources: number;
  evidence: number;
  languages: string[];
}) {
  return (
    <div className="flex flex-wrap gap-2 text-xs">
      <span className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2 py-1">
        <GitBranch className="h-3.5 w-3.5 text-muted" aria-hidden="true" />
        {sources} sources
      </span>
      <span className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2 py-1">
        <Quote className="h-3.5 w-3.5 text-muted" aria-hidden="true" />
        {evidence} evidence
      </span>
      <span className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2 py-1">
        <CircleDot className="h-3.5 w-3.5 text-muted" aria-hidden="true" />
        {languages.length > 0 ? languages.join(", ") : "language n/a"}
      </span>
    </div>
  );
}

export function Callout({
  title,
  children,
  tone = "neutral",
}: {
  title: string;
  children: ReactNode;
  tone?: "neutral" | "warn" | "bad" | "good";
}) {
  return (
    <div
      className={cn(
        "rounded-md border p-3 text-sm leading-6",
        tone === "neutral" && "border-slate-200 bg-slate-50 text-slate-700",
        tone === "warn" && "border-amber-200 bg-amber-50 text-amber-900",
        tone === "bad" && "border-rose-200 bg-rose-50 text-rose-900",
        tone === "good" && "border-emerald-200 bg-emerald-50 text-emerald-900",
      )}
    >
      <div className="mb-1 flex items-center gap-2 font-semibold">
        <CircleAlert className="h-4 w-4" aria-hidden="true" />
        {title}
      </div>
      {children}
    </div>
  );
}
