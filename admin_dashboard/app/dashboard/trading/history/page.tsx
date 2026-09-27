"use client";

import { useEffect, useState, useCallback } from "react";
import StatusBadge from "@/components/StatusBadge";
import TradeDrawer from "@/components/TradeDrawer";
import PermissionGuard from "@/components/auth/permission_guard";
import { getTradeHistory } from "@/lib/api";
import { Button, Card, PageHeader, SelectField, Table, Td, TextField, Skeleton } from "@ds/components/ui";

export default function TradeHistoryPage() {
  const [trades, setTrades] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState("");
  const [symbol, setSymbol] = useState("");
  const [direction, setDirection] = useState("");
  const [offset, setOffset] = useState(0);
  const [selectedTrade, setSelectedTrade] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const LIMIT = 30;

  const load = useCallback(async (sym: string, dir: string, off: number) => {
    setLoading(true);
    const params = new URLSearchParams({ limit: String(LIMIT), offset: String(off) });
    if (sym) params.set("symbol", sym);
    if (dir) params.set("direction", dir);
    try {
      const res = await getTradeHistory(`?${params.toString()}`);
      setTrades(res.items);
      setTotal(res.total);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(symbol, direction, offset); }, [load, symbol, direction, offset]);

  const exportCSV = () => {
    const headers = ["Symbol", "Direction", "Entry", "Exit", "Lot", "RR", "R Realized", "Close Reason", "Duration", "Score", "Opened", "Closed"];
    const rows = trades.map((t) => [
      t.symbol, t.direction, t.entry_price, t.exit_price, t.lot_size,
      t.risk_reward, t.realized_r, t.close_reason, t.trade_duration_sec, t.score, t.created_at, t.closed_at,
    ].map((v) => `"${v ?? ""}"`).join(","));
    const csv = [headers.join(","), ...rows].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url; a.download = `trade_history_${new Date().toISOString().slice(0, 10)}.csv`; a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <PermissionGuard permission="trades.read">
      <div>
        <PageHeader
          title="Trade History"
          subtitle="Closed trades and performance"
          actions={<Button variant="ghost" onClick={exportCSV}>CSV</Button>}
        />

        {error && <div className="text-danger text-sm mb-3">{error}</div>}

        <div className="flex gap-3 mb-4">
          <TextField
            placeholder="Symbol (XAUUSD, NAS100...)"
            value={symbol}
            onChange={(e) => { setSymbol(e.target.value.toUpperCase()); setOffset(0); }}
            className="min-w-[200px]"
          />
          <SelectField value={direction} onChange={(e) => { setDirection(e.target.value); setOffset(0); }}>
            <option value="">All directions</option>
            <option value="BUY">BUY</option>
            <option value="SELL">SELL</option>
          </SelectField>
        </div>

        <Card bodyClassName="p-0">
          <Table columns={["Symbol", "Dir", "Entry", "Exit", "Lot", "P&L (R)", "RR", "Reason", "Score", "Closed"]}>
            {loading ? (
              <tr>
                <td colSpan={10} className="px-4 py-4">
                  <div className="flex flex-col gap-2">
                    <Skeleton className="h-9 w-full" />
                    <Skeleton className="h-9 w-full" />
                    <Skeleton className="h-9 w-full" />
                  </div>
                </td>
              </tr>
            ) : trades.length === 0 ? (
              <tr>
                <td colSpan={10} className="text-center py-8 text-ink-muted px-4">No closed trades</td>
              </tr>
            ) : (
            trades.map((t) => (
              <tr key={t.id} className="cursor-pointer" onClick={() => setSelectedTrade(t)}>
                <Td mono>{t.symbol || "—"}</Td>
                <Td>
                  <span className={`text-xs font-semibold ${t.direction === "BUY" ? "text-ok" : "text-danger"}`}>{t.direction || "—"}</span>
                </Td>
                <Td mono className="text-xs">{t.entry_price || "—"}</Td>
                <Td mono className="text-xs">{t.exit_price || "—"}</Td>
                <Td>{t.lot_size || "—"}</Td>
                <Td>
                  <span className={`font-mono text-xs ${(t.realized_r || 0) > 0 ? "text-ok" : (t.realized_r || 0) < 0 ? "text-danger" : ""}`}>
                    {t.realized_r != null ? t.realized_r.toFixed(2) : "—"}
                  </span>
                </Td>
                <Td>{t.risk_reward || "—"}</Td>
                <Td className="text-xs">{t.close_reason || "—"}</Td>
                <Td>{t.score || "—"}</Td>
                <Td className="text-ink-muted text-xs">{t.closed_at ? new Date(t.closed_at).toLocaleDateString() : "—"}</Td>
              </tr>
            ))
            )}
          </Table>
        </Card>

        {total > LIMIT && (
          <div className="flex items-center justify-between mt-4 text-sm text-ink-muted">
            <span>{total} total</span>
            <div className="flex gap-2">
              <Button variant="secondary" size="sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - LIMIT))}>Previous</Button>
              <Button variant="secondary" size="sm" disabled={offset + LIMIT >= total} onClick={() => setOffset(offset + LIMIT)}>Next</Button>
            </div>
          </div>
        )}

        <TradeDrawer trade={selectedTrade} onClose={() => setSelectedTrade(null)} />
      </div>
    </PermissionGuard>
  );
}
