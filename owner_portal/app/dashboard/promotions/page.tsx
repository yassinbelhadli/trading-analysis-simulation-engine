"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import OwnerPermissionGuard from "@/components/auth/owner_permission_guard";
import { listPromotions, createPromotion, updatePromotion, deletePromotion, togglePromotion, listPlans } from "@/lib/api";
import { parseApiError } from "@/lib/errors";
import { PageHeader, Card, Table, Td, Badge, Button, TextField, SelectField, EmptyState } from "@ds/components/ui";
import { Modal, ConfirmDialog } from "@ds/components/Modal";
import { Icon } from "@ds/components/Icon";

interface PromoForm {
  name: string;
  plan_id: string;
  old_price: string;
  new_price: string;
  discount_percent?: number;
  badge_text: string;
  start_date: string;
  end_date: string;
  active: boolean;
}

const EMPTY_FORM: PromoForm = {
  name: "",
  plan_id: "",
  old_price: "",
  new_price: "",
  badge_text: "",
  start_date: "",
  end_date: "",
  active: true,
};

export default function PromotionsPage() {
  const [promos, setPromos] = useState<any[]>([]);
  const [plans, setPlans] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [editing, setEditing] = useState<any>(null);
  const [form, setForm] = useState<PromoForm>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<any>(null);
  const [confirmDeactivate, setConfirmDeactivate] = useState<any>(null);

  const load = useCallback(async () => {
    try {
      const [promoResult, plansResult] = await Promise.allSettled([
        listPromotions("?limit=100"),
        listPlans(),
      ]);
      if (promoResult.status === "fulfilled") {
        setPromos(promoResult.value.items);
        setTotal(promoResult.value.total);
      }
      if (plansResult.status === "fulfilled") {
        setPlans(plansResult.value.items);
      }
      // Partial success is acceptable; each rejection gets its own parsed,
      // user-friendly message instead of raw browser error text
      const errors: string[] = [];
      if (promoResult.status === "rejected") errors.push(parseApiError(promoResult.reason));
      if (plansResult.status === "rejected") errors.push(parseApiError(plansResult.reason));
      setError([...new Set(errors)].join(" "));
    } catch (e) {
      setError(parseApiError(e));
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const autoDiscount = useMemo(() => {
    const oldP = parseFloat(form.old_price);
    const newP = parseFloat(form.new_price);
    if (oldP > 0 && newP > 0 && oldP > newP) {
      return Math.round((1 - newP / oldP) * 100);
    }
    return 0;
  }, [form.old_price, form.new_price]);

  const openCreate = () => {
    setEditing("new");
    setFieldErrors({});
    setForm({ ...EMPTY_FORM });
  };

  const openEdit = (promo: any) => {
    setEditing(promo.id);
    setFieldErrors({});
    setForm({
      name: promo.name,
      plan_id: promo.plan_id,
      old_price: promo.old_price,
      new_price: promo.new_price,
      discount_percent: promo.discount_percent,
      badge_text: promo.badge_text ?? "",
      start_date: promo.start_date ? promo.start_date.split("T")[0] : "",
      end_date: promo.end_date ? promo.end_date.split("T")[0] : "",
      active: promo.active,
    });
  };

  const validate = (): boolean => {
    const errs: Record<string, string> = {};
    if (!form.name?.trim()) errs.name = "Required";
    if (!form.plan_id) errs.plan_id = "Required";
    if (!form.old_price || parseFloat(form.old_price) <= 0) errs.old_price = "Must be > 0";
    if (!form.new_price || parseFloat(form.new_price) <= 0) errs.new_price = "Must be > 0";
    setFieldErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSave = async () => {
    if (!editing || !validate()) return;
    setSaving(true);
    setError("");
    try {
      const body: any = { ...form };
      if (body.start_date === "") body.start_date = null;
      if (body.end_date === "") body.end_date = null;
      body.discount_percent = autoDiscount;

      if (editing === "new") {
        await createPromotion(body);
      } else {
        await updatePromotion(editing, body);
      }
      setEditing(null);
      load();
    } catch (e) {
      setError(parseApiError(e));
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      setError("");
      await deletePromotion(id);
      setConfirmDelete(null);
      load();
    } catch (e) {
      setError(parseApiError(e));
      setConfirmDelete(null);
    }
  };

  const handleToggle = async (id: string) => {
    try {
      setError("");
      await togglePromotion(id);
      setConfirmDeactivate(null);
      load();
    } catch (e) {
      setError(parseApiError(e));
      setConfirmDeactivate(null);
    }
  };

  const activeCount = promos.filter((p) => p.active).length;
  const planNames: Record<string, string> = {};
  plans.forEach((pl) => { planNames[pl.id] = pl.name; });

  const fieldCls = (hasError: boolean) =>
    `w-full px-2.5 py-1.5 rounded-lg bg-input border text-xs text-ink outline-none transition-colors ${
      hasError ? "border-danger" : "border-line focus:border-brand-500"
    }`;

  return (
    <OwnerPermissionGuard permission="subscriptions.read">
      <div className="flex flex-col gap-5 max-w-6xl">
        <PageHeader
          title="Promotions"
          subtitle={`${total} promotion${total !== 1 ? "s" : ""} · ${activeCount} active`}
          actions={
            <Button icon="plus" onClick={openCreate}>
              New Promotion
            </Button>
          }
        />

        {error && (
          <div className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
            {error}
          </div>
        )}

        {activeCount > 0 && (
          <div className="flex gap-2 flex-wrap">
            {promos.filter((p) => p.active).map((p) => (
              <div key={p.id} className="flex items-center gap-2 bg-brand-tint border border-brand-500/40 text-xs px-2.5 py-1 rounded-full">
                <span className="font-medium text-brand-400">{p.name}</span>
                <Icon name="arrow-right" className="h-3 w-3 text-ink-muted" />
                <span className="text-ink-soft">{planNames[p.plan_id] || p.plan_id}</span>
                <span className="text-warn font-bold">-{p.discount_percent}%</span>
              </div>
            ))}
          </div>
        )}

        <Card title="Promotion directory" icon="tag" bodyClassName="p-0">
          {promos.length === 0 && !error ? (
            <EmptyState
              icon="tag"
              title="No promotions yet"
              description="Create the first promotion to start offering discounts on plans."
              action={
                <Button icon="plus" onClick={openCreate}>
                  New Promotion
                </Button>
              }
            />
          ) : (
            <Table columns={["Name", "Plan", "Old Price", "New Price", "Discount", "Badge", "Period", "Status", "Actions"]}>
              {promos.map((p) => (
                <tr key={p.id} className="hover:bg-hover transition-colors">
                  <Td>
                    <div className="flex items-center gap-2">
                      {p.active && <span className="h-1.5 w-1.5 rounded-full bg-ok shrink-0" />}
                      <span className="text-xs font-medium text-ink">{p.name}</span>
                    </div>
                  </Td>
                  <Td>
                    <Badge tone="blue">{planNames[p.plan_id] || p.plan_id}</Badge>
                  </Td>
                  <Td className="text-xs text-ink-muted line-through">${p.old_price?.toFixed(2)}</Td>
                  <Td className="text-xs font-bold text-brand-400">${p.new_price?.toFixed(2)}</Td>
                  <Td>
                    <span className="text-xs font-bold text-warn bg-warn/10 px-1.5 py-0.5 rounded">
                      -{p.discount_percent}%
                    </span>
                  </Td>
                  <Td className="text-xs">
                    {p.badge_text ? (
                      <Badge tone="red">{p.badge_text}</Badge>
                    ) : (
                      <span className="text-xs text-ink-muted">—</span>
                    )}
                  </Td>
                  <Td className="text-[10px] text-ink-muted">
                    {p.start_date ? new Date(p.start_date).toLocaleDateString() : "—"}
                    <Icon name="arrow-right" className="inline h-3 w-3 mx-1" />
                    {p.end_date ? new Date(p.end_date).toLocaleDateString() : "∞"}
                  </Td>
                  <Td>
                    <button
                      onClick={() => {
                        if (p.active) setConfirmDeactivate(p);
                        else handleToggle(p.id);
                      }}
                      className={`text-[10px] px-2 py-0.5 rounded-full font-medium transition-colors ${
                        p.active
                          ? "bg-brand-tint text-brand-400 hover:bg-brand-tint"
                          : "bg-hover text-ink-soft hover:bg-hover"
                      }`}
                    >
                      {p.active ? "Active" : "Inactive"}
                    </button>
                  </Td>
                  <Td>
                    <div className="flex gap-1.5">
                      <Button size="sm" variant="ghost" icon="edit" onClick={() => openEdit(p)}>
                        Edit
                      </Button>
                      <Button size="sm" variant="danger" icon="trash" onClick={() => setConfirmDelete(p)}>
                        Delete
                      </Button>
                    </div>
                  </Td>
                </tr>
              ))}
            </Table>
          )}
        </Card>

        <Modal
          open={!!editing}
          onClose={() => setEditing(null)}
          title={editing === "new" ? "Create Promotion" : "Edit Promotion"}
          icon="info"
          size="lg"
        >
          {editing && (
            <div className="space-y-4 text-sm">
              <div>
                <p className="text-[10px] uppercase tracking-wider text-ink-muted font-semibold mb-2">Basic Info</p>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <TextField
                      label="Name"
                      required
                      value={form.name}
                      error={fieldErrors.name}
                      onChange={(e) => { setForm({ ...form, name: e.target.value }); setFieldErrors({ ...fieldErrors, name: "" }); }}
                      placeholder="e.g. Black Friday"
                    />
                  </div>
                  <div>
                    <SelectField
                      label="Applies To"
                      value={form.plan_id}
                      onChange={(e) => { setForm({ ...form, plan_id: e.target.value }); setFieldErrors({ ...fieldErrors, plan_id: "" }); }}
                    >
                      <option value="">Select Plan</option>
                      {plans.map((pl) => <option key={pl.id} value={pl.id}>{pl.name}</option>)}
                    </SelectField>
                    {fieldErrors.plan_id && <p className="text-[10px] text-danger mt-0.5">{fieldErrors.plan_id}</p>}
                  </div>
                </div>
              </div>

              <div>
                <p className="text-[10px] uppercase tracking-wider text-ink-muted font-semibold mb-2">Pricing</p>
                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <TextField
                      label="Old Price ($)"
                      type="number"
                      step="0.01"
                      value={form.old_price}
                      error={fieldErrors.old_price}
                      onChange={(e) => { setForm({ ...form, old_price: e.target.value }); setFieldErrors({ ...fieldErrors, old_price: "" }); }}
                    />
                  </div>
                  <div>
                    <TextField
                      label="New Price ($)"
                      type="number"
                      step="0.01"
                      value={form.new_price}
                      error={fieldErrors.new_price}
                      onChange={(e) => { setForm({ ...form, new_price: e.target.value }); setFieldErrors({ ...fieldErrors, new_price: "" }); }}
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-ink-soft mb-1.5">Discount</label>
                    <div className="flex items-center h-9">
                      {autoDiscount > 0 ? (
                        <span className="text-lg font-bold text-warn">-{autoDiscount}%</span>
                      ) : (
                        <span className="text-xs text-ink-muted">Auto-calculated</span>
                      )}
                    </div>
                  </div>
                </div>
              </div>

              <div>
                <p className="text-[10px] uppercase tracking-wider text-ink-muted font-semibold mb-2">Display</p>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <TextField
                      label="Badge Text"
                      value={form.badge_text}
                      onChange={(e) => setForm({ ...form, badge_text: e.target.value })}
                      placeholder="e.g. Limited Offer"
                    />
                  </div>
                  <div className="flex items-end gap-3 pb-1">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={form.active}
                        onChange={(e) => setForm({ ...form, active: e.target.checked })}
                        className="accent-brand-500"
                      />
                      <span className="text-xs text-ink-soft">Active</span>
                    </label>
                  </div>
                </div>
              </div>

              <div>
                <p className="text-[10px] uppercase tracking-wider text-ink-muted font-semibold mb-2">Schedule</p>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-ink-soft mb-1.5">Start Date</label>
                    <input
                      type="date"
                      className={fieldCls(false)}
                      value={form.start_date}
                      onChange={(e) => setForm({ ...form, start_date: e.target.value })}
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-ink-soft mb-1.5">End Date</label>
                    <input
                      type="date"
                      className={fieldCls(false)}
                      value={form.end_date}
                      onChange={(e) => setForm({ ...form, end_date: e.target.value })}
                    />
                  </div>
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-line">
                <Button variant="ghost" onClick={() => setEditing(null)}>Cancel</Button>
                <Button onClick={handleSave} loading={saving}>
                  {saving ? "Saving..." : editing === "new" ? "Create Promotion" : "Save Changes"}
                </Button>
              </div>
            </div>
          )}
        </Modal>

        <ConfirmDialog
          open={!!confirmDelete}
          title="Delete promotion"
          description={
            confirmDelete
              ? `Delete promotion "${confirmDelete.name}"? Clients currently seeing this offer will revert to standard pricing.`
              : undefined
          }
          confirmLabel="Delete"
          cancelLabel="Cancel"
          tone="danger"
          onConfirm={() => confirmDelete && handleDelete(confirmDelete.id)}
          onCancel={() => setConfirmDelete(null)}
        />

        <ConfirmDialog
          open={!!confirmDeactivate}
          title="Deactivate promotion"
          description={
            confirmDeactivate
              ? `Deactivate "${confirmDeactivate.name}"? The offer will no longer be visible to clients.`
              : undefined
          }
          confirmLabel="Deactivate"
          cancelLabel="Cancel"
          tone="danger"
          onConfirm={() => confirmDeactivate && handleToggle(confirmDeactivate.id)}
          onCancel={() => setConfirmDeactivate(null)}
        />
      </div>
    </OwnerPermissionGuard>
  );
}
