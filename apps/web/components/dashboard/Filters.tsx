"use client";

import { usePreferences } from "@/components/preferences-provider";
import { Select } from "@/components/ui";

/**
 * Professional_Mode-only dashboard controls (R10.4).
 *
 * Simple_Mode renders no controls at all, so this component is only
 * mounted by :component:`LearningDashboard` when ``mode === professional``.
 */
export function Filters({
  domains,
  value,
  onChange,
}: {
  domains: string[];
  value: string;
  onChange: (next: string) => void;
}) {
  const { t } = usePreferences();
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-muted">{t("dash.mastery")}</span>
      <Select value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">{t("dash.empty")}</option>
        {domains.map((domain) => (
          <option key={domain} value={domain}>
            {domain}
          </option>
        ))}
      </Select>
    </div>
  );
}
