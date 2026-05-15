"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Loader2, User } from "lucide-react";
import { useEffect, useState } from "react";

import { usePreferences } from "@/components/preferences-provider";
import { Badge, Button, Input, Panel, Select, Textarea } from "@/components/ui";
import { v2 } from "@/lib/api-v2";

const LEVELS = ["beginner", "intermediate", "independent", "expert"] as const;

type FormState = {
  industry: string;
  level: (typeof LEVELS)[number];
  resources: string;
  goals: string;
  constraints: string;
  current_tasks: string;
  error_patterns: string;
};

const EMPTY: FormState = {
  industry: "",
  level: "beginner",
  resources: "",
  goals: "",
  constraints: "",
  current_tasks: "",
  error_patterns: "",
};

function linesToList(value: string): string[] {
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

function listToLines(value: string[] | undefined | null): string {
  if (!value) return "";
  return value.join("\n");
}

function resourcesFromLines(value: string): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const raw of value.split("\n")) {
    const line = raw.trim();
    if (!line) continue;
    const idx = line.indexOf(":");
    if (idx <= 0) continue;
    const key = line.slice(0, idx).trim();
    const val = line.slice(idx + 1).trim();
    if (key && val) out[key] = val;
  }
  return out;
}

function resourcesToLines(value: Record<string, unknown> | undefined | null): string {
  if (!value) return "";
  return Object.entries(value)
    .map(([k, v]) => `${k}:${v}`)
    .join("\n");
}

export function ProfilePanel() {
  const { t } = usePreferences();
  const queryClient = useQueryClient();
  const [form, setForm] = useState<FormState>(EMPTY);
  const [justSaved, setJustSaved] = useState(false);

  const profileQuery = useQuery({
    queryKey: ["v2", "profile"],
    queryFn: () => v2.getProfile(),
  });

  useEffect(() => {
    const loaded = profileQuery.data;
    if (!loaded?.exists || !loaded.profile) return;
    setForm({
      industry: loaded.profile.industry ?? "",
      level: (loaded.profile.level as (typeof LEVELS)[number]) ?? "beginner",
      resources: resourcesToLines(loaded.profile.resources as Record<string, unknown>),
      goals: listToLines(loaded.profile.goals),
      constraints: listToLines(loaded.profile.constraints),
      current_tasks: listToLines(loaded.profile.current_tasks),
      error_patterns: listToLines(loaded.profile.error_patterns),
    });
  }, [profileQuery.data]);

  const saveMutation = useMutation({
    mutationFn: () =>
      v2.saveProfile({
        industry: form.industry.trim(),
        level: form.level,
        resources: resourcesFromLines(form.resources),
        goals: linesToList(form.goals),
        constraints: linesToList(form.constraints),
        current_tasks: linesToList(form.current_tasks),
        error_patterns: linesToList(form.error_patterns),
      }),
    onSuccess: () => {
      setJustSaved(true);
      window.setTimeout(() => setJustSaved(false), 2000);
      queryClient.invalidateQueries({ queryKey: ["v2", "profile"] });
    },
  });

  const profileExists = profileQuery.data?.exists === true;

  return (
    <Panel>
      <div className="flex items-start gap-2">
        <User className="mt-0.5 h-4 w-4 text-accent" aria-hidden="true" />
        <div>
          <h2 className="text-sm font-semibold text-foreground">{t("settings.profile.title")}</h2>
          <p className="mt-1 text-sm leading-6 text-muted">{t("settings.profile.desc")}</p>
        </div>
        {profileExists ? (
          <Badge className="ml-auto border-success/40 bg-success/10 text-success">
            {t("settings.profile.loaded")}
          </Badge>
        ) : (
          <Badge className="ml-auto border-warning/40 bg-warning/10 text-warning">
            {t("settings.profile.empty_hint")}
          </Badge>
        )}
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <Labeled label={t("settings.profile.industry")}>
          <Input
            placeholder={t("settings.profile.industry_placeholder")}
            value={form.industry}
            onChange={(event) => setForm({ ...form, industry: event.target.value })}
          />
        </Labeled>
        <Labeled label={t("settings.profile.level")}>
          <Select
            value={form.level}
            onChange={(event) => setForm({ ...form, level: event.target.value as (typeof LEVELS)[number] })}
          >
            {LEVELS.map((level) => (
              <option key={level} value={level}>
                {t(`settings.profile.level.${level}`)}
              </option>
            ))}
          </Select>
        </Labeled>
      </div>

      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <Labeled label={t("settings.profile.resources")}>
          <Textarea
            rows={4}
            value={form.resources}
            onChange={(event) => setForm({ ...form, resources: event.target.value })}
            placeholder={"time:20h/week\nmoney:low\ntools:cursor, notion"}
          />
        </Labeled>
        <Labeled label={t("settings.profile.goals")}>
          <Textarea
            rows={4}
            value={form.goals}
            onChange={(event) => setForm({ ...form, goals: event.target.value })}
          />
        </Labeled>
      </div>

      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <Labeled label={t("settings.profile.constraints")}>
          <Textarea
            rows={4}
            value={form.constraints}
            onChange={(event) => setForm({ ...form, constraints: event.target.value })}
          />
        </Labeled>
        <Labeled label={t("settings.profile.current_tasks")}>
          <Textarea
            rows={4}
            value={form.current_tasks}
            onChange={(event) => setForm({ ...form, current_tasks: event.target.value })}
          />
        </Labeled>
      </div>

      <div className="mt-3">
        <Labeled label={t("settings.profile.error_patterns")}>
          <Textarea
            rows={3}
            value={form.error_patterns}
            onChange={(event) => setForm({ ...form, error_patterns: event.target.value })}
          />
        </Labeled>
      </div>

      <div className="mt-4 flex items-center gap-2">
        <Button onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending}>
          {saveMutation.isPending ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              {t("settings.profile.saving")}
            </>
          ) : justSaved ? (
            <>
              <Check className="h-4 w-4 text-success" aria-hidden="true" />
              {t("settings.profile.saved")}
            </>
          ) : (
            t("settings.profile.save")
          )}
        </Button>
      </div>
    </Panel>
  );
}

function Labeled({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="text-[11px] font-semibold uppercase tracking-widest text-muted">{label}</label>
      <div className="mt-1">{children}</div>
    </div>
  );
}
