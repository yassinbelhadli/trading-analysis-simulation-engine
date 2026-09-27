"use client";

import { useEffect, useState, useCallback } from "react";
import Modal from "@/components/Modal";
import PermissionGuard from "@/components/auth/permission_guard";
import { listCoupons, createCoupon, updateCoupon, deleteCoupon, toggleCoupon, listPlans } from "@/lib/api";
import { Badge, Button, Card, PageHeader, Table, Td } from "@ds/components/ui";
import { ConfirmDialog } from "@ds/components/Modal";
import { hasPermission } from "@/lib/auth";

const VALID_CURRENCIES = ["USD", "EUR", "MAD", "AED", "GBP", "CAD", "AUD", "CHF", "JPY", "USDT"];

export default function CouponsPage() {
  const [coupons, setCoupons] = useState<any[]>([]);
  const [plans, setPlans] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [editing, setEditing] = useState<any>(null);
  const [form, setForm] = useState<any>({});
  const [saving, setSaving] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; name: string } | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);

  const canCreate = hasPermission("coupons.create");
  const canUpdate = hasPermission("coupons.update");
  const canDelete = hasPermission("coupons.delete");

  const load = useCallback(async () => {
    try {
      const [c, plansRes] = await Promise.all([listCoupons(), listPlans()]);
      setCoupons(c.items);
      setTotal(c.total);
      setPlans(plansRes.items);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const openCreate = () => {
    setEditing("new");
    setFieldErrors({});
    setForm({
      code: "", name: "", description: "", discount_type: "percentage", discount_value: "",
      currency: "USD", valid_from: "", valid_until: "", max_redemptions: "", max_per_user: 1,
      min_subscription_value: "", applicable_plans: [], active: true,
    });
  };

  const openEdit = (c: any) => {
    setEditing(c.id);
    setFieldErrors({});
    setForm({
      code: c.code, name: c.name, description: c.description ?? "",
      discount_type: c.discount_type, discount_value: c.discount_value,
      currency: c.currency || "USD",
      valid_from: c.valid_from ? c.valid_from.split("T")[0] : "",
      valid_until: c.valid_until ? c.valid_until.split("T")[0] : "",
      max_redemptions: c.max_redemptions ?? "", max_per_user: c.max_per_user ?? 1,
      min_subscription_value: c.min_subscription_value ?? "",
      applicable_plans: c.applicable_plans || [], active: c.active,
    });
  };

  const validate = (): boolean => {
    const errs: Record<string, string> = {};
    if (!form.code?.trim()) errs.code = "Required";
    else if (!/^[A-Z0-9][A-Z0-9_-]{2,49}$/.test(form.code.trim().toUpperCase())) errs.code = "3-50 chars: A-Z, 0-9, _ or -";
    if (!form.name?.trim()) errs.name = "Required";
    if (!form.discount_type) errs.discount_type = "Required";
    if (form.discount_value === "" || form.discount_value === null || parseFloat(form.discount_value) <= 0) {
      errs.discount_value = "Must be > 0";
    } else if (form.discount_type === "percentage" && parseFloat(form.discount_value) > 100) {
      errs.discount_value = "Must be ≤ 100";
    }
    if (form.discount_type === "fixed_amount" && !form.currency) errs.currency = "Required";
    if (form.max_redemptions !== "" && form.max_redemptions !== null && parseInt(form.max_redemptions) <= 0) {
      errs.max_redemptions = "Must be > 0";
    }
    if (form.max_per_user !== "" && form.max_per_user !== null && parseInt(form.max_per_user) <= 0) {
      errs.max_per_user = "Must be > 0";
    }
    if (form.valid_from && form.valid_until && form.valid_from > form.valid_until) {
      errs.valid_until = "Must be after start";
    }
    setFieldErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSave = async () => {
    if (!editing || !validate()) return;
    setSaving(true);
    setError("");
    try {
      const body: any = {
        code: form.code.trim().toUpperCase(),
        name: form.name.trim(),
        description: form.description || null,
        discount_type: form.discount_type,
        discount_value: parseFloat(form.discount_value),
        currency: form.discount_type === "fixed_amount" ? form.currency : null,
        valid_from: form.valid_from ? new Date(form.valid_from).toISOString() : null,
        valid_until: form.valid_until ? new Date(form.valid_until).toISOString() : null,
        max_redemptions: form.max_redemptions === "" || form.max_redemptions === null ? null : parseInt(form.max_redemptions),
        max_per_user: form.max_per_user === "" || form.max_per_user === null ? 1 : parseInt(form.max_per_user),
        min_subscription_value: form.min_subscription_value === "" || form.min_subscription_value === null ? null : parseFloat(form.min_subscription_value),
        applicable_plans: form.applicable_plans.length ? form.applicable_plans : null,
        active: form.active,
      };

      if (editing === "new") {
        await createCoupon(body);
      } else {
        await updateCoupon(editing, body);
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
      await deleteCoupon(deleteTarget.id);
      setDeleteTarget(null);
      load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setDeleteBusy(false);
    }
  };

  const handleToggle = async (id: string) => {
    try { setError(""); await toggleCoupon(id); load(); }
    catch (e) { setError((e as Error).message); }
  };

  const activeCount = coupons.filter((c) => c.active).length;
  const planNames: Record<string, string> = {};
  plans.forEach((pl) => { planNames[pl.id] = pl.name; });

  const togglePlan = (pid: string) => {
    const cur: string[] = Array.isArray(form.applicable_plans) ? form.applicable_plans : [];
    setForm({
      ...form,
      applicable_plans: cur.includes(pid) ? cur.filter((x) => x !== pid) : [...cur, pid],
    });
  };

  const fmtDiscount = (c: any) =>
    c.discount_type === "percentage" ? `${c.discount_value}%` : `${c.currency || ""} ${c.discount_value}`;

  return (
    <PermissionGuard permission="coupons.read">
      <div>
        <PageHeader
          title="Coupons"
          subtitle={`${total} coupon${total !== 1 ? "s" : ""} · ${activeCount} active`}
          actions={
            canCreate && (
            <Button icon="plus" onClick={openCreate}>
              New Coupon
            </Button>
            )
          }
        />

        {error && (
          <div className="bg-danger/10 border border-danger/30 text-danger text-xs px-3 py-2 rounded-lg mb-3">
            {error}
          </div>
        )}

        <Card bodyClassName="p-0">
          <Table columns={["Code", "Name", "Discount", "Plans", "Redemptions", "Valid", "Status", "Actions"]}>
            {coupons.length === 0 && (
              <tr>
                <td colSpan={8} className="text-center py-16 text-ink-muted text-sm">
                  <p>No coupons yet</p>
                  <p className="text-xs mt-1">Click &quot;New Coupon&quot; to create your first discount code.</p>
                </td>
              </tr>
            )}
            {coupons.map((c) => (
              <tr key={c.id} className="hover:bg-hover/60 transition-colors">
                <Td>
                  <div className="flex items-center gap-2">
                    {c.active && <span className="w-1.5 h-1.5 rounded-full bg-ok shrink-0" />}
                    <span className="text-xs font-mono font-medium text-ink">{c.code}</span>
                  </div>
                </Td>
                <Td>
                  <div className="text-xs text-ink">{c.name}</div>
                  {c.description && <div className="text-[10px] text-ink-muted">{c.description}</div>}
                </Td>
                <Td>
                  <Badge tone={c.discount_type === "percentage" ? "amber" : "blue"}>{fmtDiscount(c)}</Badge>
                </Td>
                <Td className="text-[10px] text-ink-muted">
                  {c.applicable_plans && c.applicable_plans.length
                    ? c.applicable_plans.map((pid: string) => planNames[pid] || pid).join(", ")
                    : "All plans"}
                </Td>
                <Td className="text-xs text-ink-muted">
                  {c.total_redemptions}
                  {c.max_redemptions ? ` / ${c.max_redemptions}` : ""}
                </Td>
                <Td className="text-[10px] text-ink-muted">
                  {c.valid_from ? new Date(c.valid_from).toLocaleDateString() : "—"}
                  <span className="mx-1">to</span>
                  {c.valid_until ? new Date(c.valid_until).toLocaleDateString() : "∞"}
                </Td>
                <Td>
                  <button type="button" onClick={() => handleToggle(c.id)} title="Toggle status">
                    <Badge tone={c.active ? "green" : "gray"}>{c.active ? "Active" : "Inactive"}</Badge>
                  </button>
                </Td>
                <Td>
                  <div className="flex gap-1.5">
                    {canUpdate && <Button size="sm" variant="ghost" onClick={() => openEdit(c)}>Edit</Button>}
                    {canDelete && <Button size="sm" variant="danger" onClick={() => setDeleteTarget({ id: c.id, name: c.code })}>Delete</Button>}
                  </div>
                </Td>
              </tr>
            ))}
          </Table>
        </Card>

        {/* Create / Edit Modal */}
        <Modal open={!!editing} onClose={() => setEditing(null)}
          title={editing === "new" ? "Create Coupon" : "Edit Coupon"}>
          {editing && (
            <div className="space-y-4 text-sm">
              {/* Section: Basic Info */}
              <div>
                <div className="text-[10px] uppercase tracking-wider text-ink-muted font-semibold mb-2">Basic Info</div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-[10px] text-ink-soft mb-1">
                      Code <span className="text-danger">*</span>
                    </label>
                    <input
                      className={`w-full h-8 px-2.5 rounded-lg bg-input border text-xs text-ink outline-none transition-colors font-mono uppercase ${
                        fieldErrors.code ? "border-danger" : "border-line focus:border-brand-500"
                      }`}
                      value={form.code}
                      onChange={(e) => { setForm({ ...form, code: e.target.value }); setFieldErrors({ ...fieldErrors, code: "" }); }}
                      placeholder="e.g. SAVE20" />
                    {fieldErrors.code && <p className="text-[10px] text-danger mt-0.5">{fieldErrors.code}</p>}
                  </div>
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
                      placeholder="e.g. Summer Sale" />
                    {fieldErrors.name && <p className="text-[10px] text-danger mt-0.5">{fieldErrors.name}</p>}
                  </div>
                </div>
                <div className="mt-3">
                  <label className="block text-[10px] text-ink-soft mb-1">Description</label>
                  <textarea
                    className="w-full h-16 px-2.5 py-1.5 rounded-lg bg-input border border-line text-xs text-ink outline-none focus:border-brand-500 transition-colors resize-none"
                    value={form.description}
                    onChange={(e) => setForm({ ...form, description: e.target.value })}
                    placeholder="Optional description shown to clients" />
                </div>
              </div>

              {/* Section: Discount */}
              <div>
                <div className="text-[10px] uppercase tracking-wider text-ink-muted font-semibold mb-2">Discount</div>
                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <label className="block text-[10px] text-ink-soft mb-1">
                      Type <span className="text-danger">*</span>
                    </label>
                    <select
                      className={`w-full h-8 px-2.5 rounded-lg bg-input border text-xs text-ink outline-none transition-colors ${
                        fieldErrors.discount_type ? "border-danger" : "border-line focus:border-brand-500"
                      }`}
                      value={form.discount_type}
                      onChange={(e) => { setForm({ ...form, discount_type: e.target.value }); setFieldErrors({ ...fieldErrors, discount_type: "" }); }}>
                      <option value="percentage">Percentage (%)</option>
                      <option value="fixed_amount">Fixed Amount</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-[10px] text-ink-soft mb-1">
                      Value <span className="text-danger">*</span>
                    </label>
                    <input type="number" step="0.01"
                      className={`w-full h-8 px-2.5 rounded-lg bg-input border text-xs text-ink outline-none transition-colors ${
                        fieldErrors.discount_value ? "border-danger" : "border-line focus:border-brand-500"
                      }`}
                      value={form.discount_value}
                      onChange={(e) => { setForm({ ...form, discount_value: e.target.value }); setFieldErrors({ ...fieldErrors, discount_value: "" }); }} />
                    {fieldErrors.discount_value && <p className="text-[10px] text-danger mt-0.5">{fieldErrors.discount_value}</p>}
                  </div>
                  <div>
                    <label className="block text-[10px] text-ink-soft mb-1">Currency</label>
                    <select
                      className={`w-full h-8 px-2.5 rounded-lg bg-input border text-xs text-ink outline-none transition-colors ${
                        form.discount_type === "fixed_amount" && fieldErrors.currency ? "border-danger" : "border-line focus:border-brand-500"
                      }`}
                      value={form.currency}
                      disabled={form.discount_type !== "fixed_amount"}
                      onChange={(e) => { setForm({ ...form, currency: e.target.value }); setFieldErrors({ ...fieldErrors, currency: "" }); }}>
                      {VALID_CURRENCIES.map((cur) => <option key={cur} value={cur}>{cur}</option>)}
                    </select>
                    {form.discount_type === "fixed_amount" && fieldErrors.currency && <p className="text-[10px] text-danger mt-0.5">{fieldErrors.currency}</p>}
                  </div>
                </div>
              </div>

              {/* Section: Limits */}
              <div>
                <div className="text-[10px] uppercase tracking-wider text-ink-muted font-semibold mb-2">Limits</div>
                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <label className="block text-[10px] text-ink-soft mb-1">Max Redemptions</label>
                    <input type="number"
                      className={`w-full h-8 px-2.5 rounded-lg bg-input border text-xs text-ink outline-none transition-colors ${
                        fieldErrors.max_redemptions ? "border-danger" : "border-line focus:border-brand-500"
                      }`}
                      value={form.max_redemptions}
                      onChange={(e) => { setForm({ ...form, max_redemptions: e.target.value }); setFieldErrors({ ...fieldErrors, max_redemptions: "" }); }}
                      placeholder="Unlimited" />
                    {fieldErrors.max_redemptions && <p className="text-[10px] text-danger mt-0.5">{fieldErrors.max_redemptions}</p>}
                  </div>
                  <div>
                    <label className="block text-[10px] text-ink-soft mb-1">Max Per User</label>
                    <input type="number"
                      className={`w-full h-8 px-2.5 rounded-lg bg-input border text-xs text-ink outline-none transition-colors ${
                        fieldErrors.max_per_user ? "border-danger" : "border-line focus:border-brand-500"
                      }`}
                      value={form.max_per_user}
                      onChange={(e) => { setForm({ ...form, max_per_user: e.target.value }); setFieldErrors({ ...fieldErrors, max_per_user: "" }); }} />
                    {fieldErrors.max_per_user && <p className="text-[10px] text-danger mt-0.5">{fieldErrors.max_per_user}</p>}
                  </div>
                  <div>
                    <label className="block text-[10px] text-ink-soft mb-1">Min Subscription Value</label>
                    <input type="number" step="0.01"
                      className="w-full h-8 px-2.5 rounded-lg bg-input border border-line text-xs text-ink outline-none focus:border-brand-500 transition-colors"
                      value={form.min_subscription_value}
                      onChange={(e) => setForm({ ...form, min_subscription_value: e.target.value })}
                      placeholder="Optional" />
                  </div>
                </div>
              </div>

              {/* Section: Applicable Plans */}
              <div>
                <div className="text-[10px] uppercase tracking-wider text-ink-muted font-semibold mb-2">Applicable Plans</div>
                <div className="flex flex-wrap gap-2">
                  {plans.length === 0 && <span className="text-xs text-ink-muted">No plans available</span>}
                  {plans.map((pl) => {
                    const sel = Array.isArray(form.applicable_plans) && form.applicable_plans.includes(pl.id);
                    return (
                      <button key={pl.id} type="button" onClick={() => togglePlan(pl.id)}
                        className={`px-2.5 py-1 rounded-full text-[10px] border transition-colors ${
                          sel ? "bg-brand-500/15 border-brand-500 text-brand-500" : "bg-input border-line text-ink-muted hover:border-brand-500"
                        }`}>
                        {pl.name}
                      </button>
                    );
                  })}
                  <span className="text-[10px] text-ink-muted self-center">(none selected = all plans)</span>
                </div>
              </div>

              {/* Section: Schedule */}
              <div>
                <div className="text-[10px] uppercase tracking-wider text-ink-muted font-semibold mb-2">Schedule</div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-[10px] text-ink-soft mb-1">Valid From</label>
                    <input type="date"
                      className="w-full h-8 px-2.5 rounded-lg bg-input border border-line text-xs text-ink outline-none focus:border-brand-500 transition-colors"
                      value={form.valid_from} onChange={(e) => setForm({ ...form, valid_from: e.target.value })} />
                  </div>
                  <div>
                    <label className="block text-[10px] text-ink-soft mb-1">Valid Until</label>
                    <input type="date"
                      className={`w-full h-8 px-2.5 rounded-lg bg-input border text-xs text-ink outline-none transition-colors ${
                        fieldErrors.valid_until ? "border-danger" : "border-line focus:border-brand-500"
                      }`}
                      value={form.valid_until} onChange={(e) => { setForm({ ...form, valid_until: e.target.value }); setFieldErrors({ ...fieldErrors, valid_until: "" }); }} />
                    {fieldErrors.valid_until && <p className="text-[10px] text-danger mt-0.5">{fieldErrors.valid_until}</p>}
                  </div>
                </div>
              </div>

              {/* Active toggle */}
              <div className="flex items-center gap-2">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" checked={form.active}
                    onChange={(e) => setForm({ ...form, active: e.target.checked })}
                    className="accent-brand-500" />
                  <span className="text-xs text-ink-soft">Active</span>
                </label>
              </div>

              {/* Actions */}
              <div className="flex justify-end gap-2 pt-3 border-t border-line">
                <Button size="sm" variant="ghost" type="button" onClick={() => setEditing(null)}>Cancel</Button>
                <Button size="sm" type="button" onClick={handleSave} loading={saving}>
                  {editing === "new" ? "Create Coupon" : "Save Changes"}
                </Button>
              </div>
            </div>
          )}
        </Modal>

        <ConfirmDialog
          open={!!deleteTarget}
          title="Delete coupon"
          description={`Delete "${deleteTarget?.name}"? This deactivates the coupon and preserves redemption history.`}
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