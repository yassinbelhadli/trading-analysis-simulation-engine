"use client";

import { useEffect, useState, useCallback } from "react";
import OwnerPermissionGuard from "@/components/auth/owner_permission_guard";
import { getSystemHealth, getSystemEngines, getHeartbeat, getHealthReport, controlEngine } from "@/lib/api";
import { PageHeader, Card, StatCard, Badge, Button, Skeleton, type BadgeTone } from "@ds/components/ui";
import { ConfirmDialog } from "@ds/components/Modal";
import { Icon } from "@ds/components/Icon";

function stateTone(state?: string): BadgeTone {
  const s = (state || "").toLowerCase();
  if (s === "running" || s === "online" || s === "healthy") return "green";
  if (s === "stopped" || s === "offline" || s === "error") return "red";
  if (s === "restarting" || s === "starting") return "blue";
  return "gray";
}

export default function SystemPage() {
  const [health, setHealth] = useState<any>(null);
  const [engines, setEngines] = useState<any[]>([]);
  const [heartbeat, setHeartbeat] = useState<any>(null);
  const [report, setReport] = useState<any>(null);
  const [error, setError] = useState("");
  const [actionMsg, setActionMsg] = useState("");
  const [confirmAction, setConfirmAction] = useState<string | null>(null);
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
    setConfirmAction(null);
    setActionMsg("");
    setError("");
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
    }
  };

  const controlLabel = (key: string) =>
    key === "restart_engine" ? "Restart Engine" : key === "stop_engine" ? "Stop Engine" : "Start Engine";

  return (
    <OwnerPermissionGuard permission="system.health.read">
      <div className="flex flex-col gap-5 max-w-6xl">
        <PageHeader
          title="System Health"
          subtitle="Service, engine and heartbeat status across the platform."
          actions={
            <Button size="sm" variant="secondary" icon="refresh" onClick={load}>
              Refresh
            </Button>
          }
        />

        {error && (
          <div className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
            {error}
          </div>
        )}
        {actionMsg && (
          <div className="rounded-lg border border-ok/30 bg-ok/10 px-3 py-2 text-sm text-ok">
            {actionMsg}
          </div>
        )}

        {!health && !error ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-24 rounded-xl" />
            ))}
          </div>
        ) : health ? (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <StatCard label="System Version" value={health.system_version || "—"} icon="layers" mono />
              <StatCard
                label="Components"
                value={`${health.components?.healthy || 0}/${health.components?.total || 0}`}
                sub={`${health.components?.warning || 0} warning · ${health.components?.error || 0} error`}
                tone={health.components?.error > 0 ? "red" : health.components?.warning > 0 ? "amber" : "green"}
                icon="activity"
                mono
              />
              <StatCard
                label="Uptime"
                value={health.uptime_seconds ? `${Math.floor(health.uptime_seconds / 3600)}h ${Math.floor((health.uptime_seconds % 3600) / 60)}m` : "—"}
                icon="clock"
                tone="blue"
                mono
              />
              <StatCard
                label="Engines"
                value={health.engines?.running ?? 0}
                sub={`${health.engines?.total ?? 0} total`}
                tone={health.engines?.running > 0 ? "green" : "default"}
                icon="cpu"
                mono
              />
            </div>

            <Card title="System Controls" icon="power" subtitle="Restart and stop actions are destructive and are confirmed before execution.">
              <div className="flex flex-wrap gap-2">
                <Button variant="secondary" icon="refresh" disabled={restarting} onClick={() => setConfirmAction("restart_engine")}>
                  Restart Engine
                </Button>
                <Button variant="danger" icon="stop" disabled={restarting} onClick={() => setConfirmAction("stop_engine")}>
                  Stop Engine
                </Button>
                <Button variant="secondary" icon="play" disabled={restarting} onClick={() => handleControl("start_engine")}>
                  Start Engine
                </Button>
              </div>
            </Card>

            {heartbeat && (
              <Card title="Latest Heartbeat" icon="activity" bodyClassName="p-0">
                <pre className="text-xs text-ink-muted font-mono whitespace-pre-wrap p-4">{JSON.stringify(heartbeat, null, 2)}</pre>
              </Card>
            )}

            {engines.length > 0 && (
              <Card title="Running Engines" icon="cpu">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {engines.map((e, i) => (
                    <div key={e.account_id || i} className="rounded-xl border border-line bg-base p-4">
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-mono text-sm text-ink">{e.account_id || `Engine ${i + 1}`}</span>
                        <Badge tone={stateTone(e.state)}>{e.state || "unknown"}</Badge>
                      </div>
                      <div className="text-xs text-ink-muted space-y-1">
                        {e.uptime_seconds != null && <div>Uptime: {Math.floor(e.uptime_seconds / 60)}m</div>}
                        {e.last_heartbeat && <div>Last beat: {new Date(e.last_heartbeat).toLocaleString()}</div>}
                        {e.pid && <div className="font-mono">PID: {e.pid}</div>}
                        {e.error && <div className="text-danger">{e.error}</div>}
                      </div>
                    </div>
                  ))}
                </div>
              </Card>
            )}

            {report && (
              <Card title="Full Health Report" icon="file-text" bodyClassName="p-0">
                <pre className="text-xs text-ink-muted font-mono whitespace-pre-wrap max-h-96 overflow-y-auto p-4">
                  {JSON.stringify(report, null, 2)}
                </pre>
              </Card>
            )}
          </>
        ) : null}
      </div>

      <ConfirmDialog
        open={!!confirmAction}
        title={controlLabel(confirmAction || "")}
        description={
          confirmAction === "restart_engine"
            ? "Restart the trading engine? Trading will pause for up to a minute and resume automatically."
            : "Stop the trading engine? All trading activity will halt until the engine is started again."
        }
        confirmLabel={controlLabel(confirmAction || "")}
        cancelLabel="Cancel"
        tone="danger"
        loading={restarting}
        onConfirm={() => confirmAction && handleControl(confirmAction)}
        onCancel={() => setConfirmAction(null)}
      />

      {restarting && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/70 backdrop-blur-sm">
          <div className="relative bg-overlay border border-line-strong rounded-xl shadow-pop p-8 max-w-sm w-full mx-4 text-center">
            <div className="animate-spin h-8 w-8 border-2 border-brand-500 border-t-transparent rounded-full mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-ink mb-2">Engine is restarting...</h3>
            <p className="text-sm text-ink-muted mb-4">This may take up to a minute. All operations will resume automatically.</p>
            {dismissible && (
              <Button
                variant="secondary"
                onClick={() => { setRestarting(false); setDismissible(false); }}
              >
                Dismiss
              </Button>
            )}
          </div>
        </div>
      )}
    </OwnerPermissionGuard>
  );
}
