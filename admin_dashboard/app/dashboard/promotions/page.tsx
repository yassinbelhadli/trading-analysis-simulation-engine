"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import Modal from "@/components/Modal";
import PermissionGuard from "@/components/auth/permission_guard";
import { listPromotions, createPromotion, updatePromotion, deletePromotion, togglePromotion, listPlans } from "@/lib/api";
import { Badge, Button, Card, PageHeader, Table, Td } from "@ds/components/ui";
import { ConfirmDialog } from "@ds/components/Modal";
import { hasPermission } from "@/lib/auth";

export default function PromotionsPage() {
  const [promos, setPromos] = useState<any[]>([]);
  const [plans, setPlans] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [editing, setEditing] = useState<any>(null);
  const [form, setForm] = useState<any>({});
  const [saving, setSaving] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; name: string } | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);

  const canCreate = hasPermission("subscriptions.create");
  const canUpdate = hasPermission("subscriptions.update");
  const canDelete = hasPermission("subscriptions.cancel");

  const load = useCallback(async () => {
    try {
      const [p, plansRes] = await Promise.all([listPromotions("?limit=100"), listPlans()]);
      setPromos(p.items);
      setTotal(p.total);
      setPlans(plansRes.items);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // Compute discount whenever old_price or new_price changes
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
    setForm({ name: "", plan_id: "", old_price: "", new_price: "", badge_text: "", start_date: "", end_date: "", active: true });
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
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setDeleteBusy(true);
    try {
      setError("");
      await deletePromotion(deleteTarget.id);
      setDeleteTarget(null);
      load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setDeleteBusy(false);
    }
  };

  const handleToggle = async (id: string) => {
    try { setError(""); await togglePromotion(id); load(); }
    catch (e) { setError((e as Error).message); }
  };

  const activeCount = promos.filter((p) => p.active).length;
  const planNames: Record<string, string> = {};
  plans.forEach((pl) => { planNames[pl.id] = pl.name; });

  return (
    <PermissionGuard permission="subscriptions.read">
      <div>
        <PageHeader
          title="Promotions"
          subtitle={`${total} promotion${total !== 1 ? "s" : ""} · ${activeCount} active`}
          actions={
            canCreate && (
            <Button icon="plus" onClick={openCreate}>
              New Promotion
            </Button>
            )
          }
        />

        {error && (
          <div className="bg-danger/10 border border-danger/30 text-danger text-xs px-3 py-2 rounded-lg mb-3">
            {error}
          </div>
        )}

        {/* Active promos summary bar */}
        {activeCount > 0 && (
          <div className="flex gap-2 mb-4 flex-wrap">
            {promos.filter((p) => p.active).map((p) => (
              <div key={p.id} className="flex items-center gap-2 bg-ok/10 border border-ok/30 text-xs px-2.5 py-1 rounded-full">
                <span className="font-medium text-ok">{p.name}</span>
                <span className="text-ink-muted">for</span>
                <span className="text-ink-muted">{planNames[p.plan_id] || p.plan_id}</span>
                <span className="text-warn font-bold">-{p.discount_percent}%</span>
              </div>
            ))}
          </div>
        )}

        <Card bodyClassName="p-0">
          <Table columns={["Name", "Plan", "Old Price", "New Price", "Discount", "Badge", "Period", "Status", "Actions"]}>
            {promos.length === 0 && (
              <tr>
                <td colSpan={9} className="text-center py-16 text-ink-muted text-sm">
                  <p>No promotions yet</p>
                  <p className="text-xs mt-1">Click &quot;New Promotion&quot; to create your first offer.</p>
                </td>
              </tr>
            )}
            {promos.map((p) => (
              <tr key={p.id} className="hover:bg-hover/60 transition-colors">
                <Td>
                  <div className="flex items-center gap-2">
                    {p.active && <span className="w-1.5 h-1.5 rounded-full bg-ok shrink-0" />}
                    <span className="text-xs font-medium text-ink">{p.name}</span>
                  </div>
                </Td>
                <Td>
                  <Badge tone="blue">{planNames[p.plan_id] || p.plan_id}</Badge>
                </Td>
                <Td className="text-xs text-ink-muted line-through">${p.old_price?.toFixed(2)}</Td>
                <Td className="text-xs font-bold text-ok">${p.new_price?.toFixed(2)}</Td>
                <Td>
                  <Badge tone="amber">-{p.discount_percent}%</Badge>
                </Td>
                <Td>
                  {p.badge_text ? (
                    <Badge tone="red">{p.badge_text}</Badge>
                  ) : (
                    <span className="text-xs text-ink-muted">—</span>
                  )}
                </Td>
                <Td className="text-[10px] text-ink-muted">
                  {p.start_date ? new Date(p.start_date).toLocaleDateString() : "—"}
                  <span className="mx-1">to</span>
                  {p.end_date ? new Date(p.end_date).toLocaleDateString() : "∞"}
                </Td>
                <Td>
                  <button type="button" onClick={() => handleToggle(p.id)} title="Toggle status">
                    <Badge tone={p.active ? "green" : "gray"}>{p.active ? "Active" : "Inactive"}</Badge>
                  </button>
                </Td>
                <Td>
                  <div className="flex gap-1.5">
                    {canUpdate && <Button size="sm" variant="ghost" onClick={() => openEdit(p)}>Edit</Button>}
                    {canDelete && <Button size="sm" variant="danger" onClick={() => setDeleteTarget({ id: p.id, name: p.name })}>Delete</Button>}
                  </div>
                </Td>
              </tr>
            ))}
          </Table>
        </Card>

        {/* Create / Edit Modal */}
        <Modal open={!!editing} onClose={() => setEditing(null)}
          title={editing === "new" ? "Create Promotion" : "Edit Promotion"}>
          {editing && (
            <div className="space-y-4 text-sm">
              {/* Section: Basic Info */}
              <div>
                <div className="text-[10px] uppercase tracking-wider text-ink-muted font-semibold mb-2">Basic Info</div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-[10px] text-ink-soft mb-1">
                      Name <span className="text-danger">*</span>
                    </label>
                    <input
                      className={`w-full h-8 px-2.5 rounded-lg bg-input border text-xs text-ink outline-none transition-colors ${
                        fieldErrors.name ? "border-danger" : "border-line focus:border-brand-500"
                      }`}
                      value={form.name}
                      onChange={(e) => { setForm({ ...form, name: e.target.value }); setFieldErrors({ ...fieldErrors, name: "" }); }}
                      placeholder="e.g. Black Friday" />
                    {fieldErrors.name && <p className="text-[10px] text-danger mt-0.5">{fieldErrors.name}</p>}
                  </div>
                  <div>
                    <label className="block text-[10px] text-ink-soft mb-1">
                      Applies To <span className="text-danger">*</span>
                    </label>
                    <select
                      className={`w-full h-8 px-2.5 rounded-lg bg-input border text-xs text-ink outline-none transition-colors ${
                        fieldErrors.plan_id ? "border-danger" : "border-line focus:border-brand-500"
                      }`}
                      value={form.plan_id}
                      onChange={(e) => { setForm({ ...form, plan_id: e.target.value }); setFieldErrors({ ...fieldErrors, plan_id: "" }); }}>
                      <option value="">— Select Plan —</option>
                      {plans.map((pl) => <option key={pl.id} value={pl.id}>{pl.name}</option>)}
                    </select>
                    {fieldErrors.plan_id && <p className="text-[10px] text-danger mt-0.5">{fieldErrors.plan_id}</p>}
                  </div>
                </div>
              </div>

              {/* Section: Pricing */}
              <div>
                <div className="text-[10px] uppercase tracking-wider text-ink-muted font-semibold mb-2">Pricing</div>
                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <label className="block text-[10px] text-ink-soft mb-1">
                      Old Price ($) <span className="text-danger">*</span>
                    </label>
                    <input type="number" step="0.01"
                      className={`w-full h-8 px-2.5 rounded-lg bg-input border text-xs text-ink outline-none transition-colors ${
                        fieldErrors.old_price ? "border-danger" : "border-line focus:border-brand-500"
                      }`}
                      value={form.old_price}
                      onChange={(e) => { setForm({ ...form, old_price: e.target.value }); setFieldErrors({ ...fieldErrors, old_price: "" }); }} />
                    {fieldErrors.old_price && <p className="text-[10px] text-danger mt-0.5">{fieldErrors.old_price}</p>}
                  </div>
                  <div>
                    <label className="block text-[10px] text-ink-soft mb-1">
                      New Price ($) <span className="text-danger">*</span>
                    </label>
                    <input type="number" step="0.01"
                      className={`w-full h-8 px-2.5 rounded-lg bg-input border text-xs text-ink outline-none transition-colors ${
                        fieldErrors.new_price ? "border-danger" : "border-line focus:border-brand-500"
                      }`}
                      value={form.new_price}
                      onChange={(e) => { setForm({ ...form, new_price: e.target.value }); setFieldErrors({ ...fieldErrors, new_price: "" }); }} />
                    {fieldErrors.new_price && <p className="text-[10px] text-danger mt-0.5">{fieldErrors.new_price}</p>}
                  </div>
                  <div>
                    <label className="block text-[10px] text-ink-soft mb-1">Discount</label>
                    <div className="flex items-center h-full pt-4">
                      {autoDiscount > 0 ? (
                        <span className="text-lg font-bold text-warn">-{autoDiscount}%</span>
                      ) : (
                        <span className="text-xs text-ink-muted">Auto-calculated</span>
                      )}
                    </div>
                  </div>
                </div>
              </div>

              {/* Section: Display */}
              <div>
                <div className="text-[10px] uppercase tracking-wider text-ink-muted font-semibold mb-2">Display</div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-[10px] text-ink-soft mb-1">Badge Text</label>
                    <input className="w-full h-8 px-2.5 rounded-lg bg-input border border-line text-xs text-ink outline-none focus:border-brand-500 transition-colors"
                      value={form.badge_text}
                      onChange={(e) => setForm({ ...form, badge_text: e.target.value })}
                      placeholder="e.g. Limited Offer" />
                  </div>
                  <div className="flex items-end gap-3 pb-1">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input type="checkbox" checked={form.active}
                        onChange={(e) => setForm({ ...form, active: e.target.checked })}
                        className="accent-brand-500" />
                      <span className="text-xs text-ink-soft">Active</span>
                    </label>
                  </div>
                </div>
              </div>

              {/* Section: Schedule */}
              <div>
                <div className="text-[10px] uppercase tracking-wider text-ink-muted font-semibold mb-2">Schedule</div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-[10px] text-ink-soft mb-1">Start Date</label>
                    <input type="date"
                      className="w-full h-8 px-2.5 rounded-lg bg-input border border-line text-xs text-ink outline-none focus:border-brand-500 transition-colors"
                      value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} />
                  </div>
                  <div>
                    <label className="block text-[10px] text-ink-soft mb-1">End Date</label>
                    <input type="date"
                      className="w-full h-8 px-2.5 rounded-lg bg-input border border-line text-xs text-ink outline-none focus:border-brand-500 transition-colors"
                      value={form.end_date} onChange={(e) => setForm({ ...form, end_date: e.target.value })} />
                  </div>
                </div>
              </div>

              {/* Actions */}
              <div className="flex justify-end gap-2 pt-3 border-t border-line">
                <Button size="sm" variant="ghost" type="button" onClick={() => setEditing(null)}>Cancel</Button>
                <Button size="sm" type="button" onClick={handleSave} loading={saving}>
                  {editing === "new" ? "Create Promotion" : "Save Changes"}
                </Button>
              </div>
            </div>
          )}
        </Modal>

        <ConfirmDialog
          open={!!deleteTarget}
          title="Delete promotion"
          description={`Delete "${deleteTarget?.name}"? This cannot be undone.`}
          confirmLabel="Delete"
          tone="danger"
          loading={deleteBusy}
          onConfirm={handleDelete}
          onCancel={() => setDeleteTarget(null)}
        />
      </div>
    </PermissionGuard>
  );
}
