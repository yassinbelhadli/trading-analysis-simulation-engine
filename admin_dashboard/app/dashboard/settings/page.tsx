"use client";

import { useCallback, useEffect, useState } from "react";
import PermissionGuard from "@/components/auth/permission_guard";
import { getSettings, getSettingsSchema, updateSettings } from "@/lib/api";
import type { SettingField } from "@/lib/api";
import { Button, PageHeader } from "@ds/components/ui";

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

type Values = Record<string, unknown>;

function FieldInput({ field, value, onChange }: {
  field: SettingField;
  value: unknown;
  onChange: (v: unknown) => void;
}) {
  const common = "w-full px-3 py-2 rounded-lg border border-line bg-input text-sm text-ink focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500 transition-colors";
  switch (field.type) {
    case "boolean":
      return (
        <button type="button" onClick={() => onChange(!value)}
          className={`w-12 h-6 rounded-full transition-colors ${value ? "bg-brand-500" : "bg-hover"}`}
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

export default function SettingsPage() {
  const [categories, setCategories] = useState<string[]>([]);
  const [groups, setGroups] = useState<Record<string, SettingField[]>>({});
  const [values, setValues] = useState<Values>({});
  const [active, setActive] = useState<string>("appearance");
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [saving, setSaving] = useState(false);

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

  const handleSave = async () => {
    setSaving(true); setError(""); setMsg("");
    try {
      for (const cat of categories) {
        for (const field of groups[cat] || []) {
          if (field.type === "json" && typeof values[field.key] === "string") {
            JSON.parse(values[field.key] as string); // throws if invalid
          }
        }
      }
      // Never submit the masked secret sentinel as a real value. A secret that
      // is still masked means the admin did not type a replacement, so it must
      // be omitted from the payload to keep the stored value unchanged.
      const payload: Values = {};
      for (const cat of categories) {
        for (const field of groups[cat] || []) {
          const v = values[field.key];
          if (field.is_secret && v === "••••••••") continue;
          payload[field.key] = v;
        }
      }
      await updateSettings(payload);
      window.dispatchEvent(new Event("settings-saved"));
      setMsg("Settings saved successfully.");
      setTimeout(() => setMsg(""), 4000);
    } catch (e) {
      setError(e instanceof SyntaxError ? "Invalid JSON in one of the fields." : (e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <PermissionGuard permission="system.settings">
      <div>
        <PageHeader
          title="Settings"
          subtitle="Platform configuration"
          actions={
            <Button onClick={handleSave} loading={saving}>
              {saving ? "Saving..." : "Save Changes"}
            </Button>
          }
        />

        {error && <div className="text-danger text-sm mb-3">{error}</div>}
        {msg && <div className="text-ok text-sm mb-3">{msg}</div>}

        <div className="flex flex-col md:flex-row gap-6">
          <aside className="md:w-52 shrink-0">
            <nav className="flex md:flex-col flex-wrap gap-1">
              {categories.map((cat) => (
                <Button key={cat} variant={active === cat ? "primary" : "ghost"} size="sm"
                  className="justify-start"
                  onClick={() => setActive(cat)}>
                  {CATEGORY_LABELS[cat] || cat}
                </Button>
              ))}
            </nav>
          </aside>

          <div className="flex-1 space-y-4">
            {(groups[active] || []).map((field) => {
              const isSecretMasked = field.is_secret && values[field.key] === "••••••••";
              return (
                <div key={field.key} className="bg-raised border border-line rounded-lg p-4">
                  <div className="flex items-center justify-between gap-4">
                    <div className="flex-1">
                      <label className="block text-sm font-medium mb-1 text-ink">{field.label}</label>
                      {field.help && <p className="text-xs text-ink-muted mb-1">{field.help}</p>}
                    </div>
                    <div className="max-w-xs w-full">
                      <FieldInput field={field} value={values[field.key]} onChange={(v) => setValue(field.key, v)} />
                    </div>
                  </div>
                  {isSecretMasked && (
                    <p className="text-[11px] text-ink-muted mt-2">Stored value hidden. Type a new one to replace it.</p>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </PermissionGuard>
  );
}
