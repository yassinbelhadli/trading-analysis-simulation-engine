"use client";

import { useCallback, useEffect, useState } from "react";
import OwnerPermissionGuard from "@/components/auth/owner_permission_guard";
import {
  getSettingsSchema,
  getSettings,
  updateSettings,
  sanitizeSettingsPayload,
  type SettingField,
} from "@/lib/api";
import {
  PageHeader,
  Card,
  Badge,
  Button,
  Skeleton,
  EmptyState,
} from "@ds/components/ui";
import { Icon } from "@ds/components/Icon";

/**
 * Secrets — secure credential management.
 *
 * Values are NEVER returned by the API (masked server-side) and NEVER stored
 * in the browser. The page lists the schema's `is_secret` fields with their
 * configured/present state, and lets the owner set a NEW value (write-only).
 * The client-side deny-list + sanitizer in lib/api.ts block every known
 * secret key from being echoed or misrouted.
 */
export default function SecretsPage() {
  const [fields, setFields] = useState<{ group: string; field: SettingField; configured: boolean }[] | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setError("");
    try {
      const [schema, current] = await Promise.all([getSettingsSchema(), getSettings()]);
      const configured = current.settings as Record<string, unknown>;

      const rows: { group: string; field: SettingField; configured: boolean }[] = [];
      for (const [group, fs] of Object.entries(schema.groups)) {
        for (const f of fs) {
          if (!f.is_secret) continue;
          const key = f.key;
          const present = key in configured && configured[key] !== null && configured[key] !== "";
          rows.push({ group, field: f, configured: present });
        }
      }
      rows.sort((a, b) => a.group.localeCompare(b.group) || a.field.key.localeCompare(b.field.key));
      setFields(rows);
      setValues({});
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load secrets schema");
      setFields([]);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleSave = async (field: SettingField, newValue: string) => {
    setNotice("");
    setError("");
    setSaving(true);
    try {
      const schemaRes = await getSettingsSchema();
      const safe = sanitizeSettingsPayload({ [field.key]: newValue }, schemaRes.groups);
      if (!(field.key in safe)) {
        setError(`Key "${field.key}" is deny-listed and cannot be updated here.`);
        return;
      }
      const res = await updateSettings(safe);
      setNotice(`"${field.label}" updated.`);
      setValues((v) => ({ ...v, [field.key]: "" }));
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Update failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <OwnerPermissionGuard permission="system.settings">
      <div className="flex flex-col gap-5 max-w-6xl">
        <PageHeader
          title="Secrets"
          subtitle="Credential settings. Values are write-only — they are never displayed and never leave this page unencrypted."
        />

        {error && (
          <div className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
            {error}
          </div>
        )}
        {notice && (
          <div className="rounded-lg border border-ok/30 bg-ok/10 px-3 py-2 text-sm text-ok">
            {notice}
          </div>
        )}

        {!fields ? (
          <div className="flex flex-col gap-3">
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-20 w-full" />
          </div>
        ) : fields.length === 0 ? (
          <Card title="Secrets" icon="key">
            <EmptyState
              icon="key"
              title="No secret settings defined"
              description="The settings schema does not declare any is_secret fields yet."
            />
          </Card>
        ) : (
          <div className="flex flex-col gap-4">
            {fields.map(({ group, field, configured }) => (
              <Card key={field.key} icon="key" title={`${field.label}`} subtitle={`${group} · ${field.key}`}>
                <div className="flex flex-col sm:flex-row sm:items-end gap-3">
                  <div className="flex-1">
                    <div className="mb-1.5 flex items-center gap-2">
                      <Badge tone={configured ? "green" : "amber"}>
                        {configured ? "Configured" : "Not set"}
                      </Badge>
                      {field.help && <span className="text-xs text-ink-muted">{field.help}</span>}
                    </div>
                    <input
                      type="password"
                      autoComplete="new-password"
                      placeholder={configured ? "Set a new value…" : "Set value…"}
                      value={values[field.key] ?? ""}
                      onChange={(e) => setValues((v) => ({ ...v, [field.key]: e.target.value }))}
                      className="h-9 w-full rounded-lg border border-line bg-input px-3 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500 transition-colors"
                    />
                  </div>
                  <Button
                    variant="secondary"
                    disabled={saving || !(values[field.key] ?? "").trim()}
                    onClick={() => handleSave(field, (values[field.key] ?? "").trim())}
                  >
                    Update
                  </Button>
                </div>
              </Card>
            ))}

            <div className="rounded-xl border border-line bg-raised px-5 py-4 text-xs text-ink-muted">
              <div className="flex items-start gap-2">
                <Icon name="shield" className="h-4 w-4 mt-0.5 shrink-0" />
                <p>
                  Secrets are stored encrypted at rest (ENCRYPTION_KEY) and masked by the API on
                  every read. The dashboard never holds them in memory beyond the update request.
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
    </OwnerPermissionGuard>
  );
}
