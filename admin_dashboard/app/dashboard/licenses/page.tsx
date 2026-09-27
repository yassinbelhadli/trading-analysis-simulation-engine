"use client";

import { useEffect, useState, useCallback } from "react";
import Modal from "@/components/Modal";
import PermissionGuard from "@/components/auth/permission_guard";
import { listUsers, listPlans, listLicenses, createLicense, licenseAction, UserItem, LicenseItem } from "@/lib/api";
import { Badge, Button, Card, PageHeader, SelectField, TextField } from "@ds/components/ui";
import { ConfirmDialog } from "@ds/components/Modal";
import { hasPermission } from "@/lib/auth";

export default function LicensesPage() {
  const [licenses, setLicenses] = useState<LicenseItem[]>([]);
  const [plans, setPlans] = useState<any[]>([]);
  const [users, setUsers] = useState<UserItem[]>([]);
  const [error, setError] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [formUserId, setFormUserId] = useState("");
  const [formPlan, setFormPlan] = useState("starter");
  const [formDays, setFormDays] = useState("30");
  const [formAccounts, setFormAccounts] = useState("1");
  const [saving, setSaving] = useState(false);
  const [deactivateId, setDeactivateId] = useState<string | null>(null);
  const [actionBusy, setActionBusy] = useState(false);

  const canCreate = hasPermission("licenses.create");
  const canUpdate = hasPermission("licenses.update");

  const load = useCallback(async () => {
    try {
      const [licRes, planRes, userRes] = await Promise.all([
        listLicenses(),
        listPlans(),
        listUsers("?limit=200"),
      ]);
      setLicenses(licRes.items);
      setPlans(planRes.items);
      setUsers(userRes.items);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleAction = async (id: string, action: string) => {
    setActionBusy(true);
    try {
      await licenseAction(id, action);
      setDeactivateId(null);
      load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setActionBusy(false);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await createLicense({
        user_id: formUserId,
        plan: formPlan,
        max_accounts: parseInt(formAccounts),
        expires_in_days: formDays ? parseInt(formDays) : null,
      });
      setShowCreate(false);
      load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const planInfo = (name: string) => plans.find((p) => p.id === name);

  return (
    <PermissionGuard permission="licenses.read">
      <div>
        <PageHeader
          title="Licenses"
          subtitle="Client EA licenses, plans and binding status."
          actions={
            canCreate && (
            <Button icon="plus" onClick={() => setShowCreate(true)}>
              Create License
            </Button>
            )
          }
        />

        {error && <div className="text-danger text-sm mb-3">{error}</div>}

        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {licenses.length === 0 && !error && (
            <div className="col-span-full text-center py-12 text-ink-muted text-sm">
              <p>No data yet.</p>
              <p className="mt-1">Create your first license to get started.</p>
            </div>
          )}
          {licenses.map((lic) => {
            const plan = planInfo(lic.plan);
            return (
              <Card key={lic.id} className="flex flex-col">
                <div className="flex items-center justify-between mb-2">
                  <div className="font-mono text-xs truncate max-w-[180px]" title={lic.license_key}>
                    {lic.license_key}
                  </div>
                  <Badge tone={lic.status === "active" ? "green" : lic.status === "revoked" ? "red" : "gray"}>
                    {lic.status}
                  </Badge>
                </div>
                <div className="flex items-center gap-2 mb-2">
                  <Badge tone={lic.plan === "enterprise" || lic.plan === "lifetime" ? "blue" : lic.plan === "professional" ? "green" : "gray"}>
                    {plan?.name || lic.plan}
                  </Badge>
                  <span className="text-xs text-ink-muted">{lic.max_accounts} accounts</span>
                </div>
                <div className="text-[10px] text-ink-muted space-y-0.5 mb-3">
                  <div>User: {lic.telegram_username || lic.user_id?.slice(0, 8) || "—"}</div>
                  <div>Expires: {lic.expires_at ? new Date(lic.expires_at).toLocaleDateString() : "Never"}</div>
                  {lic.bound_account_id && <div>Bound: {lic.bound_account_id.slice(0, 8)}...</div>}
                  <div>Created: {lic.created_at ? new Date(lic.created_at).toLocaleDateString() : "—"}</div>
                </div>
                {plan?.features && (
                  <div className="flex flex-wrap gap-1 mb-3">
                    {Object.entries(plan.features).map(([key, val]) => (
                      <span
                        key={key}
                        className={`text-[9px] px-1.5 py-0.5 rounded-full border ${
                          val
                            ? "bg-brand-tint border-brand-500/30 text-brand-400"
                            : "bg-hover border-line text-ink-muted"
                        }`}
                      >
                        {key.replace(/_/g, " ")}
                      </span>
                    ))}
                  </div>
                )}
                <div className="flex flex-wrap gap-1 mt-auto">
                  {canUpdate && (
                    <>
                      {lic.status === "active" ? (
                        <Button size="sm" variant="secondary" onClick={() => setDeactivateId(lic.id)}>
                          Deactivate
                        </Button>
                      ) : (
                        <Button size="sm" variant="success" icon="play" onClick={() => handleAction(lic.id, "activate")}>
                          Activate
                        </Button>
                      )}
                      {lic.bound_account_id && (
                        <Button size="sm" variant="ghost" onClick={() => handleAction(lic.id, "unbind")}>
                          Unbind
                        </Button>
                      )}
                      <Button size="sm" variant="ghost" onClick={() => handleAction(lic.id, "reset")}>
                        Reset
                      </Button>
                    </>
                  )}
                </div>
              </Card>
            );
          })}
        </div>

        <Modal open={showCreate} onClose={() => setShowCreate(false)} title="Create License">
          <form onSubmit={handleCreate} className="flex flex-col gap-4">
            <SelectField label="User" value={formUserId} onChange={(e) => setFormUserId(e.target.value)} required>
              <option value="">Select user</option>
              {users.map((u) => (
                <option key={u.id} value={u.id}>{u.email || u.id.slice(0, 8)}</option>
              ))}
            </SelectField>
            <SelectField label="Plan" value={formPlan} onChange={(e) => setFormPlan(e.target.value)}>
              {plans.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </SelectField>
            <div className="grid grid-cols-2 gap-3">
              <TextField
                label="Max Accounts"
                type="number"
                placeholder="e.g. 1"
                value={formAccounts}
                onChange={(e) => setFormAccounts(e.target.value)}
              />
              <TextField
                label="Expires In (Days)"
                type="number"
                placeholder="blank = never"
                value={formDays}
                onChange={(e) => setFormDays(e.target.value)}
              />
            </div>
            <div className="flex justify-end gap-2 mt-2 pt-2 border-t border-line">
              <Button type="button" variant="ghost" onClick={() => setShowCreate(false)}>
                Cancel
              </Button>
              <Button type="submit" loading={saving}>
                {saving ? "Creating..." : "Create"}
              </Button>
            </div>
          </form>
        </Modal>

        <ConfirmDialog
          open={!!deactivateId}
          title="Deactivate License"
          description="This will deactivate the license immediately. The user's EA will stop working until the license is reactivated."
          confirmLabel="Deactivate"
          tone="danger"
          loading={actionBusy}
          onConfirm={() => deactivateId && handleAction(deactivateId, "deactivate")}
          onCancel={() => setDeactivateId(null)}
        />
      </div>
    </PermissionGuard>
  );
}
