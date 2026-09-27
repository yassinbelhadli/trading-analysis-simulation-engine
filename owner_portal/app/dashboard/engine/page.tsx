"use client";

import { useEffect, useState, useCallback } from "react";
import EngineConsole from "@/components/EngineConsole";
import OwnerPermissionGuard from "@/components/auth/owner_permission_guard";
import { getEngineMonitor, getEngineLogs, controlTrading, closeSymbolTrades } from "@/lib/api";
import { useAutoRefresh } from "@/hooks/useAutoRefresh";
import { PageHeader, Card, StatCard, Button, TextField, Skeleton, EmptyState } from "@ds/components/ui";
import { Modal, ConfirmDialog } from "@ds/components/Modal";

const ACTIONS = [
  { key: "enable", label: "Enable", desc: "Resume normal trading operation.", danger: false },
  { key: "disable", label: "Disable", desc: "Block new trades from opening.", danger: false },
  { key: "pause", label: "Pause", desc: "Pause execution temporarily.", danger: false },
  { key: "resume", label: "Resume", desc: "Resume execution.", danger: false },
  { key: "close-all", label: "Close All", desc: "Close every open position on all accounts.", danger: true },
  { key: "close-symbol", label: "Close Symbol", desc: "Close all positions for one symbol.", danger: true },
  { key: "emergency-stop", label: "Emergency Stop", desc: "Immediately halt the trading engine.", danger: true },
];

export default function EngineControlPage() {
  const [data, setData] = useState<any>(null);
  const [logs, setLogs] = useState<any[]>([]);
  const [error, setError] = useState("");
  const [actionMsg, setActionMsg] = useState("");
  const [confirmAction, setConfirmAction] = useState<string | null>(null);
  const [symbol, setSymbol] = useState("");
  const [busy, setBusy] = useState(false);

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

  const run = async (action: string) => {
    setBusy(true); setActionMsg(""); setError("");
    try {
      const res = await controlTrading(action);
      setActionMsg(res.message || `Action "${action}" completed`);
      setTimeout(() => setActionMsg(""), 5000);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
      setConfirmAction(null);
    }
  };

  const handleConfirm = () => {
    if (confirmAction) run(confirmAction);
  };

  const handleCloseSymbol = async () => {
    if (!symbol) return;
    setBusy(true); setActionMsg(""); setError("");
    closeSymbolTrades(symbol)
      .then((res) => {
        setActionMsg(res.message || `Closed all ${symbol} trades`);
        setTimeout(() => setActionMsg(""), 5000);
      })
      .catch((e) => setError((e as Error).message))
      .finally(() => { setBusy(false); setConfirmAction(null); setSymbol(""); });
  };

  const selectedAction = ACTIONS.find((a) => a.key === confirmAction);

  return (
    <OwnerPermissionGuard permission="engine.read">
      <div className="flex flex-col gap-5 max-w-6xl">
        <PageHeader
          title="Engine Control"
          subtitle="Direct trading-engine control. Destructive actions require explicit confirmation and are audited."
          actions={
            <div className="flex items-center gap-2">
              <label className="flex items-center gap-1.5 text-xs text-ink-soft cursor-pointer">
                <input
                  type="checkbox"
                  checked={autoRefresh}
                  onChange={() => setAutoRefresh(!autoRefresh)}
                  className="accent-brand-500"
                />
                Live
              </label>
              <Button size="sm" variant="secondary" icon="refresh" onClick={load}>
                Refresh
              </Button>
            </div>
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

        {!data && !error ? (
          <div className="space-y-4">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              {[0, 1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-24 rounded-xl" />
              ))}
            </div>
            <Skeleton className="h-40 rounded-xl" />
            <Skeleton className="h-64 rounded-xl" />
          </div>
        ) : data ? (
          <>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <StatCard label="System Version" value={data.system_version || "—"} icon="layers" mono />
              <StatCard
                label="Uptime"
                value={data.uptime_seconds ? `${Math.floor(data.uptime_seconds / 3600)}h ${Math.floor((data.uptime_seconds % 3600) / 60)}m` : "—"}
                icon="clock"
                tone="blue"
              />
              <StatCard label="PID" value={data.pid ?? "—"} icon="cpu" mono />
              <StatCard
                label="Active Trades"
                value={data.active_trades ?? 0}
                tone={data.active_trades > 0 ? "green" : "default"}
                icon="activity"
                mono
              />
            </div>

            <Card
              title="Trading Control"
              icon="zap"
              subtitle="Dangerous actions require explicit confirmation. Every action is audited server-side."
            >
              <div className="flex flex-wrap gap-2">
                {ACTIONS.map((a) => (
                  <Button
                    key={a.key}
                    variant={a.danger ? "danger" : "secondary"}
                    icon={a.key === "close-symbol" ? "filter" : a.key === "close-all" ? "x-circle" : a.key === "emergency-stop" ? "stop" : a.key === "pause" ? "pause" : a.key === "resume" ? "play" : a.key === "enable" ? "power" : "power"}
                    title={a.desc}
                    disabled={busy}
                    onClick={() => {
                      // Non-destructive actions run immediately; destructive
                      // ones (close-all, close-symbol, emergency-stop) require
                      // explicit confirmation first.
                      if (a.danger) {
                        setConfirmAction(a.key);
                      } else {
                        run(a.key);
                      }
                    }}
                  >
                    {a.label}
                  </Button>
                ))}
              </div>
            </Card>

            <Card title="Engine Console" icon="activity" bodyClassName="p-0">
              <EngineConsole logs={logs} />
            </Card>
          </>
        ) : null}
      </div>

      <ConfirmDialog
        open={confirmAction === "close-all" || confirmAction === "emergency-stop"}
        title={selectedAction?.label || "Confirm"}
        description={
          confirmAction === "close-all"
            ? "Close every open position on all accounts? This is a destructive action and is audited."
            : confirmAction === "emergency-stop"
              ? "Immediately halt the trading engine? Normal trading will be suspended until re-enabled."
              : undefined
        }
        confirmLabel="Confirm"
        cancelLabel="Cancel"
        tone="danger"
        loading={busy}
        onConfirm={handleConfirm}
        onCancel={() => setConfirmAction(null)}
      />

      <Modal
        open={confirmAction === "close-symbol"}
        onClose={() => { setConfirmAction(null); setSymbol(""); }}
        title="Close Symbol Trades"
        icon="danger"
      >
        <div className="flex flex-col gap-3">
          <p className="text-sm text-ink-soft">
            Close all open positions for a single symbol across accounts. This is a destructive action and is audited.
          </p>
          <TextField
            label="Symbol"
            placeholder="e.g. XAUUSD"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value.toUpperCase())}
            autoFocus
          />
          <div className="flex justify-end gap-2 mt-2">
            <Button variant="ghost" onClick={() => { setConfirmAction(null); setSymbol(""); }}>
              Cancel
            </Button>
            <Button variant="danger" icon="trash" disabled={!symbol || busy} loading={busy} onClick={handleCloseSymbol}>
              Close {symbol || "Symbol"} trades
            </Button>
          </div>
        </div>
      </Modal>
    </OwnerPermissionGuard>
  );
}
