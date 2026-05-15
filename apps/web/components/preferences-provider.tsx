"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import {
  DEFAULT_PREFERENCES,
  PREFERENCE_STORAGE_KEY,
  sanitizePreferences,
  writePreferencesCookie,
  type Appearance,
  type Language,
  type Mode,
  type Palette,
  type Preferences,
} from "@/lib/preferences";
import { translate } from "@/lib/i18n";
import {
  PROFESSIONAL_PARAMETERS,
  defaultProfessionalValues,
  type ProfessionalParameterValues,
} from "@/lib/professional-parameters";

const PRO_STORAGE_KEY = "reality-os:professional-parameters";

type PreferencesContextValue = {
  preferences: Preferences;
  professional: ProfessionalParameterValues;
  isHydrated: boolean;
  setLanguage: (value: Language) => void;
  setPalette: (value: Palette) => void;
  setAppearance: (value: Appearance) => void;
  setMode: (value: Mode) => void;
  setPreferences: (partial: Partial<Preferences>) => void;
  setProfessionalValue: (id: string, value: string | number | boolean) => void;
  resetProfessional: () => void;
  t: (key: string) => string;
};

const PreferencesContext = createContext<PreferencesContextValue | null>(null);

function applyHtmlAttributes(preferences: Preferences) {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  root.dataset.theme = preferences.palette;
  root.dataset.appearance = preferences.appearance;
  root.dataset.mode = preferences.mode;
  root.setAttribute("lang", preferences.language);
}

function loadProfessional(): ProfessionalParameterValues {
  if (typeof window === "undefined") return defaultProfessionalValues();
  try {
    const raw = window.localStorage.getItem(PRO_STORAGE_KEY);
    if (!raw) return defaultProfessionalValues();
    const parsed = JSON.parse(raw) as ProfessionalParameterValues;
    const defaults = defaultProfessionalValues();
    const merged: ProfessionalParameterValues = { ...defaults };
    for (const parameter of PROFESSIONAL_PARAMETERS) {
      const candidate = parsed[parameter.id];
      if (candidate === undefined) continue;
      if (parameter.kind === "toggle" && typeof candidate === "boolean") {
        merged[parameter.id] = candidate;
      } else if (parameter.kind === "slider" && typeof candidate === "number" && Number.isFinite(candidate)) {
        merged[parameter.id] = Math.min(parameter.max, Math.max(parameter.min, candidate));
      } else if (parameter.kind === "select" && typeof candidate === "string") {
        const allowed = parameter.options.some((option) => option.value === candidate);
        if (allowed) merged[parameter.id] = candidate;
      }
    }
    return merged;
  } catch {
    return defaultProfessionalValues();
  }
}

export function PreferencesProvider({
  children,
  initialPreferences,
}: {
  children: ReactNode;
  initialPreferences?: Preferences;
}) {
  const seed = initialPreferences ? sanitizePreferences(initialPreferences) : DEFAULT_PREFERENCES;
  const [preferences, setPreferencesState] = useState<Preferences>(seed);
  const [professional, setProfessional] = useState<ProfessionalParameterValues>(defaultProfessionalValues);
  const [isHydrated, setIsHydrated] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    let loaded: Preferences = seed;
    try {
      const raw = window.localStorage.getItem(PREFERENCE_STORAGE_KEY);
      if (raw) {
        loaded = sanitizePreferences(JSON.parse(raw));
      }
    } catch {
      loaded = seed;
    }
    setPreferencesState(loaded);
    applyHtmlAttributes(loaded);
    writePreferencesCookie(loaded);
    setProfessional(loadProfessional());
    setIsHydrated(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!isHydrated) return;
    applyHtmlAttributes(preferences);
    writePreferencesCookie(preferences);
    try {
      window.localStorage.setItem(PREFERENCE_STORAGE_KEY, JSON.stringify(preferences));
    } catch {
      /* storage full or blocked; cookie still holds the state */
    }
  }, [preferences, isHydrated]);

  useEffect(() => {
    if (!isHydrated) return;
    try {
      window.localStorage.setItem(PRO_STORAGE_KEY, JSON.stringify(professional));
    } catch {
      /* ignore */
    }
  }, [professional, isHydrated]);

  const setPreferences = useCallback((partial: Partial<Preferences>) => {
    setPreferencesState((previous) => sanitizePreferences({ ...previous, ...partial }));
  }, []);

  const setProfessionalValue = useCallback((id: string, value: string | number | boolean) => {
    setProfessional((previous) => ({ ...previous, [id]: value }));
  }, []);

  const resetProfessional = useCallback(() => {
    setProfessional(defaultProfessionalValues());
  }, []);

  const value = useMemo<PreferencesContextValue>(() => {
    const t = (key: string) => translate(preferences.language, key);
    return {
      preferences,
      professional,
      isHydrated,
      setLanguage: (language) => setPreferences({ language }),
      setPalette: (palette) => setPreferences({ palette }),
      setAppearance: (appearance) => setPreferences({ appearance }),
      setMode: (mode) => setPreferences({ mode }),
      setPreferences,
      setProfessionalValue,
      resetProfessional,
      t,
    };
  }, [preferences, professional, isHydrated, setPreferences, setProfessionalValue, resetProfessional]);

  return <PreferencesContext.Provider value={value}>{children}</PreferencesContext.Provider>;
}

export function usePreferences(): PreferencesContextValue {
  const value = useContext(PreferencesContext);
  if (!value) {
    throw new Error("usePreferences must be used inside <PreferencesProvider>");
  }
  return value;
}

export function useTranslation() {
  const { t, preferences } = usePreferences();
  return { t, language: preferences.language };
}
