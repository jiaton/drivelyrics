import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { en, type Dictionary } from "./en";
import { zh } from "./zh";

export type Lang = "en" | "zh";
const DICTIONARIES: Record<Lang, Dictionary> = { en, zh };
const STORAGE_KEY = "lang";

/**
 * UI language. English unless the browser prefers Chinese; a manual switch is remembered
 * in localStorage. (localStorage is right here, unlike user preferences: the language
 * applies before anyone signs in — the landing page — and is a property of the device.)
 */
export function detectLang(preferred: readonly string[]): Lang {
  // The browser's languages are in preference order: the first English or Chinese one
  // wins. ("en-US, zh-CN" is an English reader who also reads Chinese — not a Chinese one.)
  for (const tag of preferred) {
    const l = tag?.toLowerCase() ?? "";
    if (l.startsWith("zh")) return "zh";
    if (l.startsWith("en")) return "en";
  }
  return "en";
}

function initialLang(): Lang {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved === "en" || saved === "zh") return saved;
  return detectLang(navigator.languages?.length ? navigator.languages : [navigator.language]);
}

interface I18n {
  lang: Lang;
  t: Dictionary;
  setLang: (lang: Lang) => void;
}

const I18nContext = createContext<I18n | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(initialLang);

  useEffect(() => {
    document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";
  }, [lang]);

  const setLang = useCallback((next: Lang) => {
    localStorage.setItem(STORAGE_KEY, next);
    setLangState(next);
  }, []);

  const value = useMemo(() => ({ lang, t: DICTIONARIES[lang], setLang }), [lang, setLang]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18n {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n outside I18nProvider");
  return ctx;
}
