"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import OwnerPermissionGuard from "@/components/auth/owner_permission_guard";
import { getSettings, getSettingsSchema, updateSettings, sanitizeSettingsPayload } from "@/lib/api";
import type { SettingField } from "@/lib/api";
import { PageHeader, Button, Skeleton } from "@ds/components/ui";
import { Icon, type IconName } from "@ds/components/Icon";
import { TIMEZONE_REGIONS, formatUserTime, formatUserDate } from "@/lib/timezone";

const CATEGORY_LABELS: Record<string, string> = {
  appearance: "Appearance",
  telegram: "Telegram",
  email: "Email",
  trading: "Trading",
  renderer: "Renderer",
  symbols: "Symbols",
  timeframes: "Timeframes",
  sessions: "Sessions",
  news: "News",
  api: "API",
  workers: "Workers",
};

const CATEGORY_ICONS: Record<string, IconName> = {
  appearance: "sparkles",
  telegram: "send",
  email: "mail",
  trading: "chart",
  renderer: "layers",
  symbols: "activity",
  timeframes: "clock",
  sessions: "calendar",
  news: "newspaper",
  api: "link",
  workers: "cpu",
};

/** Pseudo-category for the documented Secrets gap (matrix row 23, status D). */
const SECRETS_HREF = "/dashboard/settings/secrets";

type Values = Record<string, unknown>;

function FieldInput({ field, value, onChange }: {
  field: SettingField;
  value: unknown;
  onChange: (v: unknown) => void;
}) {
  const common = "w-full px-3 py-2 rounded-lg border border-line bg-input text-sm text-ink focus:outline-none focus:border-brand-500";
  switch (field.type) {
    case "boolean":
      return (
        <button type="button" onClick={() => onChange(!value)}
          className={`h-6 w-12 rounded-full transition-colors ${value ? "bg-brand-500" : "bg-hover border border-line"}`}
          aria-pressed={!!value}>
          <span className={`block h-5 w-5 rounded-full bg-white transition-transform ${value ? "translate-x-6" : "translate-x-0.5"}`} />
        </button>
      );
    case "number":
      return (
        <input type="number" className={common} value={value as number | string}
          onChange={(e) => onChange(e.target.value === "" ? "" : Number(e.target.value))} />
      );
    case "select":
      return (
        <select className={common} value={value as string} onChange={(e) => onChange(e.target.value)}>
          {(field.options || []).map((opt) => <option key={opt} value={opt}>{opt}</option>)}
        </select>
      );
    case "color":
      return (
        <div className="flex items-center gap-2">
          <input type="color" className="h-9 w-12 rounded cursor-pointer bg-transparent"
            value={value as string} onChange={(e) => onChange(e.target.value)} />
          <input type="text" className={common} value={value as string} onChange={(e) => onChange(e.target.value)} />
        </div>
      );
    case "password":
      return (
        <input type="password" className={common} placeholder={value === "••••••••" ? "Leave blank to keep current value" : ""}
          value={value === "••••••••" ? "" : (value as string)} onChange={(e) => onChange(e.target.value)} />
      );
    case "textarea":
      return (
        <textarea className={`${common} min-h-[90px] font-mono text-xs`} value={value as string}
          onChange={(e) => onChange(e.target.value)} />
      );
    case "json":
      return (
        <textarea className={`${common} min-h-[90px] font-mono text-xs`}
          value={typeof value === "string" ? value : JSON.stringify(value, null, 2)}
          onChange={(e) => {
            try { onChange(JSON.parse(e.target.value)); } catch { onChange(e.target.value); }
          }} />
      );
    default:
      return (
        <input type="text" className={common} value={value as string} onChange={(e) => onChange(e.target.value)} />
      );
  }
}

/**
 * Safe Configuration (OQ-3). Secret/sensitive keys are excluded from editing
 * and can never be sent to PUT /settings:
 *  1. The schema `is_secret` flag marks masked secret fields.
 *  2. `sanitizeSettingsPayload` (lib/api.ts) applies a code-level deny-list
 *     and drops `••••••••` masked placeholders before any write.
 * This portal NEVER displays or writes decrypted secrets.
 */
export default function SettingsPage() {
  const [categories, setCategories] = useState<string[]>([]);
  const [groups, setGroups] = useState<Record<string, SettingField[]>>({});
  const [values, setValues] = useState<Values>({});
  const [active, setActive] = useState<string>("appearance");
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [saving, setSaving] = useState(false);

  // Timezone state
  const [timezone, setTimezone] = useState("");
  const [tzLoading, setTzLoading] = useState(true);
  const [tzSaving, setTzSaving] = useState(false);
  const [tzMsg, setTzMsg] = useState("");
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, [timezone]);

  // Load timezone from settings on mount
  useEffect(() => {
    getSettings()
      .then((data) => {
        const tz = (data.settings as Record<string, unknown>)["timezone"];
        setTimezone(typeof tz === "string" ? tz : "");
      })
      .catch(() => {})
      .finally(() => setTzLoading(false));
  }, []);

  const handleSaveTimezone = async () => {
    if (!timezone) return;
    setTzSaving(true);
    setTzMsg("");
    try {
      await updateSettings({ timezone });
      setTzMsg("Timezone saved.");
      setTimeout(() => setTzMsg(""), 4000);
    } catch (e) {
      setTzMsg((e as Error).message);
    } finally {
      setTzSaving(false);
    }
  };

  const load = useCallback(async () => {
    try {
      const [schema, data] = await Promise.all([getSettingsSchema(), getSettings()]);
      setCategories(schema.categories);
      setGroups(schema.groups);
      setValues(data.settings);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const setValue = (key: string, v: unknown) => setValues((prev) => ({ ...prev, [key]: v }));

  const activeFields = (groups[active] || []).filter((f) => !f.is_secret);

  const handleSave = async () => {
    setSaving(true); setError(""); setMsg("");
    try {
      for (const cat of categories) {
        for (const field of groups[cat] || []) {
          if (field.is_secret) continue;
          if (field.type === "json" && typeof values[field.key] === "string") {
            JSON.parse(values[field.key] as string); // throws if invalid
          }
        }
      }
      const safe = sanitizeSettingsPayload(values, groups);
      if (Object.keys(safe).length === 0) {
        setMsg("No editable (non-secret) settings to save.");
        setTimeout(() => setMsg(""), 4000);
        setSaving(false);
        return;
      }
      await updateSettings(safe);
      window.dispatchEvent(new Event("settings-saved"));
      setMsg("Safe settings saved successfully.");
      setTimeout(() => setMsg(""), 4000);
    } catch (e) {
      setError(e instanceof SyntaxError ? "Invalid JSON in one of the fields." : (e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const navCategories = categories;

  return (
    <OwnerPermissionGuard permission="system.settings">
      <div className="flex flex-col gap-5 max-w-6xl">
        <PageHeader
          title="Safe Settings"
          subtitle="Configuration control plane — non-secret settings only. Secret values are masked and excluded from editing."
          actions={
            <Button onClick={handleSave} loading={saving} icon="check">
              {saving ? "Saving..." : "Save Changes"}
            </Button>
          }
        />

        {error && (
          <div className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
            {error}
          </div>
        )}
        {msg && (
          <div className="rounded-lg border border-ok/30 bg-ok/10 px-3 py-2 text-sm text-ok">
            {msg}
          </div>
        )}

        <div className="bg-raised border border-line rounded-xl p-4">
          <h3 className="text-sm font-medium text-ink mb-3">Timezone</h3>
          {tzLoading ? (
            <Skeleton className="h-9 w-full max-w-xs" />
          ) : (
            <div className="flex flex-col gap-2 max-w-xs">
              <select
                value={timezone}
                onChange={(e) => setTimezone(e.target.value)}
                className="w-full h-9 px-3 rounded-lg bg-input border border-line text-sm text-ink focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500 transition-colors"
              >
                <option value="">Select timezone...</option>
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
                <div className="rounded-lg border border-line bg-surface px-3 py-2 text-sm">
                  <div className="text-ink font-medium tabular-nums">{formatUserTime(now, timezone)}</div>
                  <div className="text-ink-muted text-xs">{formatUserDate(now, timezone)}</div>
                </div>
              )}
              {tzMsg && (
                <p className="text-xs text-ok">{tzMsg}</p>
              )}
              <div className="flex justify-end">
                <Button onClick={handleSaveTimezone} loading={tzSaving} icon="check" size="sm">
                  {tzSaving ? "Saving..." : "Save Timezone"}
                </Button>
              </div>
            </div>
          )}
        </div>

        {!categories.length && !error ? (
          <div className="flex flex-col md:flex-row gap-5">
            <Skeleton className="h-64 w-52 rounded-xl" />
            <div className="flex-1 space-y-3">
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} className="h-20 rounded-xl" />
              ))}
            </div>
          </div>
        ) : (
          <div className="flex flex-col md:flex-row gap-5">
            <aside className="md:w-52 shrink-0">
              <nav className="flex md:flex-col flex-wrap gap-1">
                {navCategories.map((cat) => {
                  const hasVisible = (groups[cat] || []).some((f) => !f.is_secret);
                  const icon = CATEGORY_ICONS[cat] || "settings";
                  return (
                    <button
                      key={cat}
                      onClick={() => setActive(cat)}
                      className={`flex items-center gap-2 px-3 py-2 text-sm rounded-lg text-left transition-colors ${
                        active === cat
                          ? "bg-brand-tint text-brand-400 font-medium"
                          : "text-ink-soft hover:bg-hover hover:text-ink"
                      } ${hasVisible ? "" : "opacity-50"}`}
                    >
                      <Icon name={icon} className="h-4 w-4 shrink-0" />
                      {CATEGORY_LABELS[cat] || cat}
                    </button>
                  );
                })}
                <Link
                  href={SECRETS_HREF}
                  className="flex items-center gap-2 px-3 py-2 text-sm rounded-lg text-left transition-colors text-ink-soft hover:bg-hover hover:text-ink"
                >
                  <Icon name="lock" className="h-4 w-4 shrink-0" />
                  Secrets
                  <span className="ml-auto rounded-full bg-warn/10 border border-warn/30 px-1.5 py-px text-[9px] font-mono text-warn">
                    gap
                  </span>
                </Link>
              </nav>
            </aside>

            <div className="flex-1 space-y-4">
              {activeFields.length === 0 ? (
                <div className="bg-raised border border-line rounded-xl p-4 text-xs text-ink-muted">
                  This category contains only secret/sensitive keys. They are intentionally not editable here.
                </div>
              ) : (
                activeFields.map((field) => {
                  const isMasked = values[field.key] === "••••••••";
                  return (
                    <div key={field.key} className="bg-raised border border-line rounded-xl p-4">
                      <div className="flex items-center justify-between gap-4">
                        <div className="flex-1">
                          <label className="block text-sm font-medium text-ink mb-1">{field.label}</label>
                          {field.help && <p className="text-xs text-ink-muted mb-1">{field.help}</p>}
                        </div>
                        <div className="max-w-xs w-full">
                          <FieldInput field={field} value={values[field.key]} onChange={(v) => setValue(field.key, v)} />
                        </div>
                      </div>
                      {isMasked && (
                        <p className="text-[11px] text-ink-muted mt-2">
                          Secret value hidden. This field is read-only here — manage secrets in a dedicated secure channel.
                        </p>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          </div>
        )}
      </div>
    </OwnerPermissionGuard>
  );
}
