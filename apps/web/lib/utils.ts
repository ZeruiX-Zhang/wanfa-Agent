import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function fmtDate(value: string | null | undefined, locale: string = "zh-CN") {
  if (!value) return locale === "zh-CN" ? "暂无" : "n/a";
  return new Intl.DateTimeFormat(locale, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function pct(value: number | null | undefined, locale: string = "zh-CN") {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return locale === "zh-CN" ? "暂无" : "n/a";
  }
  return `${Math.round(value * 100)}%`;
}

export function compactNumber(value: number | null | undefined, locale: string = "en-US") {
  if (value === null || value === undefined || Number.isNaN(value)) return locale === "zh-CN" ? "暂无" : "n/a";
  return new Intl.NumberFormat(locale, { maximumFractionDigits: 1 }).format(value);
}

export function unique<T>(items: T[]) {
  return Array.from(new Set(items));
}
