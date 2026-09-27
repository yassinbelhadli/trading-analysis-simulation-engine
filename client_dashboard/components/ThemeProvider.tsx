"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { getClientSettings } from "@/lib/api";

type Theme = "dark" | "light";

interface AppearanceCtx {
  theme: Theme;
  toggle: () => void;
  brandName: string;
  accentColor: string;
}

const Ctx = createContext<AppearanceCtx>({
  theme: "dark",
  toggle: () => {},
  brandName: "ICT EA Pro",
  accentColor: "#3b82f6",
});

function darken(hex: string, factor = 0.85): string {
  const m = hex.replace("#", "");
  if (!/^[0-9a-fA-F]{6}$/.test(m)) return "#2563eb";
  const r = Math.round(parseInt(m.slice(0, 2), 16) * factor);
  const g = Math.round(parseInt(m.slice(2, 4), 16) * factor);
  const b = Math.round(parseInt(m.slice(4, 6), 16) * factor);
  return `#${[r, g, b].map((c) => c.toString(16).padStart(2, "0")).join("")}`;
}

function resolveTheme(pref: string, stored: string | null): Theme {
  if (stored === "light" || stored === "dark") return stored;
  if (pref === "light") return "light";
  if (pref === "system") {
    return typeof window !== "undefined" && window.matchMedia("(prefers-color-scheme: light)").matches
      ? "light"
      : "dark";
  }
  return "dark";
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = useState<Theme>("dark");
  const [brandName, setBrandName] = useState("ICT EA Pro");
  const [accentColor, setAccentColor] = useState("#3b82f6");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    const stored = localStorage.getItem("theme");

    const applyClientPrefs = () => {
      getClientSettings()
        .then((s) => {
          const p = s.preferences || {};
          if (stored === "light" || stored === "dark") {
            setTheme(stored);
          } else {
            const pref = String(p.theme || "dark");
            setTheme(resolveTheme(pref, null));
          }
        })
        .catch(() => {
          if (stored === "light" || stored === "dark") setTheme(stored);
        });
    };

    applyClientPrefs();
    const onClientSaved = () => {};
    window.addEventListener("client-settings-saved", onClientSaved);
    return () => window.removeEventListener("client-settings-saved", onClientSaved);
  }, []);

  useEffect(() => {
    if (!mounted) return;
    document.documentElement.classList.toggle("light", theme === "light");
    localStorage.setItem("theme", theme);
  }, [theme, mounted]);

  const toggle = () => setTheme((t) => (t === "dark" ? "light" : "dark"));

  return (
    <Ctx.Provider value={{ theme, toggle, brandName, accentColor }}>
      {children}
    </Ctx.Provider>
  );
}

export const useTheme = () => useContext(Ctx);
