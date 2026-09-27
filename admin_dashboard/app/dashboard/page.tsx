"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getOverview, listAuditLogs, OverviewResponse, AuditLogItem } from "@/lib/api";
import StatusBadge from "@/components/StatusBadge";
import { Button, Card, PageHeader, StatCard, Table, Td } from "@ds/components/ui";
import { parseApiError } from "@/lib/errors";

export default function DashboardOverview() {
  const router = useRouter();
  const [data, setData] = useState<OverviewResponse | null>(null);
  const [audit, setAudit] = useState<AuditLogItem[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    getOverview()
      .then(setData)
      .catch((e) => setError(parseApiError(e)));
    listAuditLogs("?limit=10")
      .then((res) => setAudit(res.items))
      .catch(() => {});
  }, []);

  if (error) {
    const is403 = error.includes("Access Denied") || error.includes("API 403");
    const isAuth = error.includes("Session expired") || error.includes("API 401");
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="text-lg font-semibold text-ink">
            {is403 ? "Access Denied" : isAuth ? "Session Expired" : "Connection Error"}
          </div>
          <div className="text-sm mt-1 text-ink-muted">
            {is403
              ? "You do not have permission to view the admin dashboard."
              : isAuth
              ? "Your session has expired. Please sign in again."
              : error}
          </div>
        </div>
      </div>
    );
  }

  if (!data) {
    return <div className="text-ink-muted text-center py-20">Loading dashboard...</div>;
  }

  const { engine, counts, errors_24h } = data;
  const engineRunning = engine.status?.toLowerCase() === "running";

  return (
    <div>
      <PageHeader
        title="Dashboard Overview"
        subtitle="Live platform status, performance and recent security activity."
      />

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <StatCard
          label="Engine Status"
          value={engine.status}
          sub={engine.mt5_connected ? "MT5 connected" : "MT5 disconnected"}
          icon="cpu"
          tone={engineRunning ? "green" : "red"}
        />
        <StatCard
          label="Uptime"
          value={engine.uptime_hours ? `${engine.uptime_hours.toFixed(1)}h` : "—"}
          sub={engine.started_at ? `Started ${new Date(engine.started_at).toLocaleDateString()}` : undefined}
          icon="clock"
        />
        <StatCard
          label="Active Trades"
          value={engine.active_trades}
          icon="activity"
          tone={engine.active_trades > 0 ? "green" : "default"}
        />
        <StatCard
          label="Errors (24h)"
          value={errors_24h}
          icon="alert-triangle"
          tone={errors_24h > 0 ? "red" : "green"}
        />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard label="Total Clients" value={counts.total_clients} icon="users" />
        <StatCard label="Active Subscriptions" value={counts.active_subscriptions} icon="scroll" tone="green" />
        <StatCard label="Connected Accounts" value={counts.connected_accounts} icon="server" />
        <StatCard
          label="Support Tickets"
          value={counts.open_support_tickets}
          icon="lifebuoy"
          tone={counts.open_support_tickets > 0 ? "amber" : "default"}
        />
      </div>

      <div className="flex flex-wrap gap-2 mb-8">
        <Button icon="chart" onClick={() => router.push("/dashboard/trading")}>
          Trading Overview
        </Button>
        <Button variant="secondary" icon="activity" onClick={() => router.push("/dashboard/trading/trades")}>
          Active Trades
        </Button>
        <Button variant="secondary" icon="alert-triangle" onClick={() => router.push("/dashboard/trading/risk")}>
          Risk Monitor
        </Button>
        <Button variant="secondary" icon="users" onClick={() => router.push("/dashboard/users")}>
          Users
        </Button>
        <Button variant="secondary" icon="users" onClick={() => router.push("/dashboard/clients")}>
          Clients
        </Button>
        <Button variant="secondary" icon="gauge" onClick={() => router.push("/dashboard/system")}>
          System
        </Button>
      </div>

      <Card title="Recent Audit Logs" subtitle="Latest 10 recorded actions" icon="scroll">
        <Table
          columns={["Time", "Action", "Severity", "Actor", "Target"]}
          className="-mx-5 px-5"
        >
          {audit.length === 0 && (
            <tr>
              <td colSpan={5} className="text-center text-ink-muted py-6 px-4">
                No logs
              </td>
            </tr>
          )}
          {audit.map((log) => (
            <tr key={log.id}>
              <Td className="text-ink-muted whitespace-nowrap">
                {log.timestamp ? new Date(log.timestamp).toLocaleString() : "—"}
              </Td>
              <Td>{log.action}</Td>
              <Td>
                <StatusBadge status={log.severity} />
              </Td>
              <Td>{log.actor || "—"}</Td>
              <Td className="max-w-[200px] truncate">{log.target || "—"}</Td>
            </tr>
          ))}
        </Table>
      </Card>
    </div>
  );
}
