import type { Metadata } from "next";
import { cookies } from "next/headers";

import "./globals.css";
import { LayoutShell } from "@/components/layout-shell";
import { Providers } from "@/components/providers";
import { PREFERENCE_COOKIE, decodePreferences } from "@/lib/preferences";

export const metadata: Metadata = {
  title: "Reality OS",
  description: "Human-agent reality capability operating system",
};

export default async function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const cookieStore = await cookies();
  const cookieValue = cookieStore.get(PREFERENCE_COOKIE)?.value;
  const preferences = decodePreferences(cookieValue);
  return (
    <html
      lang={preferences.language}
      data-theme={preferences.palette}
      data-appearance={preferences.appearance}
      data-mode={preferences.mode}
    >
      <body>
        <Providers initialPreferences={preferences}>
          <LayoutShell>{children}</LayoutShell>
        </Providers>
      </body>
    </html>
  );
}
