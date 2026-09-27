"use client";

import { useCallback, useEffect, useState } from "react";
import PermissionGuard from "@/components/auth/permission_guard";
import { getAdminTelegramStatus, sendTestTelegram } from "@/lib/api";
import { PageHeader, Card, Badge, Button, EmptyState, Skeleton, TextField } from "@ds/components/ui";
import { Icon } from "@ds/components/Icon";

export default function TelegramPage() {
  const [data, setData] = useState<Awaited<ReturnType<typeof getAdminTelegramStatus>> | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [testChatId, setTestChatId] = useState("");

  const load = useCallback(async () => {
    try {
      setData(await getAdminTelegramStatus());
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load Telegram status");
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleTest = async () => {
    setNotice(null);
    const chatId = Number(testChatId);
    if (!chatId || chatId <= 0) {
      setNotice({ ok: false, text: "Enter a valid chat ID." });
      return;
    }
    setBusy(true);
    try {
      const res = await sendTestTelegram(chatId);
      setNotice({ ok: res.success, text: res.mock ? `${res.message} (test mode)` : res.message });
      load();
    } catch (err) {
      setNotice({ ok: false, text: err instanceof Error ? err.message : "Test message failed" });
    } finally {
      setBusy(false);
    }
  };

  if (error && !data) {
    return (
      <PermissionGuard permission="telegram.send">
        <EmptyState icon="alert-triangle" title="Could not load Telegram status" description={error} />
      </PermissionGuard>
    );
  }
  if (!data) {
    return (
      <PermissionGuard permission="telegram.send">
        <div className="flex flex-col gap-5">
          <div className="h-8 w-56 rounded bg-hover animate-pulse" />
          <Skeleton className="h-44 w-full" />
        </div>
      </PermissionGuard>
    );
  }

  return (
    <PermissionGuard permission="telegram.send">
      <div className="flex flex-col gap-5">
        <PageHeader
          title="Telegram"
          subtitle="Bot status, linked clients, and test broadcasts."
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
          title="Bot Status"
          icon="send"
          actions={
            <Badge tone={data.telegram_configured ? "green" : "gray"}>
              {data.telegram_configured ? "Configured" : "Not configured"}
              {data.telegram_test_mode ? " · test mode" : ""}
            </Badge>
          }
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-3 text-sm">
            <Info k="Bot" v={`@${data.bot_username}`} />
            <Info k="Linked users" v={String(data.linked_users)} />
            <Info k="Delivery mode" v={data.telegram_test_mode ? "Mocked (test)" : "Live API"} />
          </div>

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
            <Button variant="secondary" size="sm" icon="send" onClick={handleTest} loading={busy}>
              {busy ? "Sending…" : "Send test message"}
            </Button>
          </div>

          <p className="text-xs text-ink-muted mt-4">
            Delivery history for Telegram and email is shown on the{" "}
            <a href="/dashboard/notifications" className="text-brand-400 underline">
              Notifications
            </a>{" "}
            page. Clients manage their own links and preferences in the client portal.
          </p>
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
