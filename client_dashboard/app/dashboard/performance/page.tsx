"use client";

import { useEffect, useState } from "react";
import { getClientPerformance, type PerformanceData } from "@/lib/api";
import { PageHeader, Card, StatCard, Table, Td, EmptyState, Skeleton } from "@ds/components/ui";
import { useLocale } from "@/components/LocaleContext";

export default function PerformancePage() {
  const { t } = useLocale();
  const [data, setData] = useState<PerformanceData | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getClientPerformance()
      .then(setData)
      .catch((e) => setError(e.message));
  }, []);

  if (error) {
    return <EmptyState icon="alert-triangle" title={t("performance.loadError")} description={error} />;
  }
  if (!data) {
    return (
      <div className="flex flex-col gap-5">
        <div className="h-8 w-48 rounded bg-hover animate-pulse" />
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
        <Skeleton className="h-80 w-full" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t("performance.title")} subtitle={t("performance.subtitle")} />

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
        <StatCard label={t("performance.totalTrades")} value={data.total_trades} icon="activity" />
        <StatCard
          label={t("performance.netPnl")}
          value={`${data.net_pnl >= 0 ? "+" : ""}$${data.net_pnl.toFixed(2)}`}
          tone={data.net_pnl >= 0 ? "green" : "red"}
          icon="dollar"
          mono
        />
        <StatCard
          label={t("performance.profitFactor")}
          value={data.profit_factor.toFixed(2)}
          tone={data.profit_factor >= 1.5 ? "green" : "amber"}
          icon="gauge"
          mono
        />
        <StatCard
          label={t("performance.winRate")}
          value={`${data.win_rate}%`}
          tone={data.win_rate >= 50 ? "green" : "amber"}
          icon="check-circle"
        />
        <StatCard
          label={t("performance.avgR")}
          value={`${data.avg_r}R`}
          tone={data.avg_r >= 1 ? "green" : "amber"}
          icon="trending-up"
          mono
        />
        <StatCard
          label={t("performance.maxDd")}
          value={`$${data.max_drawdown.toFixed(2)}`}
          tone="red"
          icon="trending-down"
          mono
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Card title={t("performance.bySymbol")} icon="chart-bar">
          {data.by_symbol.length === 0 ? (
            <EmptyState icon="chart-bar" title={t("performance.noSymbolData")} description={t("performance.noSymbolDesc")} />
          ) : (
            <Table columns={[t("performance.colSymbol"), t("performance.colTrades"), t("performance.colWins"), t("performance.colLosses"), t("performance.colPnl")]}>
              {data.by_symbol.map((s) => (
                <tr key={s.symbol}>
                  <Td mono className="font-medium">{s.symbol}</Td>
                  <Td mono className="text-right">{s.trades}</Td>
                  <Td mono className="text-right text-ok">{s.wins}</Td>
                  <Td mono className="text-right text-danger">{s.losses}</Td>
                  <Td mono className={`text-right font-medium ${s.pnl >= 0 ? "text-ok" : "text-danger"}`}>
                    {s.pnl >= 0 ? "+" : ""}${s.pnl.toFixed(2)}
                  </Td>
                </tr>
              ))}
            </Table>
          )}
        </Card>

        <Card title={t("performance.monthlyPnl")} icon="calendar">
          {data.by_month.length === 0 ? (
            <EmptyState icon="calendar" title={t("performance.noMonthlyData")} description={t("performance.noMonthlyDesc")} />
          ) : (
            <Table columns={[t("performance.colMonth"), t("performance.colTrades"), t("performance.colPnl")]}>
              {data.by_month.map((m) => (
                <tr key={m.month}>
                  <Td className="text-ink-soft">{m.month}</Td>
                  <Td mono className="text-right">{m.trades}</Td>
                  <Td mono className={`text-right font-medium ${m.pnl >= 0 ? "text-ok" : "text-danger"}`}>
                    {m.pnl >= 0 ? "+" : ""}${m.pnl.toFixed(2)}
                  </Td>
                </tr>
              ))}
            </Table>
          )}
        </Card>
      </div>

      <Card title={t("performance.equityCurve")} icon="chart">
        {data.equity_curve.length === 0 ? (
          <div className="h-44 flex items-center justify-center text-sm text-ink-muted">
            {t("performance.noEquity")}
          </div>
        ) : (
          <div className="h-48 flex items-end gap-1">
            {data.equity_curve.map((p, i) => {
              const maxEquity = Math.max(...data.equity_curve.map((e) => e.equity), 1);
              const minEquity = Math.min(...data.equity_curve.map((e) => e.equity), 0);
              const range = Math.max(maxEquity - minEquity, 1);
              const height = ((p.equity - minEquity) / range) * 100;
              return (
                <div key={i} className="flex-1 flex flex-col items-center justify-end h-full">
                  <div
                    className="w-full rounded-t transition-all duration-300"
                    style={{
                      height: `${Math.max(height, 2)}%`,
                      backgroundColor: p.equity >= 0 ? "var(--color-brand-500)" : "var(--color-danger)",
                      opacity: 0.7,
                    }}
                    title={`${p.date}: $${p.equity.toFixed(2)}`}
                  />
                </div>
              );
            })}
          </div>
        )}
      </Card>
    </div>
  );
}
