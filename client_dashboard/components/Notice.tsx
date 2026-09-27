"use client";

import { Icon } from "@ds/components/Icon";

export type NoticeState = { ok: boolean; text: string } | null;

export function Notice({ state }: { state: NoticeState }) {
  if (!state) return null;
  return (
    <div
      className={`flex items-center gap-2 text-sm px-3 py-2 rounded-lg border ${
        state.ok
          ? "text-ok border-ok/30 bg-ok/10"
          : "text-danger border-danger/30 bg-danger/10"
      }`}
    >
      <Icon name={state.ok ? "check-circle" : "alert-triangle"} className="h-4 w-4 shrink-0" />
      {state.text}
    </div>
  );
}
