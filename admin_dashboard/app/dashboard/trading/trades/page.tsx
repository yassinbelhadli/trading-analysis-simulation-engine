"use client";

import { useEffect, useState, useCallback } from "react";
import StatusBadge from "@/components/StatusBadge";
import TradeDrawer from "@/components/TradeDrawer";
import PermissionGuard from "@/components/auth/permission_guard";
import { getActiveTrades } from "@/lib/api";
import { useAutoRefresh } from "@/hooks/useAutoRefresh";
import { Button, Card, PageHeader, Table, Td, Skeleton } from "@ds/components/ui";

export default function ActiveTradesPage() {
  const [trades, setTrades] = useState<any[]>([]);
  const [error, setError] = useState("");
  const [selectedTrade, setSelectedTrade] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getActiveTrades();
      setTrades(res.items || []);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);
  const { autoRefresh, setAutoRefresh } = useAutoRefresh(load, 3000);

  return (
    <PermissionGuard permission="trades.read">
      <div>
        <PageHeader
          title="Active Trades"
          subtitle="Currently open positions"
          actions={
            <label className="flex items-center gap-1.5 text-xs text-ink-muted cursor-pointer">
              <input type="checkbox" checked={autoRefresh} onChange={() => setAutoRefresh(!autoRefresh)} className="accent-brand-500" />
              Live
            </label>
          }
        />

        {error && <div className="text-danger text-sm mb-3">{error}</div>}

        <Card bodyClassName="p-0">
          <Table columns={["Symbol", "Direction", "Status", "Entry", "SL", "TP", "Lot", "Risk %", "RR", "Score", "Session"]}>
            {loading ? (
              <tr>
                <td colSpan={11} className="px-4 py-4">
                  <div className="flex flex-col gap-2">
                    <Skeleton className="h-9 w-full" />
                    <Skeleton className="h-9 w-full" />
                    <Skeleton className="h-9 w-full" />
                  </div>
                </td>
              </tr>
            ) : trades.length === 0 ? (
              <tr>
                <td colSpan={11} className="text-center py-8 text-ink-muted px-4">No active trades</td>
              </tr>
            ) : (
            trades.map((t) => (
              <tr key={t.id} className="cursor-pointer" onClick={() => setSelectedTrade(t)}>
                <Td mono>{t.symbol || "—"}</Td>
                <Td>
                  <span className={`text-xs font-semibold ${t.direction === "BUY" ? "text-ok" : "text-danger"}`}>{t.direction || "—"}</span>
                </Td>
                <Td><StatusBadge status={t.status} /></Td>
                <Td mono className="text-xs">{t.entry_price || "—"}</Td>
                <Td mono className="text-xs">{t.stop_loss || "—"}</Td>
                <Td mono className="text-xs">{t.take_profit || "—"}</Td>
                <Td>{t.lot_size || "—"}</Td>
                <Td>{t.risk_percent != null ? `${t.risk_percent}%` : "—"}</Td>
                <Td>{t.risk_reward || "—"}</Td>
                <Td>
                  <span className={`text-xs font-semibold ${(t.score || 0) >= 80 ? "text-ok" : (t.score || 0) >= 60 ? "text-warn" : "text-ink-muted"}`}>
                    {t.score || "—"}
                  </span>
                </Td>
                <Td className="text-xs">{t.session || "—"}</Td>
              </tr>
            ))
            )}
          </Table>
        </Card>

        <TradeDrawer trade={selectedTrade} onClose={() => setSelectedTrade(null)} />
      </div>
    </PermissionGuard>
  );
}
