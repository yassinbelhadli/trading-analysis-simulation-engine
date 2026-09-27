"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  getTelegramStatus,
  getTelegramLoginUrl,
  disconnectTelegram,
  updateTelegramPreferences,
  testTelegram,
  type TelegramStatus,
} from "@/lib/api";
import { Notice, type NoticeState } from "@/components/Notice";
import {
  PageHeader,
  Card,
  Button,
  StatusPill,
  EmptyState,
  Skeleton,
  SelectField,
  ToggleRow,
} from "@ds/components/ui";
import { Icon, type IconName } from "@ds/components/Icon";
import { ConfirmDialog } from "@ds/components/Modal";
import { useLocale } from "@/components/LocaleContext";

const NOTIF_LABELS: [string, string][] = [
  ["signals", "telegram.notif.signals"],
  ["filled", "telegram.notif.filled"],
  ["tp", "telegram.notif.tp"],
  ["sl", "telegram.notif.sl"],
  ["news", "telegram.notif.news"],
  ["weekly_report", "telegram.notif.weekly_report"],
  ["monthly_report", "telegram.notif.monthly_report"],
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

const LANGS = [
  { v: "EN", label: "English" },
  { v: "AR", label: "العربية" },
  { v: "FR", label: "Français" },
  { v: "ES", label: "Español" },
];

const ERROR_REASONS: Record<string, string> = {
  missing_params: "telegram.error.missing_params",
  exchange_failed: "telegram.error.exchange_failed",
  invalid_state: "telegram.error.invalid_state",
  network_error: "telegram.error.network_error",
  code_verifier_missing: "telegram.error.code_verifier_missing",
  telegram_auth_failed: "telegram.error.telegram_auth_failed",
  missing_code: "telegram.error.missing_code",
  invalid_code: "telegram.error.invalid_code",
  token_exchange_failed: "telegram.error.token_exchange_failed",
  id_token_missing: "telegram.error.id_token_missing",
  invalid_algorithm: "telegram.error.invalid_algorithm",
  jwt_decode_failed: "telegram.error.jwt_decode_failed",
  id_token_invalid: "telegram.error.id_token_invalid",
  jwt_expired: "telegram.error.jwt_expired",
  jwt_invalid_audience: "telegram.error.jwt_invalid_audience",
  jwt_invalid_issuer: "telegram.error.jwt_invalid_issuer",
  telegram_id_missing: "telegram.error.telegram_id_missing",
  db_error: "telegram.error.db_error",
  connect_error: "telegram.error.connect_error",
};

/* ------------------------------------------------------------------ */
/*  Outer page — wraps inner in Suspense for useSearchParams            */
/* ------------------------------------------------------------------ */

export default function TelegramPage() {
  return (
    <Suspense
      fallback={
        <div className="max-w-2xl flex flex-col gap-5">
          <div className="h-8 w-44 rounded bg-hover animate-pulse" />
          <Skeleton className="h-48 w-full" />
          <Skeleton className="h-56 w-full" />
        </div>
      }
    >
      <TelegramPageInner />
    </Suspense>
  );
}

/* ------------------------------------------------------------------ */
/*  Inner page component — uses useSearchParams                         */
/* ------------------------------------------------------------------ */

function TelegramPageInner() {
  const searchParams = useSearchParams();
  const { t } = useLocale();
  const [data, setData] = useState<TelegramStatus | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState<NoticeState>(null);

  // Connection actions
  const [connecting, setConnecting] = useState(false);
  const [testSending, setTestSending] = useState(false);
  const [disconnectOpen, setDisconnectOpen] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);

  // Preferences
  const [notifications, setNotifications] = useState<Record<string, boolean>>({});
  const [language, setLanguage] = useState("EN");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const s = await getTelegramStatus();
      setData(s);
      setError("");
      setNotifications(s.notifications || {});
      setLanguage(s.language || "EN");
    } catch (e) {
      setError(e instanceof Error ? e.message : t("telegram.loadError"));
    }
  }, [t]);

  // Load status on mount
  useEffect(() => {
    load();
  }, [load]);

  // Handle redirect callback result from URL params
  useEffect(() => {
    const tg = searchParams.get("telegram");
    const reason = searchParams.get("reason");
    if (tg === "connected") {
      setNotice({ ok: true, text: t("telegram.connectedSuccess") });
      // Re-fetch status to reflect the new connection
      load();
    } else if (tg === "error") {
      const reasonKey = ERROR_REASONS[reason || ""];
      const msg = reasonKey
        ? t(reasonKey)
        : t("telegram.authFailed", { reason: reason || "unknown error" });
      setNotice({ ok: false, text: msg });
    }
  }, [searchParams, load, t]);

  /* -- OIDC Connect ------------------------------------------------ */
  const handleConnect = async () => {
    setNotice(null);
    setConnecting(true);
    try {
      const res = await getTelegramLoginUrl();
      // Redirect the browser to Telegram's official authorization page
      window.location.href = res.url;
    } catch (err) {
      setNotice({
        ok: false,
        text: err instanceof Error ? err.message : t("telegram.connectFailed"),
      });
      setConnecting(false);
    }
  };

  /* -- Actions ------------------------------------------------------ */
  const handleSavePrefs = async () => {
    setNotice(null);
    setSaving(true);
    try {
      const res = await updateTelegramPreferences({ notifications, language });
      setData((d) => (d ? { ...d, notifications: res.notifications, language: res.language } : d));
      setNotice({ ok: true, text: t("telegram.prefsSaved") });
    } catch (err) {
      setNotice({ ok: false, text: err instanceof Error ? err.message : t("telegram.saveFailed") });
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    setNotice(null);
    setTestSending(true);
    try {
      const res = await testTelegram();
      setNotice({ ok: true, text: res.message });
    } catch (err) {
      setNotice({ ok: false, text: err instanceof Error ? err.message : t("telegram.testFailed") });
    } finally {
      setTestSending(false);
    }
  };

  const handleDisconnect = async () => {
    setNotice(null);
    setDisconnecting(true);
    try {
      await disconnectTelegram();
      setDisconnectOpen(false);
      setNotice({ ok: true, text: t("telegram.disconnected") });
      await load();
    } catch (err) {
      setNotice({ ok: false, text: err instanceof Error ? err.message : t("telegram.disconnectFailed") });
    } finally {
      setDisconnecting(false);
    }
  };

  /* -- Render ------------------------------------------------------- */
  if (error && !data) {
    return <EmptyState icon="alert-triangle" title={t("telegram.loadError")} description={error} />;
  }
  if (!data) {
    return (
      <div className="max-w-2xl flex flex-col gap-5">
        <div className="h-8 w-44 rounded bg-hover animate-pulse" />
        <Skeleton className="h-48 w-full" />
        <Skeleton className="h-56 w-full" />
      </div>
    );
  }

  return (
    <div className="max-w-2xl flex flex-col gap-5">
      <PageHeader
        title={t("telegram.title")}
        subtitle={t("telegram.subtitle")}
      />

      <Notice state={notice} />

      {/* -- Connection Status Card ---------------------------------- */}
      <Card
        title={t("telegram.connStatus")}
        icon="send"
        actions={
          <StatusPill status={data.connected ? "active" : connecting ? "pending" : "inactive"}>
            {data.connected ? t("telegram.connected") : connecting ? t("telegram.connecting") : t("telegram.notConnected")}
          </StatusPill>
        }
      >
        {data.connected ? (
          /* -- Connected state ------------------------------------- */
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-3 text-sm">
              <Info k={t("telegram.bot")} v={`@${data.bot_username}`} />
              <Info k={t("telegram.tgId")} v={data.chat_id ? String(data.chat_id) : "—"} />
              <Info k={t("telegram.tgUsername")} v={data.telegram_username ? `@${data.telegram_username}` : "—"} />
              <Info k={t("telegram.ifLanguage")} v={data.language || "EN"} />
            </div>
            <div className="mt-4 flex flex-wrap items-center gap-2.5">
              <Button variant="secondary" size="sm" icon="send" onClick={handleTest} loading={testSending}>
                {testSending ? t("telegram.sending") : t("telegram.sendTest")}
              </Button>
              <Button variant="danger" size="sm" icon="plug" onClick={() => setDisconnectOpen(true)}>
                {t("telegram.disconnect")}
              </Button>
            </div>
          </>
        ) : connecting ? (
          /* -- Redirecting state ----------------------------------- */
          <div className="flex items-center gap-3 text-sm text-ink-soft py-4">
            <div className="h-5 w-5 border-2 border-brand-400 border-t-transparent rounded-full animate-spin" />
            <span>{t("telegram.redirecting")}</span>
          </div>
        ) : (
          /* -- Not connected state — OIDC redirect button ---------- */
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-3 text-sm">
              <Info k={t("telegram.bot")} v={`@${data.bot_username}`} />
              <Info k={t("telegram.tgId")} v="—" />
              <Info k={t("telegram.tgUsername")} v="—" />
              <Info k={t("telegram.ifLanguage")} v={data.language || "EN"} />
            </div>

            <div className="mt-4 rounded-lg border border-line bg-input p-3 text-sm text-ink-soft">
              <p className="flex items-start gap-2">
                <Icon name="info" className="h-4 w-4 text-ink-muted mt-0.5 shrink-0" />
                <span>
                  {t("telegram.oidcNote")}
                </span>
              </p>
            </div>

            <div className="mt-4">
              <Button
                variant="primary"
                size="sm"
                icon="send"
                onClick={handleConnect}
                loading={connecting}
              >
                {connecting ? t("telegram.redirecting") : t("telegram.connectBtn")}
              </Button>
            </div>
          </>
        )}
      </Card>

      {/* -- Notification Preferences Card --------------------------- */}
      <Card
        title={t("telegram.prefsTitle")}
        icon="bell"
        subtitle={data.connected ? undefined : t("telegram.prefsConnectNote")}
      >
        <div className="flex flex-col gap-2.5">
          {NOTIF_LABELS.map(([key, labelKey]) => (
            <ToggleRow
              key={key}
              label={t(labelKey)}
              icon={NOTIF_ICONS[key]}
              checked={!!notifications[key]}
              disabled={!data.connected}
              onChange={(v) => setNotifications({ ...notifications, [key]: v })}
            />
          ))}
        </div>
        <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
          <SelectField label={t("telegram.tgLanguage")} value={language} onChange={(e) => setLanguage(e.target.value)} disabled={!data.connected}>
            {LANGS.map((l) => (
              <option key={l.v} value={l.v}>
                {l.label}
              </option>
            ))}
          </SelectField>
        </div>
        <div className="mt-4 flex justify-end">
          <Button icon="check" onClick={handleSavePrefs} loading={saving} disabled={!data.connected}>
            {saving ? t("telegram.saving") : t("telegram.savePrefs")}
          </Button>
        </div>
      </Card>

      {/* -- Disconnect Confirmation Dialog -------------------------- */}
      <ConfirmDialog
        open={disconnectOpen}
        title={t("telegram.disconnectTitle")}
        description={t("telegram.disconnectDesc")}
        confirmLabel={t("telegram.disconnectConfirm")}
        cancelLabel={t("support.cancel")}
        tone="danger"
        loading={disconnecting}
        onConfirm={handleDisconnect}
        onCancel={() => setDisconnectOpen(false)}
      />
    </div>
  );
}

/* -- Info row helper ------------------------------------------------- */
function Info({ k, v }: { k: string; v: string }) {
  return (
    <div>
      <div className="text-xs text-ink-muted">{k}</div>
      <div className="mt-0.5 text-ink">{v}</div>
    </div>
  );
}
