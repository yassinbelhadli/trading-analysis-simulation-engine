"use client";

import { useEffect, useRef, useState } from "react";

export function useAutoRefresh(callback: () => void, intervalMs = 5000) {
  const [enabled, setEnabled] = useState(true);
  const cbRef = useRef(callback);
  const enabledRef = useRef(enabled);
  cbRef.current = callback;
  enabledRef.current = enabled;

  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState === "visible" && enabledRef.current) {
        cbRef.current();
      }
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, []);

  useEffect(() => {
    if (!enabled) return;
    let id = setInterval(() => {
      if (document.visibilityState !== "hidden") cbRef.current();
    }, intervalMs);
    return () => clearInterval(id);
  }, [enabled, intervalMs]);

  return { autoRefresh: enabled, setAutoRefresh: setEnabled };
}
