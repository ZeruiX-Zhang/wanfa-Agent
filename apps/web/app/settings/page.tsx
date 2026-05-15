"use client";

import { Check, ShieldCheck } from "lucide-react";

import { usePreferences } from "@/components/preferences-provider";
import { Badge, Button, Divider, Panel, Select } from "@/components/ui";
import { ModelTestPanel } from "@/components/model-test-panel";
import { ModelConfigPanel } from "@/components/model-config-panel";
import { ProfilePanel } from "@/components/profile-panel";
import {
  PALETTE_DESCRIPTIONS,
  PALETTE_LABELS,
  PALETTES,
  type Palette,
} from "@/lib/preferences";
import {
  PROFESSIONAL_PARAMETERS,
  PROFESSIONAL_SECTIONS,
  SIMPLE_MODE_AUTOMATION,
  parametersBySection,
  type ParameterDefinition,
  type ProfessionalSection,
} from "@/lib/professional-parameters";
import { cn } from "@/lib/utils";

export default function SettingsPage() {
  const {
    preferences,
    professional,
    setLanguage,
    setPalette,
    setAppearance,
    setMode,
    setProfessionalValue,
    resetProfessional,
    t,
  } = usePreferences();

  const isDark = preferences.appearance === "dark";

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-2 border-b border-border pb-6 md:flex-row md:items-end md:justify-between">
        <div>
          <div className="text-xs font-semibold uppercase tracking-widest text-muted">Reality OS</div>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-foreground">{t("settings.title")}</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">{t("settings.subtitle")}</p>
        </div>
        <Badge className="w-fit border-accent/40 bg-accent-soft text-foreground">
          <ShieldCheck className="mr-1 h-3.5 w-3.5" aria-hidden="true" />
          {t("common.pending_review")} / {t("common.dry_run")}
        </Badge>
      </header>

      {/* reality profile — layer 1 */}
      <ProfilePanel />

      {/* language */}
      <Panel>
        <SectionHeader title={t("settings.section.language.title")} description={t("settings.section.language.desc")} />
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <ChoiceCard
            title="简体中文"
            description="Chinese (Simplified) — default"
            selected={preferences.language === "zh-CN"}
            onClick={() => setLanguage("zh-CN")}
            tag="ZH"
          />
          <ChoiceCard
            title="English"
            description="English"
            selected={preferences.language === "en"}
            onClick={() => setLanguage("en")}
            tag="EN"
          />
        </div>
      </Panel>

      {/* theme + appearance */}
      <Panel>
        <SectionHeader title={t("settings.section.theme.title")} description={t("settings.section.theme.desc")} />
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <div className="text-xs font-semibold uppercase tracking-widest text-muted">
            {t("settings.section.theme.appearance")}
          </div>
          <div className="inline-flex overflow-hidden rounded-md border border-border bg-panel-muted p-0.5">
            <button
              type="button"
              onClick={() => setAppearance("light")}
              className={cn(
                "rounded-sm px-3 py-1 text-xs font-semibold transition",
                !isDark ? "bg-panel text-foreground shadow-panel" : "text-muted hover:text-foreground",
              )}
            >
              {t("settings.section.theme.appearance.light")}
            </button>
            <button
              type="button"
              onClick={() => setAppearance("dark")}
              className={cn(
                "rounded-sm px-3 py-1 text-xs font-semibold transition",
                isDark ? "bg-panel text-foreground shadow-panel" : "text-muted hover:text-foreground",
              )}
            >
              {t("settings.section.theme.appearance.dark")}
            </button>
          </div>
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {PALETTES.map((palette) => (
            <PaletteCard
              key={palette}
              palette={palette}
              appearance={preferences.appearance}
              selected={preferences.palette === palette}
              title={PALETTE_LABELS[palette][preferences.language]}
              description={PALETTE_DESCRIPTIONS[palette][preferences.language]}
              onClick={() => setPalette(palette)}
            />
          ))}
        </div>
      </Panel>

      {/* working mode */}
      <Panel>
        <SectionHeader title={t("settings.section.mode.title")} description={t("settings.section.mode.desc")} />
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <ModeCard
            title={t("common.simple_mode")}
            tag={t("mode.simple.badge")}
            selected={preferences.mode === "simple"}
            description={t("settings.section.mode.simple.desc")}
            onClick={() => setMode("simple")}
          />
          <ModeCard
            title={t("common.professional_mode")}
            tag={t("mode.professional.badge")}
            selected={preferences.mode === "professional"}
            description={t("settings.section.mode.professional.desc")}
            onClick={() => setMode("professional")}
          />
        </div>
        <Divider className="my-5" />
        {preferences.mode === "simple" ? (
          <SimpleModePanel language={preferences.language} />
        ) : (
          <ProfessionalModePanel
            professional={professional}
            setProfessionalValue={setProfessionalValue}
            resetProfessional={resetProfessional}
            language={preferences.language}
            t={t}
          />
        )}
      </Panel>

      {/* safety defaults (status-only) */}
      <Panel>
        <SectionHeader title={t("settings.security.title")} description={undefined} />
        <ul className="mt-4 grid gap-2 text-sm text-foreground/80 md:grid-cols-2">
          <SecurityItem label={t("settings.security.api_keys")} />
          <SecurityItem label={t("settings.security.tools")} />
          <SecurityItem label={t("settings.security.writes")} />
          <SecurityItem label={t("settings.security.external")} />
        </ul>
      </Panel>

      {/* model API configuration */}
      <ModelConfigPanel />

      {/* model intelligence test */}
      <ModelTestPanel />
    </div>
  );
}

function SectionHeader({ title, description }: { title: string; description?: string }) {
  return (
    <div>
      <h2 className="text-sm font-semibold text-foreground">{title}</h2>
      {description ? <p className="mt-1 text-sm leading-6 text-muted">{description}</p> : null}
    </div>
  );
}

function SecurityItem({ label }: { label: string }) {
  return (
    <li className="flex items-center gap-2 rounded-md border border-border bg-panel-muted px-3 py-2">
      <Check className="h-4 w-4 text-success" aria-hidden="true" />
      <span>{label}</span>
    </li>
  );
}

function ChoiceCard({
  title,
  description,
  selected,
  onClick,
  tag,
}: {
  title: string;
  description: string;
  selected: boolean;
  onClick: () => void;
  tag: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "group flex items-start gap-3 rounded-panel border p-4 text-left transition",
        selected
          ? "border-accent bg-accent-soft shadow-panel"
          : "border-border bg-panel hover:border-border-strong hover:bg-panel-muted",
      )}
    >
      <span
        className={cn(
          "mt-1 inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-xs font-bold",
          selected ? "bg-accent text-accent-foreground" : "bg-panel-muted text-muted",
        )}
      >
        {tag}
      </span>
      <span className="flex-1">
        <span className="block text-sm font-semibold text-foreground">{title}</span>
        <span className="mt-1 block text-xs leading-5 text-muted">{description}</span>
      </span>
      {selected ? <Check className="h-4 w-4 text-accent" aria-hidden="true" /> : null}
    </button>
  );
}

function PaletteCard({
  palette,
  appearance,
  selected,
  title,
  description,
  onClick,
}: {
  palette: Palette;
  appearance: "light" | "dark";
  selected: boolean;
  title: string;
  description: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "group flex flex-col gap-3 rounded-panel border p-4 text-left transition",
        selected
          ? "border-accent shadow-panel"
          : "border-border hover:border-border-strong",
      )}
      data-theme={palette}
      data-appearance={appearance}
      style={{ background: "rgb(var(--color-panel))" }}
    >
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold" style={{ color: "rgb(var(--color-foreground))" }}>
          {title}
        </span>
        {selected ? <Check className="h-4 w-4" style={{ color: "rgb(var(--color-accent))" }} aria-hidden="true" /> : null}
      </div>
      <div className="flex items-center gap-1.5">
        <Swatch token="background" />
        <Swatch token="panel" />
        <Swatch token="accent" />
        <Swatch token="ink" />
        <Swatch token="muted" />
      </div>
      <p className="text-xs leading-5" style={{ color: "rgb(var(--color-muted))" }}>
        {description}
      </p>
    </button>
  );
}

function Swatch({ token }: { token: string }) {
  return (
    <span
      className="h-6 w-6 rounded-md border"
      style={{
        background: `rgb(var(--color-${token}))`,
        borderColor: `rgb(var(--color-border))`,
      }}
    />
  );
}

function ModeCard({
  title,
  tag,
  description,
  selected,
  onClick,
}: {
  title: string;
  tag: string;
  description: string;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex flex-col gap-3 rounded-panel border p-4 text-left transition",
        selected
          ? "border-accent bg-accent-soft shadow-panel"
          : "border-border bg-panel hover:border-border-strong hover:bg-panel-muted",
      )}
    >
      <div className="flex items-center gap-2">
        <span
          className={cn(
            "inline-flex h-6 min-w-6 items-center justify-center rounded-sm px-1.5 text-[11px] font-bold",
            selected ? "bg-accent text-accent-foreground" : "bg-panel-muted text-muted",
          )}
        >
          {tag}
        </span>
        <span className="text-sm font-semibold text-foreground">{title}</span>
      </div>
      <p className="text-xs leading-5 text-muted">{description}</p>
    </button>
  );
}

function SimpleModePanel({ language }: { language: "zh-CN" | "en" }) {
  return (
    <div className="rounded-panel border border-dashed border-border bg-panel-muted p-4">
      <div className="text-xs font-semibold uppercase tracking-widest text-muted">
        {language === "zh-CN" ? "简单模式自动项" : "Simple mode automations"}
      </div>
      <ul className="mt-3 grid gap-2">
        {SIMPLE_MODE_AUTOMATION.map((entry) => (
          <li
            key={entry.id}
            className="flex items-start gap-2 rounded-md border border-border bg-panel px-3 py-2 text-sm leading-6 text-foreground/80"
          >
            <Check className="mt-0.5 h-4 w-4 shrink-0 text-success" aria-hidden="true" />
            <span>{entry.label[language]}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ProfessionalModePanel({
  professional,
  setProfessionalValue,
  resetProfessional,
  language,
  t,
}: {
  professional: Record<string, string | number | boolean>;
  setProfessionalValue: (id: string, value: string | number | boolean) => void;
  resetProfessional: () => void;
  language: "zh-CN" | "en";
  t: (key: string) => string;
}) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="text-xs font-semibold uppercase tracking-widest text-muted">
          {language === "zh-CN" ? "可调参数" : "Tunable parameters"}
        </div>
        <Button variant="ghost" onClick={resetProfessional}>
          {t("common.reset")}
        </Button>
      </div>
      <div className="grid gap-4 xl:grid-cols-2">
        {PROFESSIONAL_SECTIONS.map((section) => (
          <ProfessionalSectionCard
            key={section}
            section={section}
            language={language}
            professional={professional}
            setProfessionalValue={setProfessionalValue}
            t={t}
          />
        ))}
      </div>
    </div>
  );
}

function ProfessionalSectionCard({
  section,
  language,
  professional,
  setProfessionalValue,
  t,
}: {
  section: ProfessionalSection;
  language: "zh-CN" | "en";
  professional: Record<string, string | number | boolean>;
  setProfessionalValue: (id: string, value: string | number | boolean) => void;
  t: (key: string) => string;
}) {
  const parameters = parametersBySection(section);
  return (
    <div className="rounded-panel border border-border bg-panel p-4">
      <div className="mb-3 text-sm font-semibold text-foreground">
        {t(`settings.professional.section.${section}`)}
      </div>
      <div className="space-y-4">
        {parameters.map((parameter) => (
          <ProfessionalParameter
            key={parameter.id}
            parameter={parameter}
            language={language}
            value={professional[parameter.id]}
            onChange={(value) => setProfessionalValue(parameter.id, value)}
          />
        ))}
      </div>
    </div>
  );
}

function ProfessionalParameter({
  parameter,
  language,
  value,
  onChange,
}: {
  parameter: ParameterDefinition;
  language: "zh-CN" | "en";
  value: string | number | boolean | undefined;
  onChange: (value: string | number | boolean) => void;
}) {
  return (
    <div className="rounded-md border border-border bg-panel-muted p-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-foreground">{parameter.label[language]}</div>
          <p className="mt-1 text-xs leading-5 text-muted">{parameter.description[language]}</p>
        </div>
        <Badge className="whitespace-nowrap">{parameter.id}</Badge>
      </div>
      <div className="mt-3">
        {parameter.kind === "toggle" ? (
          <ToggleControl
            value={Boolean(value ?? parameter.defaultValue)}
            onChange={onChange}
            language={language}
          />
        ) : null}
        {parameter.kind === "slider" ? (
          <SliderControl
            parameter={parameter}
            value={Number(value ?? parameter.defaultValue)}
            onChange={onChange}
          />
        ) : null}
        {parameter.kind === "select" ? (
          <Select
            value={String(value ?? parameter.defaultValue)}
            onChange={(event) => onChange(event.target.value)}
          >
            {parameter.options.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label[language]}
              </option>
            ))}
          </Select>
        ) : null}
      </div>
      <div className="mt-2 text-[11px] text-muted">ref. {parameter.reference}</div>
    </div>
  );
}

function ToggleControl({
  value,
  onChange,
  language,
}: {
  value: boolean;
  onChange: (value: boolean) => void;
  language: "zh-CN" | "en";
}) {
  const onLabel = language === "zh-CN" ? "开启" : "On";
  const offLabel = language === "zh-CN" ? "关闭" : "Off";
  return (
    <button
      type="button"
      onClick={() => onChange(!value)}
      className={cn(
        "inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-xs font-semibold transition",
        value
          ? "border-accent bg-accent-soft text-foreground"
          : "border-border bg-panel text-foreground/80 hover:bg-panel-muted",
      )}
    >
      <span
        className={cn(
          "inline-block h-2 w-2 rounded-full",
          value ? "bg-accent" : "bg-muted",
        )}
        aria-hidden="true"
      />
      {value ? onLabel : offLabel}
    </button>
  );
}

function SliderControl({
  parameter,
  value,
  onChange,
}: {
  parameter: Extract<ParameterDefinition, { kind: "slider" }>;
  value: number;
  onChange: (value: number) => void;
}) {
  const percent = ((value - parameter.min) / (parameter.max - parameter.min)) * 100;
  return (
    <div className="space-y-2">
      <input
        type="range"
        min={parameter.min}
        max={parameter.max}
        step={parameter.step}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        className="h-2 w-full cursor-pointer appearance-none rounded-full bg-panel-muted"
        style={{
          backgroundImage: `linear-gradient(to right, rgb(var(--color-accent)) 0%, rgb(var(--color-accent)) ${percent}%, rgb(var(--color-border)) ${percent}%, rgb(var(--color-border)) 100%)`,
        }}
      />
      <div className="flex items-center justify-between text-xs text-muted">
        <span>{parameter.min}</span>
        <span className="font-semibold text-foreground">{formatSliderValue(parameter, value)}</span>
        <span>{parameter.max}</span>
      </div>
    </div>
  );
}

function formatSliderValue(
  parameter: Extract<ParameterDefinition, { kind: "slider" }>,
  value: number,
): string {
  if (parameter.unit === "ratio") {
    return `${Math.round(value * 100)}%`;
  }
  if (parameter.step < 1) {
    return value.toFixed(2);
  }
  return String(value);
}
