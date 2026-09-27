"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import StatCard from "@/components/StatCard";
import EquityCurve from "@/components/charts/EquityCurve";
import PermissionGuard from "@/components/auth/permission_guard";
import { getTradingPerformance } from "@/lib/api";
import { Button, Card, PageHeader, Table, Td } from "@ds/components/ui";

export default function PerformancePage() {
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const res = await getTradingPerformance();
      setData(res);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const metrics = data?.total;
  const overview = data?.overview;

  const { equityData, drawdownData, timeline } = useMemo(() => {
    const eq: { time: string; value: number }[] = [];
    const dd: { time: string; value: number }[] = [];
    let runningPnl = 0;
    const tl = data?.timeline?.hourly || data?.timeline;
    if (tl) {
      for (const entry of tl) {
        const date = entry.hour || entry.date || entry.period;
        const pnl = entry.net_pnl || entry.pnl || 0;
        runningPnl += pnl;
        if (date) {
          eq.push({ time: String(date), value: runningPnl });
          dd.push({ time: String(date), value: Math.abs(entry.drawdown || 0) });
        }
      }
    }
    return { equityData: eq, drawdownData: dd, timeline: tl || [] };
  }, [data]);

  return (
    <PermissionGuard permission="trades.read">
      <div>
        <PageHeader
          title="Performance"
          subtitle="Trading metrics, equity curve and timeline"
          actions={<Button onClick={load}>Refresh</Button>}
        />

        {error && <div className="text-danger text-sm mb-3">{error}</div>}

        {metrics && (
          <>
            {/* Summary Cards */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
              <StatCard label="Total Trades" value={metrics.total_trades ?? 0} sub={`${metrics.filled_trades ?? 0} filled`} color="default" />
              <StatCard label="Win Rate" value={metrics.win_rate != null ? `${(metrics.win_rate * 100).toFixed(1)}%` : "—"}
                color={(metrics.win_rate || 0) >= 0.6 ? "success" : (metrics.win_rate || 0) >= 0.4 ? "warning" : "default"} />
              <StatCard label="Profit Factor" value={metrics.profit_factor?.toFixed(2) ?? "—"}
                color={(metrics.profit_factor || 0) >= 2 ? "success" : (metrics.profit_factor || 0) >= 1 ? "warning" : "default"} />
              <StatCard label="Net P&L (R)" value={metrics.net_pnl != null ? metrics.net_pnl.toFixed(2) : "—"}
                color={(metrics.net_pnl || 0) > 0 ? "success" : (metrics.net_pnl || 0) < 0 ? "error" : "default"} />
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
              <StatCard label="TP Rate" value={metrics.tp_rate != null ? `${(metrics.tp_rate * 100).toFixed(1)}%` : "—"} color={metrics.tp_rate >= 0.5 ? "success" : "default"} />
              <StatCard label="Expectancy" value={metrics.expectancy?.toFixed(2) ?? "—"} color={(metrics.expectancy || 0) > 0 ? "success" : "default"} />
              <StatCard label="Avg Realized R" value={metrics.avg_realized_r?.toFixed(2) ?? "—"} color={(metrics.avg_realized_r || 0) > 0 ? "success" : "default"} />
              <StatCard label="Avg Planned RR" value={metrics.avg_planned_rr?.toFixed(2) ?? "—"} color="default" />
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
              <StatCard label="Best Trade" value={metrics.best_trade_r?.toFixed(2) ?? "—"} color="success" />
              <StatCard label="Worst Trade" value={metrics.worst_trade_r?.toFixed(2) ?? "—"} color="error" />
              <StatCard label="Avg Win" value={metrics.average_win?.toFixed(2) ?? "—"} color="success" />
              <StatCard label="Avg Loss" value={metrics.average_loss?.toFixed(2) ?? "—"} color="error" />
            </div>

            {/* Charts */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
              {equityData.length > 1 && (
                <EquityCurve data={equityData} color="#22c55e" label="Equity Curve (Cumulative R)" height={220} />
              )}
              {drawdownData.length > 1 && (
                <EquityCurve data={drawdownData} color="#ef4444" label="Drawdown Curve" height={220} />
              )}
            </div>

            {/* Overview */}
            {overview && (
              <div className="bg-raised border border-line rounded-lg p-4 mb-6">
                <h2 className="text-sm font-semibold mb-3 text-ink">Overview</h2>
                <div className="text-xs text-ink-muted space-y-1">
                  <div>All Trades: <span className="text-ink">{overview.all_trades_count ?? 0}</span></div>
                  <div>Closed: <span className="text-ink">{overview.closed_count ?? 0}</span></div>
                  <div>Strategic: <span className="text-ink">{overview.strategic_count ?? 0}</span></div>
                  <div>Active: <span className="text-ink">{overview.active_count ?? 0}</span></div>
                  <div>Planned: <span className="text-ink">{overview.planned_count ?? 0}</span></div>
                  <div>Filled: <span className="text-ink">{overview.filled_count ?? 0}</span></div>
                  <div>Generated: {data?.generated_at ? new Date(data.generated_at).toLocaleString() : "—"}</div>
                </div>
              </div>
            )}

            {/* Timeline */}
            {timeline.length > 0 && (
              <div className="bg-raised border border-line rounded-lg p-4">
                <h2 className="text-sm font-semibold mb-3 text-ink">Performance Timeline</h2>
                <div className="max-h-64 overflow-y-auto">
                  <Table columns={["Date", "Trades", "Wins", "Losses", "Net P&L"]}>
                    {timeline.map((entry: any, i: number) => (
                      <tr key={i}>
                        <Td className="text-xs">{entry.hour || entry.date || entry.period || "—"}</Td>
                        <Td>{entry.total || entry.trades || 0}</Td>
                        <Td className="text-ok">{entry.wins || entry.win_count || 0}</Td>
                        <Td className="text-danger">{entry.losses || entry.loss_count || 0}</Td>
                        <Td mono>{(entry.net_pnl || entry.pnl || 0).toFixed(2)}</Td>
                      </tr>
                    ))}
                  </Table>
                </div>
              </div>
            )}

            {/* Distribution */}
            {data?.distributions && (Object.keys(data.distributions).length > 0) && (
              <div className="bg-raised border border-line rounded-lg p-4 mt-4">
                <h2 className="text-sm font-semibold mb-3 text-ink">Distributions</h2>
                <pre className="text-xs text-ink-muted font-mono whitespace-pre-wrap max-h-48 overflow-y-auto">
                  {JSON.stringify(data.distributions, null, 2)}
                </pre>
              </div>
            )}
          </>
        )}

        {!data && !error && <div className="text-ink-muted text-sm py-8 text-center">Loading performance data...</div>}
      </div>
    </PermissionGuard>
  );
}
