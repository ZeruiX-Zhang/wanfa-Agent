"use client";

import { useMutation } from "@tanstack/react-query";
import { ImagePlus, Loader2, Wand2 } from "lucide-react";
import { useCallback, useId, useMemo, useRef, useState } from "react";

import { usePreferences } from "@/components/preferences-provider";
import { Badge, Button, Input, Panel, Textarea } from "@/components/ui";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

const MAX_IMAGE_BYTES = 5 * 1024 * 1024;

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result;
      if (typeof result !== "string") {
        reject(new Error("Unexpected file reader payload"));
        return;
      }
      const comma = result.indexOf(",");
      resolve(comma >= 0 ? result.slice(comma + 1) : result);
    };
    reader.onerror = () => reject(reader.error ?? new Error("Failed to read file"));
    reader.readAsDataURL(file);
  });
}

export function VisionInput() {
  const { preferences, t } = usePreferences();
  const language = preferences.language;
  const fileInputId = useId();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [preview, setPreview] = useState<{ url: string; name: string; size: number } | null>(null);
  const [hint, setHint] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: async () => {
      let imageBase64: string | undefined;
      if (fileInputRef.current?.files?.[0]) {
        const file = fileInputRef.current.files[0];
        if (file.size > MAX_IMAGE_BYTES) {
          throw new Error(
            language === "zh-CN"
              ? "图片超过 5 MB，请压缩后重试。"
              : "Image exceeds 5 MB; please compress and retry.",
          );
        }
        imageBase64 = await fileToBase64(file);
      }
      return api.visionDescribe({
        language,
        image_base64: imageBase64 ?? null,
        image_hint: hint || null,
        user_notes: notes || null,
      });
    },
    onError: (err: unknown) => {
      setError(err instanceof Error ? err.message : String(err));
    },
    onSuccess: () => setError(null),
  });

  const onFileChange = useCallback((files: FileList | null) => {
    const next = files?.[0];
    if (!next) {
      setPreview(null);
      return;
    }
    const url = URL.createObjectURL(next);
    setPreview({ url, name: next.name, size: next.size });
    setError(null);
  }, []);

  const clearAll = useCallback(() => {
    setPreview((current) => {
      if (current) URL.revokeObjectURL(current.url);
      return null;
    });
    setHint("");
    setNotes("");
    setError(null);
    mutation.reset();
    if (fileInputRef.current) fileInputRef.current.value = "";
  }, [mutation]);

  const disabled = mutation.isPending;
  const result = mutation.data;

  const localizedSize = useMemo(() => {
    if (!preview) return null;
    const kb = preview.size / 1024;
    if (kb < 1024) return `${kb.toFixed(1)} KB`;
    return `${(kb / 1024).toFixed(2)} MB`;
  }, [preview]);

  return (
    <Panel>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-foreground">{t("vision.title")}</h2>
          <p className="mt-1 text-sm leading-6 text-muted">{t("vision.desc")}</p>
        </div>
        <Badge className="whitespace-nowrap border-accent/40 bg-accent-soft text-foreground">
          {language === "zh-CN" ? t("vision.language_badge") : t("vision.language_badge.en")}
        </Badge>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
        <div>
          <label
            htmlFor={fileInputId}
            className={cn(
              "flex min-h-44 cursor-pointer flex-col items-center justify-center gap-2 rounded-panel border-2 border-dashed border-border bg-panel-muted px-4 py-6 text-center text-sm text-muted transition hover:border-accent hover:bg-accent-soft",
              disabled && "pointer-events-none opacity-70",
            )}
          >
            {preview ? (
              /* eslint-disable-next-line @next/next/no-img-element */
              <img
                src={preview.url}
                alt={preview.name}
                className="max-h-40 w-auto rounded-md border border-border object-contain"
              />
            ) : (
              <ImagePlus className="h-6 w-6 text-muted" aria-hidden="true" />
            )}
            <div className="font-medium text-foreground">{preview ? preview.name : t("vision.drop")}</div>
            <div className="text-xs text-muted">{preview ? localizedSize : t("vision.drop_hint")}</div>
            <input
              id={fileInputId}
              ref={fileInputRef}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={(event) => onFileChange(event.target.files)}
              disabled={disabled}
            />
          </label>

          <div className="mt-3 grid gap-3">
            <div>
              <label className="text-xs font-semibold uppercase tracking-widest text-muted">
                {t("vision.hint_label")}
              </label>
              <Input
                className="mt-1"
                placeholder={t("vision.hint_placeholder")}
                value={hint}
                onChange={(event) => setHint(event.target.value)}
                disabled={disabled}
              />
            </div>
            <div>
              <label className="text-xs font-semibold uppercase tracking-widest text-muted">
                {t("vision.notes_label")}
              </label>
              <Textarea
                className="mt-1"
                placeholder={t("vision.notes_placeholder")}
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
                disabled={disabled}
              />
            </div>
            <div className="flex items-center gap-2">
              <Button onClick={() => mutation.mutate()} disabled={disabled} type="button">
                {disabled ? (
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                ) : (
                  <Wand2 className="h-4 w-4" aria-hidden="true" />
                )}
                {t("vision.run")}
              </Button>
              <Button variant="secondary" type="button" onClick={clearAll} disabled={disabled}>
                {t("vision.clear")}
              </Button>
              {error ? <span className="text-xs text-danger">{error}</span> : null}
            </div>
          </div>
        </div>

        <div className="space-y-3">
          <div className="rounded-panel border border-border bg-panel p-3">
            <div className="text-xs font-semibold uppercase tracking-widest text-muted">
              {t("vision.result.caption")}
            </div>
            <div className="mt-1 min-h-6 text-sm leading-6 text-foreground">
              {result?.caption ?? t("vision.awaiting")}
            </div>
          </div>
          <div className="rounded-panel border border-border bg-panel p-3">
            <div className="text-xs font-semibold uppercase tracking-widest text-muted">
              {t("vision.result.ocr")}
            </div>
            <div className="mt-1 whitespace-pre-wrap break-words text-sm leading-6 text-foreground">
              {result?.ocr_text ?? t("vision.awaiting")}
            </div>
          </div>
          <div className="rounded-panel border border-border bg-panel p-3">
            <div className="text-xs font-semibold uppercase tracking-widest text-muted">
              {t("vision.result.visual")}
            </div>
            <ul className="mt-2 space-y-1 text-sm leading-6 text-foreground/90">
              {(result?.visual_description ?? []).map((bullet) => (
                <li className="flex items-start gap-2" key={bullet}>
                  <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" aria-hidden="true" />
                  <span>{bullet}</span>
                </li>
              ))}
              {!result ? <li className="text-muted">{t("vision.awaiting")}</li> : null}
            </ul>
          </div>
          {result?.source === "mock-safe" ? (
            <div className="rounded-md border border-dashed border-border bg-panel-muted px-3 py-2 text-xs text-muted">
              {t("vision.result.mock_notice")}
            </div>
          ) : null}
          {result?.warnings?.length ? (
            <ul className="space-y-1 text-xs text-warning">
              {result.warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          ) : null}
        </div>
      </div>
    </Panel>
  );
}
