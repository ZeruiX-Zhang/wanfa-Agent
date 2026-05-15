"use client";

import { useMutation } from "@tanstack/react-query";
import { Check, Copy, Loader2, Wand2 } from "lucide-react";
import { useState } from "react";

import { usePreferences } from "@/components/preferences-provider";
import { Badge, Button, Panel, Textarea } from "@/components/ui";
import { v2 } from "@/lib/api-v2";

export function PromptView() {
  const { preferences, t } = usePreferences();
  const [prompt, setPrompt] = useState("");
  const [includeMemory, setIncludeMemory] = useState(true);
  const [copied, setCopied] = useState(false);

  const optimizeMutation = useMutation({
    mutationFn: () =>
      v2.promptOptimize({
        prompt: prompt.trim(),
        language: preferences.language,
        include_memory: includeMemory,
      }),
  });

  const result = optimizeMutation.data;

  const copy = async () => {
    if (!result) return;
    try {
      await navigator.clipboard.writeText(result.prompt_out);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-2 border-b border-border pb-5">
        <div className="text-xs font-semibold uppercase tracking-widest text-muted">Reality OS</div>
        <h1 className="text-2xl font-bold tracking-tight text-foreground">{t("prompt.title")}</h1>
        <p className="max-w-3xl text-sm leading-6 text-muted">{t("prompt.subtitle")}</p>
      </header>

      <Panel>
        <label className="text-[11px] font-semibold uppercase tracking-widest text-muted">
          {t("prompt.input.label")}
        </label>
        <Textarea
          className="mt-2 min-h-36"
          placeholder={t("prompt.input.placeholder")}
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
        />
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <label className="inline-flex items-center gap-2 text-sm text-foreground/80">
            <input
              type="checkbox"
              checked={includeMemory}
              onChange={(event) => setIncludeMemory(event.target.checked)}
              className="h-4 w-4 rounded border-border"
            />
            {t("prompt.memory.label")}
          </label>
          <Button onClick={() => prompt.trim() && optimizeMutation.mutate()} disabled={!prompt.trim() || optimizeMutation.isPending}>
            {optimizeMutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                {t("prompt.submitting")}
              </>
            ) : (
              <>
                <Wand2 className="h-4 w-4" aria-hidden="true" />
                {t("prompt.submit")}
              </>
            )}
          </Button>
        </div>
      </Panel>

      {result ? (
        <Panel>
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-sm font-semibold text-foreground">{t("prompt.result.title")}</h2>
            <Badge>
              {t("prompt.result.meta")
                .replace("{model}", result.thinking_model)
                .replace("{count}", String(result.memory_lines.length))}
            </Badge>
            <Button variant="secondary" className="ml-auto" onClick={copy}>
              {copied ? (
                <>
                  <Check className="h-4 w-4 text-success" aria-hidden="true" />
                  {t("prompt.result.copied")}
                </>
              ) : (
                <>
                  <Copy className="h-4 w-4" aria-hidden="true" />
                  {t("prompt.result.copy")}
                </>
              )}
            </Button>
          </div>
          <pre className="mt-3 whitespace-pre-wrap rounded-md border border-border bg-panel-muted p-3 text-sm leading-6 text-foreground/90">
            {result.prompt_out}
          </pre>
          {result.memory_lines.length ? (
            <ul className="mt-3 space-y-1 text-xs text-muted">
              {result.memory_lines.map((line) => (
                <li key={line}>· {line}</li>
              ))}
            </ul>
          ) : null}
        </Panel>
      ) : null}
    </div>
  );
}
