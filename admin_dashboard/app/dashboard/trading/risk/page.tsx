"use client";

import { useEffect, useState, useCallback } from "react";
import StatusBadge from "@/components/StatusBadge";
import StatCard from "@/components/StatCard";
import AccountCard from "@/components/AccountCard";
import PermissionGuard from "@/components/auth/permission_guard";
import { getRiskMonitor } from "@/lib/api";
import { useAutoRefresh } from "@/hooks/useAutoRefresh";
import { Button, Card, PageHeader, Table, Td } from "@ds/components/ui";

export default function RiskMonitorPage() {
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const res = await getRiskMonitor();
      setData(res);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => { load(); }, [load]);
  useAutoRefresh(load, 10000);

  return (
    <PermissionGuard permission="trades.read">
      <div>
        <PageHeader
          title="Risk Monitor"
          subtitle="Funded-rule compliance and drawdown tracking"
          actions={<Button onClick={load}>Refresh</Button>}
        />

        {error && <div className="text-danger text-sm mb-3">{error}</div>}

        {data && (
          <>
            {/* Summary Stats */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
              <StatCard label="Total Daily Loss" value={`${data.total_daily_loss_pct ?? 0}%`}
                color={(data.total_daily_loss_pct || 0) <= -50 ? "error" : (data.total_daily_loss_pct || 0) <= -20 ? "warning" : "default"} />
              <StatCard label="Total Max Loss" value={`${data.total_max_loss_pct ?? 0}%`}
                color={(data.total_max_loss_pct || 0) <= -50 ? "error" : (data.total_max_loss_pct || 0) <= -20 ? "warning" : "default"} />
              <StatCard label="Total Drawdown" value={`${data.total_drawdown_pct ?? 0}%`}
                color={(data.total_drawdown_pct || 0) > 20 ? "error" : (data.total_drawdown_pct || 0) > 10 ? "warning" : "default"} />
              <StatCard label="Active Risk" value={data.active_risk_usd ? `$${data.active_risk_usd}` : "$0"} color="default" />
            </div>

            {/* Account Cards */}
            {data.items && data.items.length > 0 && (
              <div className="mb-6">
                <div className="flex items-center justify-between mb-3">
                  <h2 className="text-sm font-semibold text-ink">Account Risk Profiles</h2>
                  <span className="text-xs text-ink-muted">{data.breached_accounts ?? 0} breached · {data.total_accounts ?? 0} total</span>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  {data.items.map((rp: any) => (
                    <AccountCard key={rp.account_id} account={{
                      login: rp.login,
                      broker: null,
                      platform: "MT5",
                      account_type: "Risk Profile",
                      active: !rp.breached,
                      engine_status: rp.breached ? "breached" : "active",
                      daily_pnl_pct: rp.current_daily_loss_pct,
                      drawdown: rp.daily_drawdown_pct,
                    }} />
                  ))}
                </div>
              </div>
            )}

            {/* Details Table */}
            <Card title="Detailed Risk Table" bodyClassName="p-0">
              <Table columns={["Login", "Daily Loss", "Max Loss", "Drawdown", "Profit Target", "Max Risk/Trade", "Status"]}>
                {data.items?.map((rp: any) => (
                  <tr key={rp.account_id}>
                    <Td mono>{rp.login || rp.account_id?.slice(0, 8)}</Td>
                    <Td>
                      <span className={rp.current_daily_loss_pct <= -50 ? "text-danger" : rp.current_daily_loss_pct <= -20 ? "text-warn" : ""}>
                        {rp.current_daily_loss_pct}%
                      </span>
                    </Td>
                    <Td>
                      <span className={rp.current_max_loss_pct <= -50 ? "text-danger" : rp.current_max_loss_pct <= -20 ? "text-warn" : ""}>
                        {rp.current_max_loss_pct}%
                      </span>
                    </Td>
                    <Td>
                      <span className={rp.daily_drawdown_pct > 20 ? "text-danger" : rp.daily_drawdown_pct > 10 ? "text-warn" : ""}>
                        {rp.daily_drawdown_pct}%
                      </span>
                    </Td>
                    <Td>{rp.profit_target || "—"}</Td>
                    <Td>{rp.max_risk_per_trade || "—"}</Td>
                    <Td>{rp.breached ? <StatusBadge status="error" /> : <StatusBadge status="active" />}</Td>
                  </tr>
                ))}
              </Table>
            </Card>
          </>
        )}

        {!data && !error && <div className="text-ink-muted text-sm py-8 text-center">Loading risk data...</div>}
      </div>
    </PermissionGuard>
  );
}
