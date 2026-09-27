"use client";

import { useCallback, useEffect, useState } from "react";
import PermissionGuard from "@/components/auth/permission_guard";
import {
  getEmailStatus,
  getAdminTelegramStatus,
  sendTestEmail,
  sendTestTelegram,
  type DeliveryRecord,
} from "@/lib/api";
import { PageHeader, Card, Badge, Button, EmptyState, Skeleton, TextField } from "@ds/components/ui";
import { Icon } from "@ds/components/Icon";

type Notice = { ok: boolean; text: string } | null;

export default function NotificationsPage() {
  const [email, setEmail] = useState<Awaited<ReturnType<typeof getEmailStatus>> | null>(null);
  const [telegram, setTelegram] = useState<Awaited<ReturnType<typeof getAdminTelegramStatus>> | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState<Notice>(null);
  const [emailBusy, setEmailBusy] = useState(false);
  const [tgBusy, setTgBusy] = useState(false);
  const [testChatId, setTestChatId] = useState("");

  const load = useCallback(async () => {
    try {
      const [e, t] = await Promise.all([getEmailStatus(), getAdminTelegramStatus()]);
      setEmail(e);
      setTelegram(t);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load notification status");
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleTestEmail = async () => {
    setNotice(null);
    setEmailBusy(true);
    try {
      const res = await sendTestEmail();
      setNotice({ ok: res.success, text: res.mock ? `${res.message} (test mode)` : res.message });
      load();
    } catch (err) {
      setNotice({ ok: false, text: err instanceof Error ? err.message : "Test email failed" });
    } finally {
      setEmailBusy(false);
    }
  };

  const handleTestTelegram = async () => {
    setNotice(null);
    const chatId = Number(testChatId);
    if (!chatId || chatId <= 0) {
      setNotice({ ok: false, text: "Enter a valid chat ID." });
      return;
    }
    setTgBusy(true);
    try {
      const res = await sendTestTelegram(chatId);
      setNotice({ ok: res.success, text: res.mock ? `${res.message} (test mode)` : res.message });
      load();
    } catch (err) {
      setNotice({ ok: false, text: err instanceof Error ? err.message : "Test telegram failed" });
    } finally {
      setTgBusy(false);
    }
  };

  if (error && !email && !telegram) {
    return (
      <PermissionGuard permission="emails.read">
        <EmptyState icon="alert-triangle" title="Could not load notification status" description={error} />
      </PermissionGuard>
    );
  }
  if (!email || !telegram) {
    return (
      <PermissionGuard permission="emails.read">
        <div className="flex flex-col gap-5">
          <div className="h-8 w-56 rounded bg-hover animate-pulse" />
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-40 w-full" />
        </div>
      </PermissionGuard>
    );
  }

  return (
    <PermissionGuard permission="emails.read">
      <div className="flex flex-col gap-5">
        <PageHeader
          title="Notifications"
          subtitle="Delivery channel status and test broadcasts for email and Telegram."
        />

        {notice && (
          <div
            className={`flex items-center gap-2 text-sm px-3 py-2 rounded-lg border ${
              notice.ok ? "text-ok border-ok/30 bg-ok/10" : "text-danger border-danger/30 bg-danger/10"
            }`}
          >
            <Icon name={notice.ok ? "check-circle" : "alert-triangle"} className="h-4 w-4 shrink-0" />
            {notice.text}
          </div>
        )}

        <Card
          title="Email Channel"
          icon="mail"
          actions={
            <Badge tone={email.email_configured ? "green" : "gray"}>
              {email.email_configured ? "Configured" : "Not configured"}
              {email.email_test_mode ? " · test mode" : ""}
            </Badge>
          }
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-3 text-sm">
            <Info k="SMTP" v={email.email_configured ? "Credentials present" : "Missing credentials"} />
            <Info k="Delivery mode" v={email.email_test_mode ? "Mocked (test)" : "Live SMTP"} />
          </div>
          <PermissionGuard permission="emails.send" fallback={null}>
            <div className="mt-4 flex flex-wrap items-center gap-2.5">
              <Button variant="secondary" size="sm" icon="send" onClick={handleTestEmail} loading={emailBusy}>
                {emailBusy ? "Sending…" : "Send test email"}
              </Button>
            </div>
          </PermissionGuard>
          <div className="mt-4">
            <RecentDeliveries rows={email.recent_deliveries} />
          </div>
        </Card>

        <Card
          title="Telegram Channel"
          icon="send"
          actions={
            <Badge tone={telegram.telegram_configured ? "green" : "gray"}>
              {telegram.telegram_configured ? "Configured" : "Not configured"}
              {telegram.telegram_test_mode ? " · test mode" : ""}
            </Badge>
          }
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-3 text-sm">
            <Info k="Bot" v={`@${telegram.bot_username}`} />
            <Info k="Linked users" v={String(telegram.linked_users)} />
            <Info k="Delivery mode" v={telegram.telegram_test_mode ? "Mocked (test)" : "Live API"} />
          </div>
          <PermissionGuard permission="telegram.send" fallback={null}>
            <div className="mt-4 flex flex-wrap items-end gap-2">
              <div className="flex-1 min-w-[220px]">
                <TextField
                  label="Chat ID for test broadcast"
                  value={testChatId}
                  onChange={(e) => setTestChatId(e.target.value)}
                placeholder="e.g. 123456789"
                icon="send"
                />
              </div>
              <Button variant="secondary" size="sm" icon="send" onClick={handleTestTelegram} loading={tgBusy}>
                {tgBusy ? "Sending…" : "Send test message"}
              </Button>
            </div>
          </PermissionGuard>
          <div className="mt-4">
            <RecentDeliveries rows={telegram.recent_deliveries} />
          </div>
        </Card>
      </div>
    </PermissionGuard>
  );
}

function Info({ k, v }: { k: string; v: string }) {
  return (
    <div>
      <div className="text-xs text-ink-muted">{k}</div>
      <div className="mt-0.5 text-ink">{v}</div>
    </div>
  );
}

function RecentDeliveries({ rows }: { rows: DeliveryRecord[] }) {
  if (rows.length === 0) {
    return <p className="text-xs text-ink-muted">No recent deliveries recorded.</p>;
  }
  return (
    <div className="rounded-lg border border-line overflow-hidden">
      <div className="text-xs font-medium text-ink-muted px-3 py-2 border-b border-line bg-input">
        Recent deliveries
      </div>
      <ul className="divide-y divide-line">
        {rows.slice(0, 8).map((r) => (
          <li key={r.id} className="flex items-center justify-between gap-3 px-3 py-2 text-xs">
            <span className="text-ink-soft truncate">{r.message}</span>
            <span className="text-ink-muted shrink-0 font-mono">
              {r.created_at ? new Date(r.created_at).toLocaleString() : "—"}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
