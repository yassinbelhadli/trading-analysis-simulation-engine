"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@ds/components/ui";
import { Icon } from "@ds/components/Icon";

interface LogEntry {
  timestamp: string;
  level: string;
  message: string;
}

interface Props {
  logs: LogEntry[];
  loading?: boolean;
}

const LEVEL_STYLES: Record<string, string> = {
  INFO: "text-tech-400",
  WARNING: "text-warn",
  ERROR: "text-danger",
  CRITICAL: "text-danger font-bold",
  DEBUG: "text-ink-muted",
};

export default function EngineConsole({ logs, loading }: Props) {
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("");
  const [autoScroll, setAutoScroll] = useState(true);
  const containerRef = useRef<HTMLDivElement>(null);

  const filtered = logs.filter((l) => {
    if (filter && l.level !== filter) return false;
    if (search && !l.message.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  useEffect(() => {
    if (autoScroll && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [filtered.length, autoScroll]);

  return (
    <div className="bg-raised border border-line rounded-xl overflow-hidden">
      {/* Toolbar */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-line">
        <div className="relative flex-1">
          <Icon name="search" className="h-4 w-4 text-ink-muted absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
          <input
            placeholder="Search logs..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="h-8 w-full pl-8 pr-2 rounded-lg bg-input border border-line text-xs text-ink placeholder:text-ink-muted focus:outline-none focus:border-brand-500"
          />
        </div>
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="h-8 px-2 rounded-lg bg-input border border-line text-xs text-ink focus:outline-none focus:border-brand-500"
        >
          <option value="">All</option>
          <option value="INFO">INFO</option>
          <option value="WARNING">WARNING</option>
          <option value="ERROR">ERROR</option>
          <option value="DEBUG">DEBUG</option>
        </select>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => setAutoScroll(!autoScroll)}
          icon={autoScroll ? "pause" : "play"}
        >
          Auto
        </Button>
      </div>

      {/* Logs */}
      <div ref={containerRef} className="h-64 overflow-y-auto font-mono text-[11px] p-2 space-y-0.5">
        {loading && <div className="text-ink-muted">Loading logs...</div>}
        {!loading && filtered.length === 0 && (
          <div className="text-ink-muted">{search || filter ? "No matching logs" : "No logs available"}</div>
        )}
        {filtered.map((log, i) => (
          <div key={i} className="flex gap-2">
            <span className="text-ink-muted shrink-0 w-16">
              {log.timestamp ? new Date(log.timestamp).toLocaleTimeString() : ""}
            </span>
            <span className={`shrink-0 w-16 ${LEVEL_STYLES[log.level] || "text-ink-muted"}`}>{log.level}</span>
            <span className="text-ink break-all">{log.message}</span>
          </div>
        ))}
      </div>

      {/* Footer */}
      <div className="px-3 py-1.5 border-t border-line text-[10px] text-ink-muted flex justify-between">
        <span>{filtered.length} entries{filter || search ? " (filtered)" : ""}</span>
        <span>{logs.length} total</span>
      </div>
    </div>
  );
}
