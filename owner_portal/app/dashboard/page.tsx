"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  PageHeader,
  StatCard,
  Card,
  Badge,
  type BadgeTone,
  Table,
  Td,
  Skeleton,
  EmptyState,
  Button,
} from "@ds/components/ui";
import { Icon } from "@ds/components/Icon";
import { getOverview, listAuditLogs, OverviewResponse, AuditLogItem } from "@/lib/api";
import { parseApiError } from "@/lib/errors";

const QUICK_ACTIONS = [
  { href: "/dashboard/revenue", label: "Revenue", icon: "dollar" as const },
  { href: "/dashboard/engine", label: "Engine Control", icon: "zap" as const },
  { href: "/dashboard/users", label: "Users", icon: "users" as const },
  { href: "/dashboard/roles", label: "Roles", icon: "shield-check" as const },
  { href: "/dashboard/audit", label: "Audit Logs", icon: "scroll" as const },
  { href: "/dashboard/system", label: "System Health", icon: "gauge" as const },
];

function severityTone(s: string): BadgeTone {
  if (s === "critical" || s === "error") return "red";
  if (s === "warning") return "amber";
  if (s === "info") return "blue";
  return "gray";
}

export default function OwnerOverview() {
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
    return (
      <EmptyState
        icon="alert-triangle"
        title="Could not load the overview"
        description={error}
      />
    );
  }

  if (!data) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-28 rounded-xl" />
          ))}
        </div>
        <Skeleton className="h-56 rounded-xl" />
      </div>
    );
  }

  const { engine, counts, errors_24h } = data;
  const running = engine.status?.toLowerCase() === "running";

  return (
    <div className="flex flex-col gap-5 max-w-6xl">
      <PageHeader
        title="Platform Overview"
        subtitle="Business and platform control plane — global visibility."
      />

      {/* Engine + platform KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Engine Status"
          value={engine.status}
          sub={engine.pid != null ? `PID ${engine.pid}` : undefined}
          tone={running ? "green" : "red"}
          icon="cpu"
          mono
        />
        <StatCard
          label="Uptime"
          value={engine.uptime_hours != null ? `${engine.uptime_hours.toFixed(1)}h` : "—"}
          sub={engine.started_at ? new Date(engine.started_at).toLocaleDateString() : undefined}
          icon="clock"
          tone="blue"
        />
        <StatCard
          label="Active Trades"
          value={engine.active_trades}
          tone={engine.active_trades > 0 ? "green" : "default"}
          icon="activity"
          mono
        />
        <StatCard
          label="Errors (24h)"
          value={errors_24h}
          tone={errors_24h > 0 ? "red" : "green"}
          icon="alert-triangle"
          mono
        />
      </div>

      {/* Client base KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Total Clients" value={counts.total_clients} icon="users" mono />
        <StatCard
          label="Active Subscriptions"
          value={counts.active_subscriptions}
          tone={counts.active_subscriptions > 0 ? "green" : "default"}
          icon="credit-card"
          mono
        />
        <StatCard
          label="Connected Accounts"
          value={counts.connected_accounts}
          icon="server"
          tone="blue"
          mono
        />
        <StatCard
          label="Support Tickets"
          value={counts.open_support_tickets}
          tone={counts.open_support_tickets > 0 ? "amber" : "default"}
          icon="lifebuoy"
          mono
        />
      </div>

      {/* Engine live status */}
      <Card title="Engine Status" icon="activity" subtitle="Live connectivity for the trading engine">
        <div className="flex flex-col sm:flex-row sm:items-center gap-3 text-sm">
          <div className="flex items-center gap-2">
            <span className={`h-2 w-2 rounded-full ${running ? "bg-ok" : "bg-danger"}`} />
            <span className="text-ink-soft">Trading engine</span>
            <Badge tone={running ? "green" : "red"}>{engine.status}</Badge>
          </div>
          <div className="flex items-center gap-2">
            <span className={`h-2 w-2 rounded-full ${engine.mt5_connected ? "bg-ok" : "bg-ink-muted"}`} />
            <span className="text-ink-soft">MT5</span>
            <Badge tone={engine.mt5_connected ? "green" : "gray"}>
              {engine.mt5_connected ? "Connected" : "Disconnected"}
            </Badge>
          </div>
          <div className="flex items-center gap-2">
            <span className={`h-2 w-2 rounded-full ${engine.telegram_connected ? "bg-ok" : "bg-ink-muted"}`} />
            <span className="text-ink-soft">Telegram</span>
            <Badge tone={engine.telegram_connected ? "green" : "gray"}>
              {engine.telegram_connected ? "Connected" : "Not linked"}
            </Badge>
          </div>
          <div className="sm:ml-auto flex items-center gap-4 text-xs text-ink-muted">
            {engine.cycles != null && (
              <span className="flex items-center gap-1">
                <Icon name="refresh" className="h-3.5 w-3.5" />
                {engine.cycles} cycles
              </span>
            )}
            {engine.memory_mb != null && (
              <span className="flex items-center gap-1">
                <Icon name="hard-drive" className="h-3.5 w-3.5" />
                {engine.memory_mb} MB
              </span>
            )}
            {engine.cpu_percent != null && (
              <span className="flex items-center gap-1">
                <Icon name="cpu" className="h-3.5 w-3.5" />
                {engine.cpu_percent}% CPU
              </span>
            )}
          </div>
        </div>
      </Card>

      {/* Recent audit logs */}
      <Card title="Recent Audit Logs" icon="scroll" actions={null}>
        {audit.length === 0 ? (
          <EmptyState
            icon="scroll"
            title="No audit logs yet"
            description="Audit entries will appear here as actions are performed across the platform."
          />
        ) : (
          <Table
            columns={["Time", "Action", "Severity", "Actor", "Target"]}
          >
            {audit.map((log) => (
              <tr key={log.id}>
                <Td className="text-xs text-ink-muted whitespace-nowrap">
                  {log.timestamp ? new Date(log.timestamp).toLocaleString() : "—"}
                </Td>
                <Td mono className="text-xs">{log.action}</Td>
                <Td>
                  <Badge tone={severityTone(log.severity)}>{log.severity}</Badge>
                </Td>
                <Td className="text-xs text-ink-soft">{log.actor || "—"}</Td>
                <Td className="text-xs text-ink-soft truncate max-w-[220px]">{log.target || "—"}</Td>
              </tr>
            ))}
          </Table>
        )}
      </Card>

      {/* Quick actions */}
      <Card title="Control Plane" icon="zap">
        <div className="flex flex-wrap gap-2">
          {QUICK_ACTIONS.map((a) => (
            <Link key={a.href} href={a.href}>
              <Button variant="secondary" icon={a.icon}>
                {a.label}
              </Button>
            </Link>
          ))}
        </div>
      </Card>
    </div>
  );
}
