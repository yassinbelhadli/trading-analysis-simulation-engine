"use client";

import { useEffect, useState, useCallback } from "react";
import StatusBadge from "@/components/StatusBadge";
import StatCard from "@/components/StatCard";
import PermissionGuard from "@/components/auth/permission_guard";
import { getSystemHealth, getSystemEngines, getHeartbeat, getHealthReport, controlEngine } from "@/lib/api";
import { Button, PageHeader } from "@ds/components/ui";
import { ConfirmDialog } from "@ds/components/Modal";

export default function SystemPage() {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [health, setHealth] = useState<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [engines, setEngines] = useState<any[]>([]);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [heartbeat, setHeartbeat] = useState<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [report, setReport] = useState<any>(null);
  const [error, setError] = useState("");
  const [actionMsg, setActionMsg] = useState("");
  const [confirming, setConfirming] = useState<string | null>(null);
  const [confirmBusy, setConfirmBusy] = useState(false);
  const [restarting, setRestarting] = useState(false);
  const [dismissible, setDismissible] = useState(false);

  const load = useCallback(async () => {
    try {
      const [h, e, hb, r]: any = await Promise.all([
        getSystemHealth(), getSystemEngines(), getHeartbeat(), getHealthReport(),
      ]);
      setHealth(h); setEngines(e); setHeartbeat(hb); setReport(r);
    } catch (err) {
      setError((err as Error).message);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleControl = async (action: string) => {
    setConfirming(null);
    setActionMsg("");
    setError("");
    setConfirmBusy(true);
    if (action === "restart_engine") {
      setRestarting(true);
      setDismissible(false);
    }
    try {
      let res;
      if (action === "restart_engine") res = await controlEngine("restart");
      else if (action === "stop_engine") res = await controlEngine("stop");
      else if (action === "start_engine") res = await controlEngine("start");
      setActionMsg(res.message || "Action completed");
      setTimeout(() => setActionMsg(""), 5000);
      if (action === "restart_engine") {
        setTimeout(() => setDismissible(true), 5000);
      }
    } catch (e) {
      setError((e as Error).message);
      setRestarting(false);
      setDismissible(false);
    } finally {
      setConfirmBusy(false);
    }
  };

  const controlInfo: Record<string, { title: string; description: string; label: string; tone: "danger" | "success" }> = {
    restart_engine: { title: "Restart Engine", description: "Restart the trading engine? Trading will pause briefly and resume automatically.", label: "Restart", tone: "danger" },
    stop_engine: { title: "Stop Engine", description: "Stop the trading engine? All active trading operations will be halted.", label: "Stop", tone: "danger" },
    start_engine: { title: "Start Engine", description: "Start the trading engine? Live trading operations will resume.", label: "Start", tone: "success" },
  };

  return (
    <PermissionGuard permission="system.health.read">
      <div>
        <PageHeader
          title="System Health"
          subtitle="Engine, heartbeat and component health"
          actions={<Button onClick={load}>Refresh</Button>}
        />

        {error && <div className="text-danger text-sm mb-3">{error}</div>}
        {actionMsg && <div className="text-ok text-sm mb-3">{actionMsg}</div>}

        {health && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            <StatCard label="System Version" value={health.system_version || "—"} color="default" />
            <StatCard label="Components" value={`${health.components?.healthy || 0}/${health.components?.total || 0}`}
              sub={`${health.components?.warning || 0} warning · ${health.components?.error || 0} error`}
              color={health.components?.error > 0 ? "error" : health.components?.warning > 0 ? "warning" : "success"} />
            <StatCard label="Uptime" value={health.uptime_seconds ? `${Math.floor(health.uptime_seconds / 3600)}h ${Math.floor((health.uptime_seconds % 3600) / 60)}m` : "—"} color="default" />
            <StatCard label="Engines" value={health.engines?.running ?? 0} sub={`${health.engines?.total ?? 0} total`}
              color={health.engines?.running > 0 ? "success" : "default"} />
          </div>
        )}

        {/* System Controls */}
        <div className="bg-raised border border-line rounded-lg p-4 mb-6">
          <h2 className="text-sm font-semibold text-ink mb-3">System Controls</h2>
          <div className="flex flex-wrap gap-2">
            {[
              { key: "restart_engine", label: "Restart Engine", variant: "danger" as const },
              { key: "stop_engine", label: "Stop Engine", variant: "danger" as const },
              { key: "start_engine", label: "Start Engine", variant: "success" as const },
            ].map((btn) => (
              <Button key={btn.key} variant={btn.variant} size="sm" disabled={restarting}
                onClick={() => setConfirming(btn.key)}>
                {btn.label}
              </Button>
            ))}
          </div>
        </div>

        {heartbeat && (
          <div className="bg-raised border border-line rounded-lg p-4 mb-6">
            <h2 className="text-sm font-semibold text-ink mb-2">Latest Heartbeat</h2>
            <pre className="text-xs text-ink-muted font-mono whitespace-pre-wrap">{JSON.stringify(heartbeat, null, 2)}</pre>
          </div>
        )}

        {engines.length > 0 && (
          <div className="mb-6">
            <h2 className="text-sm font-semibold text-ink mb-3">Running Engines</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {engines.map((e, i) => (
                <div key={e.account_id || i} className="bg-raised border border-line rounded-lg p-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-mono text-sm text-ink">{e.account_id || "Engine " + (i + 1)}</span>
                    <StatusBadge status={e.state || "unknown"} />
                  </div>
                  <div className="text-xs text-ink-muted space-y-1">
                    {e.uptime_seconds != null && <div>Uptime: {Math.floor(e.uptime_seconds / 60)}m</div>}
                    {e.last_heartbeat && <div>Last beat: {new Date(e.last_heartbeat).toLocaleString()}</div>}
                    {e.pid && <div>PID: {e.pid}</div>}
                    {e.error && <div className="text-danger">{e.error}</div>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {report && (
          <div className="bg-raised border border-line rounded-lg p-4">
            <h2 className="text-sm font-semibold text-ink mb-2">Full Health Report</h2>
            <pre className="text-xs text-ink-muted font-mono whitespace-pre-wrap max-h-96 overflow-y-auto">{JSON.stringify(report, null, 2)}</pre>
          </div>
        )}
      </div>

      {restarting && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="bg-raised border border-line rounded-lg p-8 max-w-sm w-full mx-4 text-center">
            <div className="animate-spin h-8 w-8 border-2 border-brand-500 border-t-transparent rounded-full mx-auto mb-4"></div>
            <h3 className="text-lg font-semibold text-ink mb-2">Engine is restarting...</h3>
            <p className="text-sm text-ink-muted mb-4">This may take up to a minute. All operations will resume automatically.</p>
            {dismissible && (
              <button onClick={() => { setRestarting(false); setDismissible(false); }}
                className="px-4 py-2 text-sm rounded-lg border border-line hover:bg-hover text-ink-muted">Dismiss</button>
            )}
          </div>
        </div>
      )}

      <ConfirmDialog
        open={!!confirming}
        title={confirming ? controlInfo[confirming]?.title || "Confirm action" : ""}
        description={confirming ? controlInfo[confirming]?.description || "Perform this action?" : ""}
        confirmLabel={confirming ? controlInfo[confirming]?.label || "Confirm" : "Confirm"}
        tone={confirming ? controlInfo[confirming]?.tone || "danger" : "danger"}
        loading={confirmBusy}
        onConfirm={() => confirming && handleControl(confirming)}
        onCancel={() => setConfirming(null)}
      />
    </PermissionGuard>
  );
}
