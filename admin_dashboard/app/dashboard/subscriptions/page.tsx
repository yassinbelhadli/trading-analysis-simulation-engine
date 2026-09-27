"use client";

import { useEffect, useState, useCallback } from "react";
import Modal from "@/components/Modal";
import PermissionGuard from "@/components/auth/permission_guard";
import { listPlans, listSubscriptions, cancelSubscription, updatePlan, restoreDefaultPlans } from "@/lib/api";
import { Badge, Button, Card, PageHeader, Table, Td, TextField } from "@ds/components/ui";
import { ConfirmDialog } from "@ds/components/Modal";
import { hasPermission } from "@/lib/auth";

const FEATURE_KEYS = ["xauusd", "nas100", "multi_account", "telegram_alerts", "analytics", "api_access", "priority_support"];

export default function SubscriptionsPage() {
  const [plans, setPlans] = useState<any[]>([]);
  const [subs, setSubs] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState("");
  const [editingPlan, setEditingPlan] = useState<any>(null);
  const [editForm, setEditForm] = useState<any>({});
  const [saving, setSaving] = useState(false);
  const [confirmCancel, setConfirmCancel] = useState<any>(null);
  const [cancelBusy, setCancelBusy] = useState(false);
  const [confirmRestore, setConfirmRestore] = useState(false);
  const [restoreBusy, setRestoreBusy] = useState(false);

  const canUpdate = hasPermission("subscriptions.update");
  const canCancel = hasPermission("subscriptions.cancel");

  const load = useCallback(async () => {
    try {
      const [p, s] = await Promise.all([listPlans(), listSubscriptions("?limit=100")]);
      setPlans(p.items);
      setSubs(s.items);
      setTotal(s.total);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleCancel = async (id: string) => {
    setCancelBusy(true);
    try { await cancelSubscription(id); setConfirmCancel(null); load(); }
    catch (e) { setError((e as Error).message); }
    finally { setCancelBusy(false); }
  };

  const handleRestore = async () => {
    setRestoreBusy(true);
    try {
      await restoreDefaultPlans();
      setConfirmRestore(false);
      load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setRestoreBusy(false);
    }
  };

  const openEdit = (p: any) => {
    setEditingPlan(p);
    setEditForm({
      name: p.name,
      price_monthly: p.price_monthly ?? "",
      price_yearly: p.price_yearly ?? "",
      one_time_price: p.one_time_price ?? "",
      max_accounts: p.max_accounts,
      max_daily_loss: p.max_daily_loss,
      max_risk_per_trade: p.max_risk_per_trade,
      sort_order: p.sort_order ?? 0,
      features: { ...(p.features || {}) },
      on_sale: p.on_sale ?? false,
      old_price: p.old_price ?? "",
      sale_label: p.sale_label ?? "",
    });
  };

  const handleSave = async () => {
    if (!editingPlan) return;
    setSaving(true);
    try {
      const body: any = {};
      for (const k of ["name", "price_monthly", "price_yearly", "one_time_price", "max_accounts", "max_daily_loss", "max_risk_per_trade", "sort_order"]) {
        const v = editForm[k];
        if (v !== "" && v !== null) body[k] = typeof v === "string" && !isNaN(Number(v)) ? Number(v) : v;
      }
      for (const k of ["on_sale", "sale_label"]) {
        if (k in editForm) body[k] = editForm[k];
      }
      if ("old_price" in editForm) {
        const v = editForm.old_price;
        body.old_price = v !== "" && v !== null ? (typeof v === "string" && !isNaN(Number(v)) ? Number(v) : v) : null;
      }
      body.features = editForm.features;
      await updatePlan(editingPlan.id, body);
      setEditingPlan(null);
      load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const toggleFeature = (key: string) => {
    setEditForm((f: any) => ({ ...f, features: { ...f.features, [key]: !f.features[key] } }));
  };

  const calcDaysLeft = (endDate: string): number => {
    if (!endDate) return 0;
    const end = new Date(endDate).getTime();
    const now = Date.now();
    return Math.max(0, Math.ceil((end - now) / (1000 * 60 * 60 * 24)));
  };

  return (
    <PermissionGuard permission="subscriptions.read">
      <div>
        <PageHeader
          title="Plans"
          subtitle="Subscription plans, features and active client subscriptions."
          actions={
            <Button variant="secondary" onClick={() => setConfirmRestore(true)}>
              Restore Defaults
            </Button>
          }
        />
        {error && <div className="text-danger text-sm mb-3">{error}</div>}

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          {plans.map((p) => {
            const promo = p.promotion;
            const hasQuickSale = p.on_sale && p.old_price;
            const displayPrice = promo ? promo.new_price : (hasQuickSale ? p.price_monthly : p.price_monthly);
            const daysLeft = promo ? calcDaysLeft(promo.end_date) : 0;
            const badgeText = promo?.badge_text || (hasQuickSale ? p.sale_label : null);
            const oldPrice = promo?.old_price || (hasQuickSale ? p.old_price : null);
            const newPrice = promo?.new_price || p.price_monthly;

            return (
              <div key={p.id} className={`bg-raised border rounded-lg p-5 relative flex flex-col ${
                p.id === "professional" ? "border-brand-500 ring-1 ring-brand-500/40" : "border-line"
              }`}>
                {badgeText && (
                  <div className="absolute -top-2.5 left-3 bg-danger text-white text-[10px] font-bold px-2.5 py-0.5 rounded-full">
                    {badgeText}
                  </div>
                )}
                <div className="flex items-center justify-between mb-1">
                  <div className="text-base font-bold text-ink">{p.name}</div>
                  {canUpdate && <button onClick={() => openEdit(p)}
                    className="text-[10px] px-1.5 py-0.5 rounded border border-line text-ink-muted hover:bg-hover">Edit</button>}
                </div>

                <div className="mb-2">
                  {promo || hasQuickSale ? (
                    <div>
                      <div className="flex items-baseline gap-1.5">
                        <span className="text-lg text-ink-muted line-through">${oldPrice}</span>
                        <span className="text-xl font-bold text-brand-400">${promo ? promo.new_price : p.price_monthly}</span>
                        <span className="text-xs text-ink-muted font-normal">/mo</span>
                      </div>
                      {promo && (
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className="text-[10px] bg-danger/10 text-danger px-1.5 py-0.5 rounded font-bold">-{promo.discount_percent}%</span>
                          {daysLeft > 0 && (
                            <span className="text-[10px] text-warn">Ends in {daysLeft} {daysLeft === 1 ? "day" : "days"}</span>
                          )}
                        </div>
                      )}
                    </div>
                  ) : (
                    <div>
                      <div className="text-xl font-bold text-ink">
                        {p.price_monthly === null && p.price_yearly === null && p.one_time_price === null
                          ? "Custom"
                          : p.one_time_price
                            ? `$${p.one_time_price}`
                            : p.price_monthly === 0 || p.price_monthly === null
                              ? "Free"
                              : `$${p.price_monthly}`}
                        {p.price_monthly > 0 && <span className="text-xs text-ink-muted font-normal">/mo</span>}
                        {p.one_time_price > 0 && !p.price_monthly && <span className="text-xs text-ink-muted font-normal"> one-time</span>}
                      </div>
                      {p.price_yearly > 0 && <div className="text-[10px] text-ink-muted">${p.price_yearly}/year</div>}
                      {p.one_time_price > 0 && !p.price_yearly && <div className="text-[10px] text-ink-muted">Lifetime license</div>}
                    </div>
                  )}
                </div>

                <div className="text-[10px] text-ink-muted mb-2">
                  {p.max_accounts >= 999 ? "Unlimited accounts" : `Up to ${p.max_accounts} account${p.max_accounts > 1 ? "s" : ""}`}
                </div>

                <div className="space-y-1 flex-1">
                  {p.features && Object.entries(p.features).map(([k, v]) => (
                    <div key={k} className={`text-[10px] ${v ? "text-ok" : "text-ink-muted"}`}>
                      {v ? "✓" : "✗"} {k.replace(/_/g, " ")}
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>

        {/* Active Subscriptions */}
        <div className="mt-8">
          <h2 className="text-sm font-semibold mb-3 text-ink">Active Subscriptions ({total})</h2>
          <Card bodyClassName="p-0">
            <Table columns={["User", "Plan", "Cycle", "Price", "Start", "End", "Status", "Actions"]}>
              {subs.length === 0 && (
                <tr>
                  <td colSpan={8} className="text-center text-ink-muted py-12 px-4">
                    No subscriptions yet. They will appear once users start subscribing.
                  </td>
                </tr>
              )}
              {subs.map((s) => (
                <tr key={s.id}>
                  <Td mono>{s.user_id?.slice(0, 8)}</Td>
                  <Td>
                    <Badge tone={s.plan === "premium" || s.plan === "enterprise" ? "blue" : s.plan === "professional" ? "green" : "gray"}>
                      {s.plan}
                    </Badge>
                  </Td>
                  <Td>{s.billing_cycle || "—"}</Td>
                  <Td>${s.price?.toFixed(2) || "0.00"}</Td>
                  <Td>{s.start_date ? new Date(s.start_date).toLocaleDateString() : "—"}</Td>
                  <Td>{s.end_date ? new Date(s.end_date).toLocaleDateString() : "—"}</Td>
                  <Td>
                    <Badge tone={s.active ? "green" : "gray"}>{s.active ? "active" : "cancelled"}</Badge>
                  </Td>
                  <Td>
                    {s.active && canCancel && (
                      <Button size="sm" variant="danger" onClick={() => setConfirmCancel(s)}>
                        Cancel
                      </Button>
                    )}
                  </Td>
                </tr>
              ))}
            </Table>
          </Card>
        </div>

        <ConfirmDialog
          open={!!confirmCancel}
          title="Cancel Subscription"
          description="This will cancel the client's subscription immediately. The client will lose plan access at the end of the current period."
          confirmLabel="Cancel Subscription"
          tone="danger"
          loading={cancelBusy}
          onConfirm={() => confirmCancel && handleCancel(confirmCancel.id)}
          onCancel={() => setConfirmCancel(null)}
        />

        <ConfirmDialog
          open={confirmRestore}
          title="Restore Default Plans"
          description="This will overwrite all plan configurations with the default set. Custom plan edits will be lost."
          confirmLabel="Restore"
          tone="danger"
          loading={restoreBusy}
          onConfirm={handleRestore}
          onCancel={() => setConfirmRestore(false)}
        />

        {/* Edit Plan Modal */}
        <Modal open={!!editingPlan} onClose={() => setEditingPlan(null)} title={`Edit Plan: ${editingPlan?.name || ""}`}>
          {editingPlan && (
            <div className="space-y-4 text-sm">
              <div className="grid grid-cols-2 gap-3">
                <TextField label="Plan Name" value={editForm.name}
                  onChange={(e) => setEditForm({ ...editForm, name: e.target.value })} />
                <TextField label="Sort Order" type="number" value={editForm.sort_order}
                  onChange={(e) => setEditForm({ ...editForm, sort_order: e.target.value })} />
              </div>
              <div className="grid grid-cols-3 gap-3">
                <TextField label="Monthly Price ($)" type="number" step="0.01" value={editForm.price_monthly}
                  onChange={(e) => setEditForm({ ...editForm, price_monthly: e.target.value })} />
                <TextField label="Yearly Price ($)" type="number" step="0.01" value={editForm.price_yearly}
                  onChange={(e) => setEditForm({ ...editForm, price_yearly: e.target.value })} />
                <TextField label="One-Time Price ($)" type="number" step="0.01" value={editForm.one_time_price}
                  onChange={(e) => setEditForm({ ...editForm, one_time_price: e.target.value })} />
              </div>
              <div className="grid grid-cols-3 gap-3">
                <TextField label="Max Accounts" type="number" value={editForm.max_accounts}
                  onChange={(e) => setEditForm({ ...editForm, max_accounts: e.target.value })} />
                <TextField label="Max Daily Loss ($)" type="number" step="0.01" value={editForm.max_daily_loss}
                  onChange={(e) => setEditForm({ ...editForm, max_daily_loss: e.target.value })} />
                <TextField label="Max Risk/Trade (%)" type="number" step="0.1" value={editForm.max_risk_per_trade}
                  onChange={(e) => setEditForm({ ...editForm, max_risk_per_trade: e.target.value })} />
              </div>

              {/* Promo / Sale */}
              <div className="border border-line rounded-lg p-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-semibold text-ink-soft">Promo / Sale</span>
                  <label className="flex items-center gap-1.5 cursor-pointer">
                    <span className="text-[10px] text-ink-muted">On Sale</span>
                    <input type="checkbox" checked={editForm.on_sale}
                      onChange={(e) => setEditForm({ ...editForm, on_sale: e.target.checked })}
                      className="accent-brand-500" />
                  </label>
                </div>
                {editForm.on_sale && (
                  <div className="grid grid-cols-2 gap-3">
                    <TextField label="Old Price ($)" type="number" step="0.01" value={editForm.old_price}
                      onChange={(e) => setEditForm({ ...editForm, old_price: e.target.value })} />
                    <TextField label="Badge Label" value={editForm.sale_label}
                      onChange={(e) => setEditForm({ ...editForm, sale_label: e.target.value })}
                      placeholder="e.g. -50%" />
                  </div>
                )}
              </div>

              <div>
                <label className="block text-xs font-medium text-ink-soft mb-2">Features</label>
                <div className="flex flex-wrap gap-2">
                  {FEATURE_KEYS.map((k) => (
                    <button key={k} type="button" onClick={() => toggleFeature(k)}
                      className={`text-xs px-2 py-1 rounded border ${
                        editForm.features[k] ? "border-ok bg-ok/10 text-ok" : "border-line text-ink-muted"
                      }`}>
                      {editForm.features[k] ? "✓" : "✗"} {k.replace(/_/g, " ")}
                    </button>
                  ))}
                </div>
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <Button variant="ghost" onClick={() => setEditingPlan(null)}>Cancel</Button>
                <Button onClick={handleSave} loading={saving}>{saving ? "Saving..." : "Save"}</Button>
              </div>
            </div>
          )}
        </Modal>
      </div>
    </PermissionGuard>
  );
}
