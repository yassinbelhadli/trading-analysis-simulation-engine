"use client";

/**
 * Global locale context for the Client Dashboard.
 *
 * Language / Currency / Timezone are persistent user preferences stored in
 * the backend (GET/PATCH /api/client/settings). The frontend loads them once
 * and keeps them synchronized. Arabic applies RTL to the document.
 */

import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from "react";
import { getClientSettings, updateClientSettings } from "@/lib/api";
import { DEFAULT_TIMEZONE } from "@/lib/timezone";
import { translate, type Lang } from "@/lib/i18n";

export const LANGUAGES = ["EN", "FR", "AR", "ES"] as const;
export const CURRENCIES = ["MAD", "USD", "EUR"] as const;
export type Language = (typeof LANGUAGES)[number];
export type Currency = (typeof CURRENCIES)[number];

interface LocaleContextValue {
  language: Language;
  currency: Currency;
  timezone: string;
  loading: boolean;
  t: (key: string, vars?: Record<string, string | number>) => string;
  setLanguage: (lang: Language) => Promise<void>;
  setCurrency: (cur: Currency) => Promise<void>;
  setTimezone: (tz: string) => Promise<void>;
  refresh: () => Promise<void>;
}

const LocaleContext = createContext<LocaleContextValue | null>(null);

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>("EN");
  const [currency, setCurrencyState] = useState<Currency>("MAD");
  const [timezone, setTimezoneState] = useState<string>(DEFAULT_TIMEZONE);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const s = await getClientSettings();
      const lang = (s.language || "EN").toUpperCase();
      if ((LANGUAGES as readonly string[]).includes(lang)) setLanguageState(lang as Language);
      const cur = (s.billing_currency || "MAD").toUpperCase();
      if ((CURRENCIES as readonly string[]).includes(cur)) setCurrencyState(cur as Currency);
      if (s.timezone) setTimezoneState(s.timezone);
    } catch {
      // Keep defaults if settings cannot be loaded (e.g. transient network error)
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // Apply RTL for Arabic
  useEffect(() => {
    document.documentElement.dir = language === "AR" ? "rtl" : "ltr";
    document.documentElement.lang = language.toLowerCase();
  }, [language]);

  const setLanguage = useCallback(async (lang: Language) => {
    setLanguageState(lang);
    try {
      await updateClientSettings({ language: lang });
    } catch {
      // Optimistic update; backend sync failure is non-fatal for the UI
    }
  }, []);

  const setCurrency = useCallback(async (cur: Currency) => {
    setCurrencyState(cur);
    try {
      await updateClientSettings({ billing_currency: cur });
    } catch {
      // Optimistic update
    }
  }, []);

  const setTimezone = useCallback(async (tz: string) => {
    setTimezoneState(tz);
    try {
      await updateClientSettings({ timezone: tz });
    } catch {
      // Optimistic update
    }
  }, []);

  const t = useCallback(
    (key: string, vars?: Record<string, string | number>) => translate(language as Lang, key, vars),
    [language]
  );

  return (
    <LocaleContext.Provider value={{ language, currency, timezone, loading, t, setLanguage, setCurrency, setTimezone, refresh }}>
      {children}
    </LocaleContext.Provider>
  );
}

export function useLocale(): LocaleContextValue {
  const ctx = useContext(LocaleContext);
  if (!ctx) throw new Error("useLocale must be used within LocaleProvider");
  return ctx;
}