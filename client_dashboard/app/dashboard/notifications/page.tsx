"use client";

import { useEffect, useState } from "react";
import { getClientSettings, updateClientSettings, type ClientSettings } from "@/lib/api";
import { Notice, type NoticeState } from "@/components/Notice";
import { PageHeader, Card, Button, Badge, EmptyState, Skeleton, ToggleRow } from "@ds/components/ui";
import { type IconName } from "@ds/components/Icon";
import { useLocale } from "@/components/LocaleContext";

const NOTIF_LABELS: [string, string][] = [
  ["signals", "notifications.signals"],
  ["filled", "notifications.filled"],
  ["tp", "notifications.tp"],
  ["sl", "notifications.sl"],
  ["news", "notifications.news"],
  ["weekly_report", "notifications.weekly"],
  ["monthly_report", "notifications.monthly"],
];

const NOTIF_ICONS: Record<string, IconName> = {
  signals: "activity",
  filled: "play",
  tp: "check-circle",
  sl: "x-circle",
  news: "newspaper",
  weekly_report: "calendar",
  monthly_report: "megaphone",
};

export default function NotificationsPage() {
  const { t } = useLocale();
  const [data, setData] = useState<ClientSettings | null>(null);
  const [error, setError] = useState("");
  const [status, setStatus] = useState<NoticeState>(null);
  const [saving, setSaving] = useState(false);

  const [notifications, setNotifications] = useState<Record<string, boolean>>({});
  const [emailNotif, setEmailNotif] = useState(true);
  const [tgNotif, setTgNotif] = useState(true);

  useEffect(() => {
    getClientSettings()
      .then((s) => {
        setData(s);
        const p = s.preferences || {};
        setNotifications(p.notifications || {});
        setEmailNotif(p.email_notifications ?? true);
        setTgNotif(p.telegram_notifications ?? true);
      })
      .catch((e) => setError(e.message));
  }, []);

  const handleSave = async () => {
    setStatus(null);
    setSaving(true);
    try {
      await updateClientSettings({
        preferences: { notifications, email_notifications: emailNotif, telegram_notifications: tgNotif },
      });
      setStatus({ ok: true, text: t("notifications.saved") });
    } catch (err) {
      setStatus({ ok: false, text: err instanceof Error ? err.message : t("notifications.saveFailed") });
    } finally {
      setSaving(false);
    }
  };

  if (error && !data) {
    return <EmptyState icon="alert-triangle" title={t("notifications.loadError")} description={error} />;
  }
  if (!data) {
    return (
      <div className="max-w-2xl flex flex-col gap-5">
        <div className="h-8 w-56 rounded bg-hover animate-pulse" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-72 w-full" />
      </div>
    );
  }

  const enabledCount = Object.values(notifications).filter(Boolean).length;

  return (
    <div className="max-w-2xl flex flex-col gap-5">
      <PageHeader title={t("notifications.title")} subtitle={t("notifications.subtitle")} />

      <Notice state={status} />

      <Card title={t("notifications.channels")} icon="send">
        <div className="flex flex-col gap-2.5">
          <ToggleRow
            label={t("notifications.email")}
            checked={emailNotif}
            onChange={setEmailNotif}
            icon="mail"
          />
          <ToggleRow
            label={t("notifications.telegram")}
            checked={tgNotif}
            onChange={setTgNotif}
            icon="send"
          />
        </div>
      </Card>

      <Card
        title={t("notifications.events")}
        icon="bell"
        actions={<Badge tone={enabledCount > 0 ? "green" : "gray"}>{t("notifications.enabled", { n: enabledCount })}</Badge>}
      >
        <div className="flex flex-col gap-2.5">
          {NOTIF_LABELS.map(([key, labelKey]) => (
            <ToggleRow
              key={key}
              label={t(labelKey)}
              icon={NOTIF_ICONS[key]}
              checked={!!notifications[key]}
              onChange={(v) => setNotifications({ ...notifications, [key]: v })}
            />
          ))}
        </div>
        <p className="text-xs text-ink-muted mt-4">
          {t("notifications.storedNote")}
        </p>
      </Card>

      <div className="flex justify-end">
        <Button icon="check" onClick={handleSave} disabled={saving} loading={saving}>
          {saving ? t("notifications.saving") : t("notifications.save")}
        </Button>
      </div>
    </div>
  );
}
