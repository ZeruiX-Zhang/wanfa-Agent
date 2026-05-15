/**
 * User-level UI preferences: language, theme palette, light/dark, and workflow mode.
 *
 * Persistence strategy:
 *  - localStorage (client-side) for fast hydration.
 *  - Non-HttpOnly cookie (readable on the server) so server-rendered pages can
 *    apply the correct `<html lang>` / `<html data-theme>` without a flash.
 */

export const LANGUAGES = ["zh-CN", "en"] as const;
export type Language = (typeof LANGUAGES)[number];

export const PALETTES = ["obsidian", "pearl", "graphite", "aurora"] as const;
export type Palette = (typeof PALETTES)[number];

export const APPEARANCES = ["light", "dark"] as const;
export type Appearance = (typeof APPEARANCES)[number];

export const MODES = ["simple", "professional"] as const;
export type Mode = (typeof MODES)[number];

export type Preferences = {
  language: Language;
  palette: Palette;
  appearance: Appearance;
  mode: Mode;
};

export const DEFAULT_PREFERENCES: Preferences = {
  language: "zh-CN",
  palette: "obsidian",
  appearance: "light",
  mode: "simple",
};

export const PREFERENCE_COOKIE = "reality-os-prefs";
export const PREFERENCE_STORAGE_KEY = "reality-os:preferences";
const COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 365;

export const PALETTE_LABELS: Record<Palette, { "zh-CN": string; en: string }> = {
  obsidian: { "zh-CN": "曜石", en: "Obsidian" },
  pearl: { "zh-CN": "月白", en: "Pearl" },
  graphite: { "zh-CN": "石墨", en: "Graphite" },
  aurora: { "zh-CN": "极光", en: "Aurora" },
};

export const PALETTE_DESCRIPTIONS: Record<Palette, { "zh-CN": string; en: string }> = {
  obsidian: {
    "zh-CN": "极简深蓝灰，专注、沉稳，长期工作首选。",
    en: "Calm navy-graphite. Minimal, focused, meant for long sessions.",
  },
  pearl: {
    "zh-CN": "白底象牙色，线条克制，阅读密度更高。",
    en: "Ivory on soft white. Restrained, high reading density.",
  },
  graphite: {
    "zh-CN": "纯黑灰度，工程感强，深色优先。",
    en: "Pure graphite. Engineering feel, dark-mode native.",
  },
  aurora: {
    "zh-CN": "冷蓝 + 青色点缀，数据密集界面不易疲劳。",
    en: "Cool blue with teal accents. Data-heavy UI, less eye fatigue.",
  },
};

export function isLanguage(value: unknown): value is Language {
  return typeof value === "string" && (LANGUAGES as readonly string[]).includes(value);
}

export function isPalette(value: unknown): value is Palette {
  return typeof value === "string" && (PALETTES as readonly string[]).includes(value);
}

export function isAppearance(value: unknown): value is Appearance {
  return typeof value === "string" && (APPEARANCES as readonly string[]).includes(value);
}

export function isMode(value: unknown): value is Mode {
  return typeof value === "string" && (MODES as readonly string[]).includes(value);
}

export function sanitizePreferences(raw: unknown): Preferences {
  if (!raw || typeof raw !== "object") {
    return { ...DEFAULT_PREFERENCES };
  }
  const record = raw as Record<string, unknown>;
  return {
    language: isLanguage(record.language) ? record.language : DEFAULT_PREFERENCES.language,
    palette: isPalette(record.palette) ? record.palette : DEFAULT_PREFERENCES.palette,
    appearance: isAppearance(record.appearance) ? record.appearance : DEFAULT_PREFERENCES.appearance,
    mode: isMode(record.mode) ? record.mode : DEFAULT_PREFERENCES.mode,
  };
}

export function encodePreferences(preferences: Preferences): string {
  return encodeURIComponent(JSON.stringify(preferences));
}

export function decodePreferences(cookieValue: string | null | undefined): Preferences {
  if (!cookieValue) {
    return { ...DEFAULT_PREFERENCES };
  }
  try {
    const decoded = decodeURIComponent(cookieValue);
    return sanitizePreferences(JSON.parse(decoded));
  } catch {
    return { ...DEFAULT_PREFERENCES };
  }
}

export function writePreferencesCookie(preferences: Preferences): void {
  if (typeof document === "undefined") return;
  const value = encodePreferences(preferences);
  document.cookie = `${PREFERENCE_COOKIE}=${value}; path=/; max-age=${COOKIE_MAX_AGE_SECONDS}; samesite=lax`;
}

export function readPreferencesCookieFromDocument(): Preferences | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.split("; ").find((entry) => entry.startsWith(`${PREFERENCE_COOKIE}=`));
  if (!match) return null;
  return decodePreferences(match.slice(PREFERENCE_COOKIE.length + 1));
}
