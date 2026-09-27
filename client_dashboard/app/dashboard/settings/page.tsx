"use client";

import { useEffect, useState } from "react";
import {
  getClientSettings,
  updateClientSettings,
  listClientAccounts,
  getAccountTradingMode,
  updateAccountTradingMode,
  type ClientSettings,
  type ClientAccount,
} from "@/lib/api";
import { Notice, type NoticeState } from "@/components/Notice";
import { PageHeader, Card, Button, SelectField, Badge, EmptyState, Skeleton } from "@ds/components/ui";
import { parseApiError } from "@/lib/errors";
import { TIMEZONE_REGIONS, formatUserTime, formatUserDate } from "@/lib/timezone";
import { useLocale } from "@/components/LocaleContext";

/**
 * Client Settings — preferences only.
 *
 * Removed (NOT client-configurable):
 * - Symbols (fixed: XAUUSD, BTCUSD, NASDAQ — product-level config)
 * - Timeframes (engine controls its own multi-timeframe analysis)
 * - Trading Sessions (engine controls session logic via TradingModeConfig)
 * - Risk Mode / Max Risk / Daily Loss (driven by AccountProfile → RiskProfile → TradingMode)
 * - News Filter block times (engine controls T-60/T-30/T-5 via EconomicCalendar)
 *
 * Kept (actual user preferences):
 * - Language, Timezone, Theme
 * - Notifications (email, telegram, per-event toggles on /notifications page)
 * - News Alerts (notification preference only — does NOT control trading)
 * - Account Info (read-only)
 *
 * News Alerts ≠ Economic Calendar Risk Protection.
 * - News Alerts: controls whether the client receives news/calendar notifications.
 * - Economic Calendar Risk Protection: engine-controlled T-60/T-30/T-5 protection,
 *   always active, cannot be disabled by the client.
 */
export default function SettingsPage() {
  const { t } = useLocale();
  const [data, setData] = useState<ClientSettings | null>(null);
  const [error, setError] = useState("");
  const [status, setStatus] = useState<NoticeState>(null);
  const [saving, setSaving] = useState(false);

  const [language, setLanguage] = useState("EN");
  const [timezone, setTimezone] = useState("");
  const [theme, setTheme] = useState("system");
  const [newsAlertsEnabled, setNewsAlertsEnabled] = useState(true);
  const [emailNotif, setEmailNotif] = useState(true);
  const [tgNotif, setTgNotif] = useState(true);
  const [billingCurrency, setBillingCurrency] = useState("USD");

  // Live clock for timezone preview
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, [timezone]);

  // Trading mode state
  const [accounts, setAccounts] = useState<ClientAccount[]>([]);
  const [selectedAccountId, setSelectedAccountId] = useState("");
  const [tradingMode, setTradingMode] = useState("balanced");
  const [tradingModeStatus, setTradingModeStatus] = useState<NoticeState>(null);
  const [tradingModeSaving, setTradingModeSaving] = useState(false);

  useEffect(() => {
    getClientSettings()
      .then((s) => {
        setData(s);
        setLanguage(s.language || "EN");
        setTimezone(s.timezone || "");
        setBillingCurrency(s.billing_currency || "USD");
        const p = s.preferences || {};
        setTheme(p.theme || "system");
        setNewsAlertsEnabled(p.news_alerts_enabled ?? true);
        setEmailNotif(p.email_notifications ?? true);
        setTgNotif(p.telegram_notifications ?? true);
      })
      .catch((e) => setError(parseApiError(e)));

    listClientAccounts()
      .then((r) => {
        const items = r.items || [];
        setAccounts(items);
        if (items.length > 0) {
          const firstId = items[0].id;
          setSelectedAccountId(firstId);
          getAccountTradingMode(firstId)
            .then((m) => setTradingMode(m.trading_mode))
            .catch(() => {});
        }
      })
      .catch(() => {});
  }, []);

  const handleAccountSwitch = (accountId: string) => {
    setSelectedAccountId(accountId);
    setTradingModeStatus(null);
    getAccountTradingMode(accountId)
      .then((m) => setTradingMode(m.trading_mode))
      .catch(() => setTradingMode("balanced"));
  };

  const handleSaveTradingMode = async () => {
    if (!selectedAccountId) return;
    setTradingModeStatus(null);
    setTradingModeSaving(true);
    try {
      await updateAccountTradingMode(selectedAccountId, tradingMode);
      setTradingModeStatus({ ok: true, text: t("settings.saved") });
    } catch (err) {
      setTradingModeStatus({ ok: false, text: err instanceof Error ? err.message : t("settings.saveFailed") });
    } finally {
      setTradingModeSaving(false);
    }
  };

  const handleSave = async () => {
    setStatus(null);
    if (!timezone) {
      setStatus({ ok: false, text: t("settings.selectTimezone") });
      return;
    }
    setSaving(true);
    try {
      await updateClientSettings({
        language,
        timezone,
        billing_currency: billingCurrency,
        preferences: {
          theme,
          news_alerts_enabled: newsAlertsEnabled,
          email_notifications: emailNotif,
          telegram_notifications: tgNotif,
        },
      });
      setStatus({ ok: true, text: t("settings.saved") });
      window.dispatchEvent(new Event("client-settings-saved"));
    } catch (err) {
      setStatus({ ok: false, text: err instanceof Error ? err.message : t("settings.saveFailed") });
    } finally {
      setSaving(false);
    }
  };

  if (error && !data) {
    return <EmptyState icon="alert-triangle" title={t("settings.loadError")} description={error} />;
  }
  if (!data) {
    return (
      <div className="max-w-3xl flex flex-col gap-5">
        <div className="h-8 w-44 rounded bg-hover animate-pulse" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  return (
    <div className="max-w-3xl flex flex-col gap-5">
      <PageHeader title={t("settings.title")} subtitle={t("settings.subtitle")} />

      <Notice state={status} />

      <Card title={t("settings.appearanceLang")} icon="settings">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <SelectField
            label={t("settings.language")}
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
          >
            <option value="EN">English</option>
            <option value="AR">العربية</option>
            <option value="FR">Français</option>
            <option value="ES">Español</option>
          </SelectField>
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-ink-soft">{t("settings.timezone")}</label>
            <select
              value={timezone}
              onChange={(e) => setTimezone(e.target.value)}
              className="w-full h-9 px-3 rounded-lg bg-input border border-line text-sm text-ink focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500 transition-colors"
            >
              <option value="">{t("settings.selectTz")}</option>
              {TIMEZONE_REGIONS.map((region) => (
                <optgroup key={region.region} label={region.region}>
                  {region.timezones.map((tz) => (
                    <option key={tz.iana} value={tz.iana}>
                      {tz.label}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
            {timezone && (
              <div className="mt-2 rounded-lg border border-line bg-raised px-3 py-2 text-sm">
                <div className="text-ink font-medium tabular-nums">{formatUserTime(now, timezone)}</div>
                <div className="text-ink-muted text-xs">{formatUserDate(now, timezone)}</div>
              </div>
            )}
          </div>
          <SelectField
            label={t("settings.theme")}
            value={theme}
            onChange={(e) => setTheme(e.target.value)}
          >
            <option value="system">{t("settings.system")}</option>
            <option value="light">{t("settings.light")}</option>
            <option value="dark">{t("settings.dark")}</option>
          </SelectField>
        </div>
      </Card>

      <Card title={t("settings.billingCurrency")} icon="credit-card">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <SelectField
            label={t("settings.billingCurrency")}
            value={billingCurrency}
            onChange={(e) => setBillingCurrency(e.target.value)}
          >
            <option value="USD">USD — US Dollar ($)</option>
            <option value="EUR">EUR — Euro (€)</option>
            <option value="MAD">MAD — Moroccan Dirham (MAD)</option>
          </SelectField>
          <p className="text-xs text-ink-muted mt-2">
            {t("settings.billingNote")}
          </p>
        </div>
      </Card>

      <Card title={t("settings.newsAlerts")} icon="newspaper">
        <div className="flex flex-col gap-3">
          <label className="flex items-center justify-between gap-3 cursor-pointer">
            <div>
              <span className="text-sm text-ink">{t("settings.newsAlertsLabel")}</span>
              <p className="text-xs text-ink-muted mt-0.5">
                {t("settings.newsAlertsNote")}
              </p>
            </div>
            <input
              type="checkbox"
              checked={newsAlertsEnabled}
              onChange={(e) => setNewsAlertsEnabled(e.target.checked)}
              className="h-4 w-4 accent-brand-500"
            />
          </label>
        </div>
      </Card>

      <Card title={t("settings.notifications")} icon="bell">
        <div className="flex flex-col gap-2.5">
          <ToggleRow label={t("settings.emailNotif")} checked={emailNotif} onChange={setEmailNotif} />
          <ToggleRow label={t("settings.tgNotif")} checked={tgNotif} onChange={setTgNotif} />
          <p className="text-xs text-ink-muted" dangerouslySetInnerHTML={{ __html: t("settings.perEventNote") }} />
        </div>
      </Card>

      <Card title={t("settings.accountInfo")} icon="user">
        <div className="space-y-2 text-sm">
          <Row
            k="Email"
            v={data.email || "—"}
            right={
              <Badge tone={data.email_verified ? "green" : "amber"}>
                {data.email_verified ? t("settings.verified") : t("settings.notVerified")}
              </Badge>
            }
          />
          <Row k={t("settings.tgId")} v={data.telegram_id ? String(data.telegram_id) : t("settings.tgConnected")} />
          <Row k={t("settings.tgUsername")} v={data.telegram_username || "—"} />
        </div>
      </Card>

      <Card title={t("settings.tradingMarkets")} icon="chart">
        <div className="text-sm text-ink-soft">
          <p>{t("settings.marketsNote")}</p>
          <div className="flex flex-wrap gap-2 mt-3">
            <Badge tone="blue">XAUUSD</Badge>
            <Badge tone="blue">BTCUSD</Badge>
            <Badge tone="blue">NASDAQ</Badge>
          </div>
        </div>
      </Card>

      <Card title={t("settings.tradingMode")} icon="shield-check">
        {accounts.length === 0 ? (
          <div className="text-sm text-ink-soft">
            <p>{t("settings.noAccountsMode")}</p>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            <div>
              <label className="text-xs font-medium text-ink-soft mb-1.5 block">{t("settings.selectAccount")}</label>
              <select
                value={selectedAccountId}
                onChange={(e) => handleAccountSwitch(e.target.value)}
                className="w-full h-9 px-3 rounded-lg bg-input border border-line text-sm text-ink focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500 transition-colors"
              >
                {accounts.map((acc) => (
                  <option key={acc.id} value={acc.id}>
                    {acc.name || acc.login || acc.id} ({acc.platform} / {acc.account_type})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-xs font-medium text-ink-soft mb-2 block">{t("settings.mode")}</label>
              <div className="flex flex-col gap-2">
                {(["conservative", "balanced", "aggressive"] as const).map((mode) => {
                  const isSelected = tradingMode === mode;
                  const tones: Record<string, string> = {
                    conservative: isSelected ? "text-ok border-ok/40 bg-ok/10" : "text-ink-soft border-line hover:border-ok/30",
                    balanced: isSelected ? "text-amber-400 border-amber-400/40 bg-amber-400/10" : "text-ink-soft border-line hover:border-amber-400/30",
                    aggressive: isSelected ? "text-danger border-danger/40 bg-danger/10" : "text-ink-soft border-line hover:border-danger/30",
                  };
                  return (
                    <label
                      key={mode}
                      className={`flex items-center gap-3 px-3 py-2.5 rounded-lg border cursor-pointer transition-colors ${tones[mode]}`}
                    >
                      <input
                        type="radio"
                        name="trading-mode"
                        value={mode}
                        checked={isSelected}
                        onChange={() => setTradingMode(mode)}
                        className="h-4 w-4 accent-brand-500"
                      />
                      <div>
                        <span className="text-sm font-medium capitalize">{mode}</span>
                        <span className="text-xs text-ink-muted ml-2">
                          {mode === "conservative" && t("settings.modeConservative")}
                          {mode === "balanced" && t("settings.modeBalanced")}
                          {mode === "aggressive" && t("settings.modeAggressive")}
                        </span>
                      </div>
                    </label>
                  );
                })}
              </div>
            </div>

            {tradingModeStatus && (
              <div
                className={`text-sm px-3 py-2 rounded-lg border ${
                  tradingModeStatus.ok
                    ? "text-ok border-ok/30 bg-ok/10"
                    : "text-danger border-danger/30 bg-danger/10"
                }`}
              >
                {tradingModeStatus.text}
              </div>
            )}

            <div className="flex justify-end">
              <Button
                icon="check"
                onClick={handleSaveTradingMode}
                disabled={tradingModeSaving}
                loading={tradingModeSaving}
              >
                {tradingModeSaving ? t("settings.working") : t("settings.saveTradingMode")}
              </Button>
            </div>
          </div>
        )}
      </Card>

      <div className="flex justify-end">
        <Button icon="check" onClick={handleSave} disabled={saving} loading={saving}>
          {saving ? t("settings.working") : t("settings.saveSettings")}
        </Button>
      </div>
    </div>
  );
}

function ToggleRow({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex items-center justify-between gap-3 cursor-pointer">
      <span className="text-sm text-ink">{label}</span>
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="h-4 w-4 accent-brand-500"
      />
    </label>
  );
}

function Row({ k, v, right }: { k: string; v: string; right?: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-line/60 py-2 last:border-b-0">
      <span className="text-ink-soft">{k}</span>
      <span className="flex items-center gap-2 font-medium text-ink">
        {v}
        {right}
      </span>
    </div>
  );
}
