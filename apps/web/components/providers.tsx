"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactNode, useState } from "react";

import { PreferencesProvider } from "@/components/preferences-provider";
import type { Preferences } from "@/lib/preferences";

export function Providers({
  children,
  initialPreferences,
}: {
  children: ReactNode;
  initialPreferences?: Preferences;
}) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 20_000,
            retry: 1,
          },
        },
      }),
  );
  return (
    <QueryClientProvider client={client}>
      <PreferencesProvider initialPreferences={initialPreferences}>{children}</PreferencesProvider>
    </QueryClientProvider>
  );
}
