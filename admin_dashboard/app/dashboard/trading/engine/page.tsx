"use client";

import { useEffect, useState, useCallback } from "react";
import StatCard from "@/components/StatCard";
import EngineConsole from "@/components/EngineConsole";
import PermissionGuard from "@/components/auth/permission_guard";
import { getEngineMonitor, getEngineLogs } from "@/lib/api";
import { useAutoRefresh } from "@/hooks/useAutoRefresh";
import { Button, PageHeader } from "@ds/components/ui";

export default function EngineMonitorPage() {
  const [data, setData] = useState<any>(null);
  const [logs, setLogs] = useState<any[]>([]);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const [res, logRes] = await Promise.all([getEngineMonitor(), getEngineLogs(200)]);
      setData(res);
      setLogs(logRes.items || []);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => { load(); }, [load]);
  const { autoRefresh, setAutoRefresh } = useAutoRefresh(load, 5000);

  return (
    <PermissionGuard permission="engine.read">
      <div>
        <PageHeader
          title="Engine Monitor"
          subtitle="Live engine process, components and logs"
          actions={
            <>
              <label className="flex items-center gap-1.5 text-xs text-ink-muted cursor-pointer">
                <input type="checkbox" checked={autoRefresh} onChange={() => setAutoRefresh(!autoRefresh)} className="accent-brand-500" />
                Live
              </label>
              <Button variant="secondary" size="sm" onClick={load}>Refresh</Button>
            </>
          }
        />

        {error && <div className="text-danger text-sm mb-3">{error}</div>}

        {data && (
          <>
            {/* Engine Stats */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
              <StatCard label="System Version" value={data.system_version || "—"} color="default" />
              <StatCard label="Uptime" value={data.uptime_seconds ? `${Math.floor(data.uptime_seconds / 3600)}h ${Math.floor((data.uptime_seconds % 3600) / 60)}m` : "—"} color="default" />
              <StatCard label="PID" value={data.pid ?? "—"} color="default" />
              <StatCard label="Instance" value={data.instance_id ? data.instance_id.slice(0, 8) + "..." : "—"} color="default" />
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
              <StatCard label="Cycles" value={data.cycles ?? "—"} color="default" />
              <StatCard label="Memory" value={data.memory_mb != null ? `${data.memory_mb} MB` : "—"} color={data.memory_mb > 500 ? "warning" : "default"} />
              <StatCard label="CPU" value={data.cpu_percent != null ? `${data.cpu_percent}%` : "—"} color={data.cpu_percent > 80 ? "error" : data.cpu_percent > 50 ? "warning" : "default"} />
              <StatCard label="Active Trades" value={data.active_trades ?? 0} color={data.active_trades > 0 ? "success" : "default"} />
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
              <StatCard label="MT5" value={data.mt5_connected ? "Connected" : "Disconnected"} color={data.mt5_connected ? "success" : "error"} />
              <StatCard label="Telegram" value={data.telegram_connected ? "Connected" : "Disconnected"} color={data.telegram_connected ? "success" : "error"} />
              <StatCard label="Heartbeat" value={data.heartbeat_age_sec != null ? `${data.heartbeat_age_sec}s` : "—"}
                color={data.heartbeat_age_sec != null && data.heartbeat_age_sec < 60 ? "success" : data.heartbeat_age_sec != null && data.heartbeat_age_sec < 300 ? "warning" : data.heartbeat_age_sec != null ? "error" : "default"} />
              <StatCard label="Engine Counts" value="" sub={`Running: ${data.engine_counts?.running || 0} · Stopped: ${data.engine_counts?.stopped || 0}`} color="default" />
            </div>

            {/* Components */}
            {data.components && (
              <div className="bg-raised border border-line rounded-lg p-4 mb-6">
                <h2 className="text-sm font-semibold mb-3 text-ink">Components</h2>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                  {Object.entries(data.components).map(([key, val]) => {
                    const v = val as any;
                    const ok = v === true || v === "healthy" || v === "Running" || v === "connected";
                    return (
                      <div key={key} className="flex items-center gap-2 text-xs bg-input rounded p-2 text-ink-soft">
                        <span className={`w-1.5 h-1.5 rounded-full ${ok ? "bg-ok" : "bg-danger"}`} />
                        <span className="capitalize">{key.replace(/_/g, " ")}</span>
                        <span className="ml-auto font-mono text-ink">{String(v)}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Engine Console */}
            <h2 className="text-sm font-semibold text-ink mb-3">Engine Console</h2>
            <EngineConsole logs={logs} />
          </>
        )}

        {!data && !error && <div className="text-ink-muted text-sm py-8 text-center">Loading engine data...</div>}
      </div>
    </PermissionGuard>
  );
}
