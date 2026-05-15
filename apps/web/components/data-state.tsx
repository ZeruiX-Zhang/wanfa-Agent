import { AlertTriangle, Loader2 } from "lucide-react";
import { Panel } from "@/components/ui";

export function LoadingState({ label = "Loading" }: { label?: string }) {
  return (
    <Panel className="flex items-center gap-2 text-sm text-muted">
      <Loader2 className="h-4 w-4 animate-spin" />
      {label}
    </Panel>
  );
}

export function ErrorState({ error }: { error: unknown }) {
  return (
    <Panel className="flex items-center gap-2 border-red-200 bg-red-50 text-sm text-danger">
      <AlertTriangle className="h-4 w-4" />
      {error instanceof Error ? error.message : "Request failed"}
    </Panel>
  );
}

export function EmptyState({ title }: { title: string }) {
  return <Panel className="text-sm text-muted">{title}</Panel>;
}
