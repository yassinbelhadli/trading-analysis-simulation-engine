"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { createChart, ColorType, AreaSeries, UTCTimestamp } from "lightweight-charts";
import { getClientDashboard, type ClientDashboardResponse, type EquityPoint } from "@/lib/api";
import { PageHeader, StatCard, Badge, StatusPill, Card, Button, EmptyState } from "@ds/components/ui";
import { Icon, type IconName } from "@ds/components/Icon";
import { parseApiError } from "@/lib/errors";
import { useLocale } from "@/components/LocaleContext";
import { formatUserDate } from "@/lib/timezone";

export default function DashboardOverview() {
  const { t, timezone: userTimezone } = useLocale();
  const [data, setData] = useState<ClientDashboardResponse | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getClientDashboard()
      .then(setData)
      .catch((e) => setError(parseApiError(e)));
  }, []);

  if (error) {
    return (
      <EmptyState
        icon="alert-triangle"
        title={t("overview.loadError")}
        description={error}
      />
    );
  }
  if (!data) {
    return (
      <div className="space-y-4">
        <SkeletonBlock />
      </div>
    );
  }

  const lic = data.license;
  const sub = data.subscription;
  const ts = data.trading_status;

  return (
    <div className="flex flex-col gap-5 max-w-6xl">
      <PageHeader
        title={t("overview.welcome", { name: data.welcome_name })}
        subtitle={t("overview.subtitle")}
      />

      {/* Status cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <StatusCard icon="key" title={t("overview.license")}>
          {lic ? (
            <>
              <div className="flex items-center gap-2">
                <Badge tone={lic.status === "active" ? "green" : lic.status === "expired" ? "red" : "amber"}>
                  {lic.status === "active" ? t("common.active") : lic.status}
                </Badge>
                <span className="text-sm capitalize text-ink">{lic.plan}</span>
              </div>
              <div className="text-xs text-ink-muted mt-2">
                {lic.days_remaining != null
                  ? t("overview.daysRemaining", { n: lic.days_remaining })
                  : t("overview.noExpiry")}
              </div>
            </>
          ) : (
            <p className="text-sm text-ink-muted py-2">{t("overview.noLicense")}</p>
          )}
        </StatusCard>

        <StatusCard icon="credit-card" title={t("overview.subscription")}>
          {sub ? (
            <>
              <div className="flex items-center gap-2">
                <StatusPill status={sub.active ? "active" : "error"}>
                  {sub.active ? t("common.active") : t("common.expired")}
                </StatusPill>
                <span className="text-sm capitalize text-ink">{sub.plan}</span>
              </div>
              <div className="text-xs text-ink-muted mt-2">
                {sub.renew_date
                  ? t("overview.renews", { date: formatUserDate(sub.renew_date, userTimezone) })
                  : t("overview.noRenewDate")}
              </div>
            </>
          ) : (
            <p className="text-sm text-ink-muted py-2">{t("overview.noSubscription")}</p>
          )}
        </StatusCard>

        <StatusCard icon="activity" title={t("overview.tradingStatus")}>
          <div className="flex flex-col gap-2 text-sm">
            <StatusRow on={ts.running} label={t("overview.trading")} text={ts.running ? t("overview.running") : t("overview.stopped")} />
            <StatusRow on={ts.mt5_connected} label="MT5" text={ts.mt5_connected ? t("overview.connected") : t("overview.disconnected")} />
            <StatusRow on={ts.telegram_connected} label="Telegram" text={ts.telegram_connected ? t("overview.connected") : t("overview.notLinked")} />
          </div>
        </StatusCard>
      </div>

      {/* Today's performance */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label={t("overview.todayProfit")}
          value={`${data.today.profit >= 0 ? "+" : ""}$${data.today.profit.toFixed(2)}`}
          tone={data.today.profit >= 0 ? "green" : "red"}
          icon="trending-up"
          mono
        />
        <StatCard
          label={t("overview.winRate")}
          value={`${data.today.win_rate}%`}
          tone={data.today.win_rate >= 50 ? "green" : "amber"}
          icon="gauge"
        />
        <StatCard
          label={t("overview.openTrades")}
          value={data.today.open_trades}
          tone={data.today.open_trades > 0 ? "amber" : "default"}
          icon="activity"
        />
        <StatCard label={t("overview.closedToday")} value={data.today.closed_trades} icon="check-circle" />
      </div>

      {/* Equity + totals */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card title={t("overview.equityCurve")} icon="chart" className="lg:col-span-2">
          {data.equity_curve.length >= 2 ? (
            <EquityChart points={data.equity_curve} />
          ) : (
            <div className="h-40 flex items-center justify-center text-sm text-ink-muted">
              {t("overview.noEquity")}
            </div>
          )}
        </Card>
        <Card title={t("overview.accountTotals")} icon="wallet">
          <div className="flex flex-col gap-2 text-sm">
            <TotalRow k={t("overview.balance")} v={`$${data.totals.balance.toLocaleString()}`} />
            <TotalRow k={t("overview.equity")} v={`$${data.totals.equity.toLocaleString()}`} />
            <TotalRow
              k={t("overview.totalPnl")}
              v={`${data.totals.total_pnl >= 0 ? "+" : ""}$${data.totals.total_pnl.toFixed(2)}`}
              color={data.totals.total_pnl >= 0 ? "ok" : "err"}
            />
            <TotalRow k={t("overview.totalTrades")} v={data.totals.total_trades} />
            <TotalRow k={t("overview.profitFactor")} v={data.totals.profit_factor.toFixed(2)} />
          </div>
        </Card>
      </div>

      {/* Recent signals + trades */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card title={t("overview.recentSignals")} icon="zap">
          {data.recent_signals.length === 0 ? (
            <p className="text-sm text-ink-muted py-4 text-center">{t("overview.noSignals")}</p>
          ) : (
            <div className="overflow-x-auto -mx-5 px-5">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-xs text-ink-muted text-left">
                    <th className="py-1.5 pr-2">{t("overview.symbol")}</th>
                    <th className="pr-2">{t("overview.direction")}</th>
                    <th className="pr-2">{t("overview.entry")}</th>
                    <th className="pr-2">{t("overview.stopLoss")}</th>
                    <th>{t("overview.takeProfit")}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.recent_signals.map((s) => (
                    <tr key={s.id} className="border-t border-line/70">
                      <td className="py-2 pr-2 font-mono font-medium">{s.symbol}</td>
                      <td className="pr-2">
                        <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium ${
                          s.direction === "BUY"
                            ? "bg-brand-tint text-brand-400"
                            : "bg-danger/10 text-danger"
                        }`}>
                          <Icon name={s.direction === "BUY" ? "trending-up" : "trending-down"} className="h-3 w-3" />
                          {s.direction}
                        </span>
                      </td>
                      <td className="pr-2 text-ink-soft">{s.entry_price ?? "—"}</td>
                      <td className="pr-2 text-ink-soft">{s.stop_loss ?? "—"}</td>
                      <td className="text-ink-soft">{s.take_profit ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <Card title={t("overview.recentTrades")} icon="activity">
          {data.recent_trades.length === 0 ? (
            <p className="text-sm text-ink-muted py-4 text-center">{t("overview.noTrades")}</p>
          ) : (
            <div className="overflow-x-auto -mx-5 px-5">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-xs text-ink-muted text-left">
                    <th className="py-1.5 pr-2">{t("overview.symbol")}</th>
                    <th className="pr-2">{t("overview.direction")}</th>
                    <th className="pr-2">{t("overview.risk")}</th>
                    <th className="text-right">{t("overview.pnl")}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.recent_trades.map((tr) => (
                    <tr key={tr.id} className="border-t border-line/70">
                      <td className="py-2 pr-2 font-mono font-medium">{tr.symbol}</td>
                      <td className="pr-2">
                        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                          tr.direction === "BUY"
                            ? "bg-brand-tint text-brand-400"
                            : "bg-danger/10 text-danger"
                        }`}>
                          {tr.direction}
                        </span>
                      </td>
                      <td className="pr-2 text-ink-soft">
                        {tr.realized_r != null ? `${tr.realized_r >= 0 ? "+" : ""}${tr.realized_r.toFixed(2)}R` : "—"}
                      </td>
                      <td className={`text-right font-medium font-mono ${(tr.realized_pnl ?? 0) >= 0 ? "text-ok" : "text-danger"}`}>
                        {(tr.realized_pnl ?? 0) >= 0 ? "+" : ""}${(tr.realized_pnl ?? 0).toFixed(2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>

      {/* Quick actions */}
      <Card title={t("overview.quickActions")} icon="zap">
        <div className="flex flex-wrap gap-2">
          <Link href="/dashboard/subscription">
            <Button icon="credit-card">{t("overview.manageSubscription")}</Button>
          </Link>
          <Link href="/dashboard/license">
            <Button variant="secondary" icon="key">{t("overview.viewLicense")}</Button>
          </Link>
          <Link href="/dashboard/activity">
            <Button variant="secondary" icon="activity">{t("overview.allTrades")}</Button>
          </Link>
          <Link href="/dashboard/performance">
            <Button variant="secondary" icon="chart">{t("overview.performance")}</Button>
          </Link>
        </div>
      </Card>
    </div>
  );
}

function StatusCard({ title, icon, children }: { title: string; icon: IconName; children: React.ReactNode }) {
  return (
    <Card title={title} icon={icon}>
      {children}
    </Card>
  );
}

function StatusRow({ on, label, text }: { on: boolean; label: string; text: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className={`h-2 w-2 rounded-full ${on ? "bg-ok" : "bg-ink-muted"}`} />
      <span className="text-ink-soft">{label}</span>
      <span className={`ml-auto font-medium ${on ? "text-ok" : "text-ink-soft"}`}>{text}</span>
    </div>
  );
}

function TotalRow({ k, v, color }: { k: string; v: string | number; color?: "ok" | "err" }) {
  return (
    <div className="flex justify-between">
      <span className="text-ink-soft">{k}</span>
      <span className={`font-medium font-mono ${color === "ok" ? "text-ok" : color === "err" ? "text-danger" : "text-ink"}`}>
        {v}
      </span>
    </div>
  );
}

function SkeletonBlock() {
  return (
    <>
      <div className="h-8 w-64 rounded bg-hover animate-pulse" />
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-28 rounded-xl bg-hover animate-pulse" />
        ))}
      </div>
      <div className="h-40 rounded-xl bg-hover animate-pulse" />
    </>
  );
}

function EquityChart({ points }: { points: EquityPoint[] }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const chart = createChart(el, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "var(--ds-ink-muted)",
      },
      grid: {
        vertLines: { color: "var(--ds-line)" },
        horzLines: { color: "var(--ds-line)" },
      },
      rightPriceScale: { borderColor: "var(--ds-line)" },
      timeScale: { borderColor: "var(--ds-line)", visible: false },
    });
    const area = chart.addSeries(AreaSeries, {
      lineColor: "#12b76a",
      topColor: "rgba(18, 183, 106, 0.25)",
      bottomColor: "rgba(18, 183, 106, 0)",
      lineWidth: 2,
    });
    area.setData(
      points.map((p) => ({
        time: Math.floor(new Date(p.date!).getTime() / 1000) as UTCTimestamp,
        value: p.equity,
      })),
    );
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [points]);

  return <div ref={ref} className="h-44 w-full" />;
}
