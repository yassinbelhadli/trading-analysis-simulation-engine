"use client";

import { useCallback, useEffect, useState } from "react";
import OwnerPermissionGuard from "@/components/auth/owner_permission_guard";
import {
  getTelegramChannelStatus,
  getEmailChannelStatus,
  getEngineStatus,
  getHeartbeat,
} from "@/lib/api";
import { PageHeader, Card, Badge, Skeleton, type BadgeTone } from "@ds/components/ui";
import { Icon, type IconName } from "@ds/components/Icon";

interface ChannelState {
  key: string;
  label: string;
  icon: IconName;
  status: "connected" | "warning" | "offline" | "unknown";
  detail: string;
}

function toneFor(status: ChannelState["status"]): BadgeTone {
  if (status === "connected") return "green";
  if (status === "warning") return "amber";
  if (status === "offline") return "red";
  return "gray";
}

export default function IntegrationsPage() {
  const [channels, setChannels] = useState<ChannelState[] | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      const [tg, email, news, hb] = await Promise.all([
        getTelegramChannelStatus(),
        getEmailChannelStatus(),
        getEngineStatus(),
        getHeartbeat(),
      ]);

      const rows: ChannelState[] = [
        {
          key: "mt",
          label: "MT4 / MT5 Bridge",
          icon: "server",
          status: hb?.mt5_connected ? "connected" : "offline",
          detail: hb?.mt5_connected
            ? `Heartbeat ${hb.last_heartbeat_utc ? new Date(hb.last_heartbeat_utc).toLocaleString() : "—"} · ${hb.cycles ?? 0} cycles`
            : "No MT5 bridge heartbeat (engine not running)",
        },
        {
          key: "news",
          label: "Economic News Feed (ForexFactory)",
          icon: "newspaper",
          status: news?.running ? "connected" : "warning",
          detail: news?.running
            ? `${news.total_events ?? 0} events in DB · ${news.upcoming_high?.length ?? 0} upcoming high/medium`
            : "News engine idle — waiting for the next fetch cycle",
        },
        {
          key: "telegram",
          label: "Telegram Channel",
          icon: "send",
          status: tg?.telegram_configured ? "connected" : "offline",
          detail: "",
        },
        {
          key: "email",
          label: "Email / SMTP",
          icon: "mail",
          status: email?.email_configured ? "connected" : "warning",
          detail: email?.email_configured ? "SMTP configured" : "SMTP credentials not configured",
        },
      ];

      // Enrich telegram detail after status row is built
      const tgRow = rows.find((r) => r.key === "telegram");
      if (tgRow && tg?.telegram_configured) {
        tgRow.detail = `@${tg.bot_username} · ${tg.linked_users ?? 0} linked users${tg.telegram_test_mode ? " · TEST MODE" : ""}`;
      }
      if (tg?.telegram_test_mode) {
        tgRow && (tgRow.status = "warning");
      }
      if (email?.email_test_mode) {
        const em = rows.find((r) => r.key === "email");
        em && (em.status = "warning");
        em && (em.detail = `${em.detail} · TEST MODE`);
      }

      setChannels(rows);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load integration status");
      setChannels([]);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <OwnerPermissionGuard permission="system.health.read">
      <div className="flex flex-col gap-5 max-w-6xl">
        <PageHeader
          title="Integrations"
          subtitle="Live status of every external channel the platform connects to. Status is read-only; configuration lives in the Settings module."
        />

        {error && (
          <div className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
            {error}
          </div>
        )}

        {!channels ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-28 rounded-xl" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {channels.map((ch) => (
              <Card key={ch.key} icon={ch.icon} title={ch.label}>
                <div className="flex items-center justify-between mb-2">
                  <Badge tone={toneFor(ch.status)}>{ch.status}</Badge>
                </div>
                <p className="text-sm text-ink-muted">{ch.detail || "—"}</p>
              </Card>
            ))}
          </div>
        )}

        <div className="rounded-xl border border-line bg-raised px-5 py-4 text-xs text-ink-muted">
          <div className="flex items-start gap-2">
            <Icon name="info" className="h-4 w-4 mt-0.5 shrink-0" />
            <p>
              Configuration of these channels happens through the Settings module and the
              platform environment file (<code className="font-mono">config/.env</code>). Secrets
              are never exposed by this page — only presence and health state.
            </p>
          </div>
        </div>
      </div>
    </OwnerPermissionGuard>
  );
}
