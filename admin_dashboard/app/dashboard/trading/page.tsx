"use client";

import { useEffect, useState, useCallback } from "react";
import StatCard from "@/components/StatCard";
import PermissionGuard from "@/components/auth/permission_guard";
import { getTradingOverview, controlTrading } from "@/lib/api";
import { useAutoRefresh } from "@/hooks/useAutoRefresh";
import { Button, PageHeader } from "@ds/components/ui";
import { ConfirmDialog } from "@ds/components/Modal";

const CONTROL_ACTIONS = [
  { key: "enable", label: "Enable EA", variant: "success" as const, description: "Enable the EA on all connected accounts? Live trading will resume." },
  { key: "disable", label: "Disable EA", variant: "danger" as const, description: "Disable the EA on all connected accounts? No new trades will be opened." },
  { key: "pause", label: "Pause Trading", variant: "secondary" as const, description: "Pause trading? Existing positions will remain open but no new trades will be taken." },
  { key: "resume", label: "Resume Trading", variant: "success" as const, description: "Resume trading? The EA will continue from where it left off." },
  { key: "close-all", label: "Close All", variant: "danger" as const, description: "Close all open positions immediately? This cannot be undone." },
  { key: "emergency-stop", label: "Emergency Stop", variant: "danger" as const, description: "Emergency stop halts trading and closes all positions immediately. Confirm?" },
];

export default function TradingOverviewPage() {
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");
  const [actionMsg, setActionMsg] = useState("");
  const [confirming, setConfirming] = useState<string | null>(null);
  const [confirmBusy, setConfirmBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await getTradingOverview();
      setData(res);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => { load(); }, [load]);
  const { autoRefresh, setAutoRefresh } = useAutoRefresh(load, 5000);

  const handleControl = async (action: string) => {
    setConfirming(null);
    setActionMsg("");
    setConfirmBusy(true);
    try {
      const res = await controlTrading(action);
      setActionMsg(res.message);
      setTimeout(() => setActionMsg(""), 5000);
      load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setConfirmBusy(false);
    }
  };

  const pending = CONTROL_ACTIONS.find((a) => a.key === confirming);

  return (
    <PermissionGuard permission="trades.read">
      <div>
        <PageHeader
          title="Trading Overview"
          subtitle="Live performance, positions and trading controls"
          actions={
            <label className="flex items-center gap-1.5 text-xs text-ink-muted cursor-pointer">
              <input type="checkbox" checked={autoRefresh} onChange={() => setAutoRefresh(!autoRefresh)} className="accent-brand-500" />
              Live
            </label>
          }
        />

        {error && <div className="text-danger text-sm mb-3">{error}</div>}
        {actionMsg && <div className="text-ok text-sm mb-3">{actionMsg}</div>}

        {data && (
          <>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
              <StatCard label="Active Trades" value={data.active_trades ?? 0} color={data.active_trades > 0 ? "success" : "default"} />
              <StatCard label="Pending Orders" value={data.pending_orders ?? 0} color={data.pending_orders > 0 ? "warning" : "default"} />
              <StatCard label="Floating P&L" value={data.floating_pnl ?? 0} color={data.floating_pnl > 0 ? "success" : data.floating_pnl < 0 ? "error" : "default"} />
              <StatCard label="Daily P&L" value={data.daily_pnl ?? 0} color={data.daily_pnl > 0 ? "success" : data.daily_pnl < 0 ? "error" : "default"} />
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
              <StatCard label="Net P&L" value={data.net_pnl ?? 0} color={data.net_pnl > 0 ? "success" : data.net_pnl < 0 ? "error" : "default"} />
              <StatCard label="Win Rate" value={data.win_rate != null ? `${data.win_rate}%` : "—"} color={data.win_rate >= 60 ? "success" : data.win_rate >= 40 ? "warning" : "default"} />
              <StatCard label="Profit Factor" value={data.profit_factor ?? "—"} color={data.profit_factor >= 2 ? "success" : data.profit_factor >= 1 ? "warning" : "default"} />
              <StatCard label="Max Drawdown" value={data.max_drawdown != null ? data.max_drawdown : "—"} color={data.max_drawdown > 0 ? "error" : "default"} />
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
              <StatCard label="Total Trades" value={data.total_trades ?? 0} sub={`${data.win_count ?? 0}W / ${data.loss_count ?? 0}L`} color="default" />
              <StatCard label="Daily Loss" value={data.daily_loss ?? 0} color={data.daily_loss < 0 ? "error" : "default"} />
              <StatCard label="Connected Accounts" value={data.connected_accounts ?? 0} color={data.connected_accounts > 0 ? "success" : "default"} />
              <StatCard label="Current Drawdown" value={data.current_drawdown != null ? data.current_drawdown : "—"} color={data.current_drawdown > 0 ? "warning" : "default"} />
            </div>

            {/* Trading Controls */}
            <div className="bg-raised border border-line rounded-lg p-4 mb-6">
              <h2 className="text-sm font-semibold mb-3 text-ink">Trading Controls</h2>
              <div className="flex flex-wrap gap-2">
                {CONTROL_ACTIONS.map((btn) => (
                  <Button key={btn.key} variant={btn.variant} size="sm" onClick={() => setConfirming(btn.key)}>
                    {btn.label}
                  </Button>
                ))}
              </div>
            </div>

            {/* System Status */}
            <div className="bg-raised border border-line rounded-lg p-4">
              <h2 className="text-sm font-semibold mb-3 text-ink">System Status</h2>
              <div className="grid grid-cols-3 gap-4 text-xs">
                {[
                  { label: "Engine", value: data.engine_status, ok: data.engine_status === "RUNNING" },
                  { label: "MT5", value: data.mt5_connected ? "Connected" : "Disconnected", ok: data.mt5_connected },
                  { label: "Telegram", value: data.telegram_connected ? "Connected" : "Disconnected", ok: data.telegram_connected },
                ].map((s) => (
                  <div key={s.label} className="flex items-center gap-2 text-ink-soft">
                    <span className={`w-2 h-2 rounded-full ${s.ok ? "bg-ok" : "bg-danger"}`} />
                    <span>{s.label}: <span className="font-medium text-ink">{s.value}</span></span>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}

        {!data && !error && <div className="text-ink-muted text-sm py-8 text-center">Loading trading data...</div>}

        <ConfirmDialog
          open={!!confirming}
          title={pending?.label || "Confirm action"}
          description={pending?.description || "Perform this action?"}
          confirmLabel={pending?.label || "Confirm"}
          tone={pending?.variant === "success" ? "success" : "danger"}
          loading={confirmBusy}
          onConfirm={() => confirming && handleControl(confirming)}
          onCancel={() => setConfirming(null)}
        />
      </div>
    </PermissionGuard>
  );
}
