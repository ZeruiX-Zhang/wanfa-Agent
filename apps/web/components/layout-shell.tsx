"use client";

import {
  Activity,
  BadgeCheck,
  BookOpen,
  Bot,
  ChevronDown,
  ChevronUp,
  Compass,
  Database,
  FileText,
  GitBranch,
  Home,
  Inbox,
  Layers,
  LayoutDashboard,
  LifeBuoy,
  Moon,
  Network,
  Quote,
  RefreshCcw,
  Search,
  Settings as SettingsIcon,
  ShieldCheck,
  Sparkles,
  Sun,
  Target,
  Wand2,
  Zap,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";

import { usePreferences } from "@/components/preferences-provider";
import { Button } from "@/components/ui";
import { cn } from "@/lib/utils";

type NavItem = {
  href: string;
  labelKey: string;
  icon: typeof Home;
};

const primaryNav: NavItem[] = [
  { href: "/", labelKey: "nav.home", icon: Home },
  { href: "/ask", labelKey: "nav.ask", icon: Compass },
  { href: "/capture", labelKey: "nav.capture", icon: Inbox },
  { href: "/library", labelKey: "nav.library", icon: BookOpen },
  { href: "/prompt", labelKey: "nav.prompt", icon: Wand2 },
  { href: "/supervise", labelKey: "nav.supervise", icon: Bot },
  { href: "/learn", labelKey: "nav.learn", icon: LifeBuoy },
  { href: "/eval", labelKey: "nav.eval", icon: Activity },
  { href: "/settings", labelKey: "nav.settings", icon: SettingsIcon },
];

const legacyNav: NavItem[] = [
  { href: "/dashboard", labelKey: "nav.dashboard", icon: LayoutDashboard },
  { href: "/input", labelKey: "nav.input", icon: Layers },
  { href: "/decision/demo-case", labelKey: "nav.decision", icon: FileText },
  { href: "/knowledge", labelKey: "nav.knowledge", icon: Database },
  { href: "/search", labelKey: "nav.search", icon: Search },
  { href: "/verification/demo-verification", labelKey: "nav.verification", icon: BadgeCheck },
  { href: "/workflow", labelKey: "nav.workflow", icon: GitBranch },
  { href: "/supervisor", labelKey: "nav.supervisor", icon: Bot },
  { href: "/reflection", labelKey: "nav.reflection", icon: RefreshCcw },
  { href: "/speed-mode", labelKey: "nav.speed", icon: Zap },
  { href: "/clusters", labelKey: "nav.clusters", icon: Network },
  { href: "/evidence", labelKey: "nav.evidence", icon: Quote },
  { href: "/sources", labelKey: "nav.sources", icon: Database },
  { href: "/compliance", labelKey: "nav.compliance", icon: ShieldCheck },
  { href: "/watchlists", labelKey: "nav.watchlists", icon: Target },
  { href: "/reports", labelKey: "nav.reports", icon: FileText },
  { href: "/jobs", labelKey: "nav.jobs", icon: Sparkles },
];

function isActive(pathname: string, href: string) {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function LayoutShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { preferences, setLanguage, setAppearance, setMode, t } = usePreferences();
  const [legacyOpen, setLegacyOpen] = useState(() =>
    legacyNav.some((item) => pathname === item.href || pathname.startsWith(`${item.href}/`)),
  );
  const isDark = preferences.appearance === "dark";
  const allItems = [...primaryNav, ...(legacyOpen ? legacyNav : [])];

  return (
    <div className="min-h-screen bg-background text-foreground">
      <aside className="fixed inset-y-0 left-0 hidden w-72 overflow-y-auto border-r border-border bg-panel px-3 py-4 lg:block">
        <div className="mb-6 flex items-center gap-3 px-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-panel bg-ink text-accent-foreground shadow-panel">
            <Sparkles className="h-5 w-5" aria-hidden="true" />
          </div>
          <div>
            <div className="text-sm font-bold tracking-tight text-foreground">{t("app.name")}</div>
            <div className="text-xs text-muted">{t("app.tagline")}</div>
          </div>
        </div>

        <nav className="space-y-4" aria-label="Main navigation">
          <div>
            <div className="px-3 pb-2 text-[11px] font-semibold uppercase tracking-widest text-muted">
              {t("nav.section.reality")}
            </div>
            <div className="space-y-1">
              {primaryNav.map((item) => {
                const active = isActive(pathname, item.href);
                const Icon = item.icon;
                return (
                  <Link
                    href={item.href}
                    key={item.href}
                    className={cn(
                      "flex min-h-10 items-center gap-2 rounded-md px-3 py-2 text-sm text-foreground/80 transition-colors hover:bg-panel-muted",
                      active && "bg-accent-soft font-semibold text-foreground",
                    )}
                  >
                    <Icon className={cn("h-4 w-4 shrink-0", active ? "text-accent" : "text-muted")} aria-hidden="true" />
                    <span className="truncate">{t(item.labelKey)}</span>
                  </Link>
                );
              })}
            </div>
          </div>

          <div>
            <button
              type="button"
              onClick={() => setLegacyOpen((value) => !value)}
              className="flex w-full items-center justify-between gap-2 rounded-md px-3 py-1.5 text-[11px] font-semibold uppercase tracking-widest text-muted hover:bg-panel-muted"
            >
              {t("nav.section.legacy")}
              {legacyOpen ? (
                <ChevronUp className="h-3.5 w-3.5" aria-hidden="true" />
              ) : (
                <ChevronDown className="h-3.5 w-3.5" aria-hidden="true" />
              )}
            </button>
            {legacyOpen ? (
              <div className="mt-1 space-y-1">
                {legacyNav.map((item) => {
                  const active = isActive(pathname, item.href);
                  const Icon = item.icon;
                  return (
                    <Link
                      href={item.href}
                      key={item.href}
                      className={cn(
                        "flex min-h-9 items-center gap-2 rounded-md px-3 py-1.5 text-xs text-foreground/70 transition-colors hover:bg-panel-muted",
                        active && "bg-accent-soft font-semibold text-foreground",
                      )}
                    >
                      <Icon className={cn("h-4 w-4 shrink-0", active ? "text-accent" : "text-muted")} aria-hidden="true" />
                      <span className="truncate">{t(item.labelKey)}</span>
                    </Link>
                  );
                })}
              </div>
            ) : null}
          </div>
        </nav>
      </aside>

      <main className="lg:pl-72">
        <div className="sticky top-0 z-30 flex items-center justify-between gap-3 border-b border-border bg-panel/90 px-4 py-2 backdrop-blur">
          <div className="flex items-center gap-2 lg:hidden">
            <div className="flex h-8 w-8 items-center justify-center rounded-md bg-ink text-accent-foreground">
              <Sparkles className="h-4 w-4" aria-hidden="true" />
            </div>
            <div className="text-sm font-semibold">{t("app.name")}</div>
          </div>
          <div className="hidden text-xs text-muted lg:block">{t("app.tagline")}</div>
          <div className="flex items-center gap-2">
            <ModePill
              label={preferences.mode === "professional" ? t("common.professional_mode") : t("common.simple_mode")}
              badge={preferences.mode === "professional" ? t("mode.professional.badge") : t("mode.simple.badge")}
              active
              onClick={() => setMode(preferences.mode === "simple" ? "professional" : "simple")}
            />
            <Button
              variant="ghost"
              className="h-8 px-2"
              onClick={() => setAppearance(isDark ? "light" : "dark")}
              aria-label="toggle appearance"
            >
              {isDark ? <Sun className="h-4 w-4" aria-hidden="true" /> : <Moon className="h-4 w-4" aria-hidden="true" />}
            </Button>
            <Button
              variant="ghost"
              className="h-8 px-2 text-xs font-semibold"
              onClick={() => setLanguage(preferences.language === "zh-CN" ? "en" : "zh-CN")}
              aria-label="toggle language"
            >
              {preferences.language === "zh-CN" ? "EN" : "中"}
            </Button>
          </div>
        </div>

        <div className="border-b border-border bg-panel px-4 py-3 lg:hidden">
          <div className="mt-1 flex gap-2 overflow-x-auto pb-1">
            {allItems.map((item) => {
              const active = isActive(pathname, item.href);
              const Icon = item.icon;
              return (
                <Link
                  className={cn(
                    "inline-flex min-h-8 items-center gap-1 whitespace-nowrap rounded-md border border-border bg-panel-muted px-2 py-1 text-xs text-foreground/80",
                    active && "border-accent bg-accent-soft text-foreground",
                  )}
                  href={item.href}
                  key={item.href}
                >
                  <Icon className="h-3.5 w-3.5" aria-hidden="true" />
                  {t(item.labelKey)}
                </Link>
              );
            })}
          </div>
        </div>

        <div className="mx-auto max-w-7xl px-4 py-5">{children}</div>
      </main>
    </div>
  );
}

function ModePill({
  label,
  badge,
  active,
  onClick,
}: {
  label: string;
  badge: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "inline-flex h-8 items-center gap-1.5 rounded-md border px-2 text-xs font-semibold transition",
        active
          ? "border-accent bg-accent-soft text-foreground"
          : "border-border bg-panel text-foreground/80 hover:bg-panel-muted",
      )}
    >
      <span
        className={cn(
          "inline-flex h-5 min-w-5 items-center justify-center rounded-sm px-1 text-[10px]",
          active ? "bg-accent text-accent-foreground" : "bg-panel-muted text-muted",
        )}
      >
        {badge}
      </span>
      {label}
    </button>
  );
}
