"use client";

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { Icon, type IconName } from "./Icon";

/* ==========================================================================
   Design System V2 — Toast notifications
   Usage:
     const toast = useToast();
     toast.success("License activated");
     toast.error("Request failed", "Check your connection and retry.");
   Wrap your app once with <ToastProvider>.
   ========================================================================== */

export type ToastTone = "success" | "info" | "warn" | "error";

interface ToastItem {
  id: number;
  tone: ToastTone;
  title: string;
  description?: string;
}

interface ToastApi {
  success: (title: string, description?: string) => void;
  info: (title: string, description?: string) => void;
  warn: (title: string, description?: string) => void;
  error: (title: string, description?: string) => void;
}

const ToastContext = createContext<ToastApi | null>(null);

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within <ToastProvider>");
  return ctx;
}

const toneStyles: Record<ToastTone, { icon: IconName; bar: string; iconColor: string }> = {
  success: { icon: "check-circle", bar: "bg-ok", iconColor: "text-ok" },
  info: { icon: "info", bar: "bg-tech-400", iconColor: "text-tech-400" },
  warn: { icon: "alert-triangle", bar: "bg-warn", iconColor: "text-warn" },
  error: { icon: "x-circle", bar: "bg-danger", iconColor: "text-danger" },
};

let nextId = 1;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const push = useCallback(
    (tone: ToastTone, title: string, description?: string) => {
      const id = nextId++;
      setToasts((prev) => [...prev.slice(-4), { id, tone, title, description }]);
      window.setTimeout(() => dismiss(id), 5000);
    },
    [dismiss]
  );

  const api = useMemo<ToastApi>(
    () => ({
      success: (t, d) => push("success", t, d),
      info: (t, d) => push("info", t, d),
      warn: (t, d) => push("warn", t, d),
      error: (t, d) => push("error", t, d),
    }),
    [push]
  );

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="fixed top-4 right-4 z-[120] flex flex-col gap-2 w-[340px] max-w-[calc(100vw-2rem)]">
        {toasts.map((t) => {
          const s = toneStyles[t.tone];
          return (
            <div
              key={t.id}
              role="status"
              className="relative flex items-start gap-3 rounded-xl border border-line-strong bg-overlay px-4 py-3 shadow-lift overflow-hidden animate-in"
              style={{ animation: "dsToastIn 0.18s ease-out" }}
            >
              <style>{`@keyframes dsToastIn { from { opacity: 0; transform: translateX(12px); } to { opacity: 1; transform: none; } }`}</style>
              <span className={`absolute left-0 top-0 bottom-0 w-[3px] ${s.bar}`} />
              <Icon name={s.icon} className={`h-4.5 w-4.5 mt-0.5 shrink-0 ${s.iconColor}`} />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-ink leading-5">{t.title}</p>
                {t.description && <p className="text-xs text-ink-muted mt-0.5 leading-5">{t.description}</p>}
              </div>
              <button
                onClick={() => dismiss(t.id)}
                aria-label="Dismiss"
                className="h-6 w-6 rounded-md flex items-center justify-center text-ink-muted hover:text-ink hover:bg-hover transition-colors shrink-0"
              >
                <Icon name="close" className="h-3.5 w-3.5" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}
