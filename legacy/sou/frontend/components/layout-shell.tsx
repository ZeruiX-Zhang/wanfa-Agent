"use client";

import {
  BarChart3,
  Bitcoin,
  BriefcaseBusiness,
  Database,
  FileText,
  Gauge,
  Network,
  Quote,
  ScanSearch,
  Settings,
  ShieldCheck,
  ShoppingCart,
  Sparkles,
  Target,
  Zap,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

const nav = [
  { href: "/", label: "Overview", icon: BarChart3 },
  { href: "/speed-mode", label: "Speed Mode", icon: Zap },
  { href: "/precision-mode", label: "Precision Mode", icon: ScanSearch },
  { href: "/clusters", label: "Clusters", icon: Network },
  { href: "/evidence", label: "Evidence", icon: Quote },
  { href: "/sources", label: "Sources", icon: Database },
  { href: "/compliance", label: "Compliance", icon: ShieldCheck },
  { href: "/watchlists", label: "Watchlists", icon: Target },
  { href: "/ai-product-reviews", label: "AI Product Reviews", icon: Sparkles },
  { href: "/crypto-monitor", label: "Crypto Monitor", icon: Bitcoin },
  { href: "/ecommerce-monitor", label: "Ecommerce Monitor", icon: ShoppingCart },
  { href: "/reports", label: "Reports", icon: FileText },
  { href: "/jobs", label: "Jobs", icon: BriefcaseBusiness },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function LayoutShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  return (
    <div className="min-h-screen bg-background">
      <aside className="fixed inset-y-0 left-0 hidden w-72 border-r border-border bg-panel px-3 py-4 lg:block">
        <div className="mb-5 flex items-center gap-3 px-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-md bg-ink text-white">
            <Gauge className="h-5 w-5" aria-hidden="true" />
          </div>
          <div>
            <div className="text-sm font-bold">Intel Agent</div>
            <div className="text-xs text-muted">Evidence-first intelligence UI</div>
          </div>
        </div>
        <nav className="space-y-1">
          {nav.map((item) => {
            const active = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
            const Icon = item.icon;
            return (
              <Link
                href={item.href}
                key={item.href}
                className={cn(
                  "flex min-h-10 items-center gap-2 rounded-md px-3 py-2 text-sm text-slate-700 hover:bg-slate-50",
                  active && "bg-teal-50 font-semibold text-teal-900",
                )}
              >
                <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                <span className="truncate">{item.label}</span>
              </Link>
            );
          })}
        </nav>
      </aside>
      <main className="lg:pl-72">
        <div className="border-b border-border bg-panel px-4 py-3 lg:hidden">
          <div className="text-sm font-bold">Intel Agent</div>
          <div className="mt-2 flex gap-2 overflow-x-auto pb-1">
            {nav.map((item) => (
              <Link
                className={cn(
                  "whitespace-nowrap rounded-md border border-border px-2 py-1 text-xs",
                  pathname === item.href && "border-teal-300 bg-teal-50 text-teal-900",
                )}
                href={item.href}
                key={item.href}
              >
                {item.label}
              </Link>
            ))}
          </div>
        </div>
        <div className="mx-auto max-w-7xl px-4 py-5">{children}</div>
      </main>
    </div>
  );
}
