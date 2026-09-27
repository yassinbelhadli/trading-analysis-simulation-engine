"use client";

import { useEffect, useState, useCallback } from "react";
import OwnerPermissionGuard from "@/components/auth/owner_permission_guard";
import {
  listPlans, createPlan, updatePlan, deletePlan, restoreDefaultPlans,
  listCoupons, createCoupon, updateCoupon, deleteCoupon, toggleCoupon,
  listSubscriptions, listPayments, cancelSubscription,
} from "@/lib/api";
import { PageHeader, Card, Table, Td, Badge, Button, Skeleton, EmptyState, StatCard, type BadgeTone } from "@ds/components/ui";
import { Modal, ConfirmDialog } from "@ds/components/Modal";
import { Icon, type IconName } from "@ds/components/Icon";
import { parseApiError } from "@/lib/errors";
import { formatPrice, getPlanPrice } from "@/lib/currency";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
type BillingTab = "plans" | "coupons" | "subscriptions" | "payments";

interface PlanDef {
  id: string;
  name: string;
  price_usd: number | null;
  price_eur: number | null;
  price_mad: number | null;
  duration_days: number | null;
  features_json: string | null;
  description: string | null;
  badge: string | null;
  display_order: number;
  on_sale: boolean;
  is_archived: boolean;
  subscriber_count: number;
  created_at: string | null;
}

interface CouponDef {
  id: string;
  code: string;
  name: string;
  description: string | null;
  discount_type: "percentage" | "fixed_amount";
  discount_value: number;
  currency: string | null;
  valid_from: string | null;
  valid_until: string | null;
  max_redemptions: number | null;
  max_per_user: number;
  min_subscription_value: number | null;
  applicable_plans: string[] | null;
  active: boolean;
  total_redemptions: number;
  total_discount_granted: number;
  created_at: string | null;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
const inputCls = "w-full px-2 py-1.5 rounded-lg bg-input border border-line text-xs text-ink focus:outline-none focus:border-brand-500";
const CURRENCIES = ["USD", "EUR", "MAD"] as const;

function payTone(status?: string): BadgeTone {
  if (status === "completed" || status === "succeeded") return "green";
  if (status === "pending") return "amber";
  if (status === "failed" || status === "cancelled" || status === "refunded") return "red";
  return "gray";
}

function parseFeatures(json: string | null): Record<string, boolean> {
  if (!json) return {};
  try { return JSON.parse(json); } catch { return {}; }
}

function featuresToJSON(features: Record<string, boolean>): string {
  return JSON.stringify(features);
}

function computePaymentStats(payments: any[]) {
  const now = new Date();
  const today = now.toISOString().split("T")[0];
  const monthStart = new Date(now.getFullYear(), now.getMonth(), 1).toISOString();

  const pending = payments.filter((p) =>
    ["PENDING_VERIFICATION", "AWAITING_PAYMENT", "TRANSACTION_DETECTED", "CONFIRMING", "MANUAL_REVIEW"].includes(p.status)
  ).length;
  const paidToday = payments.filter((p) => p.status === "PAID" && p.paid_at?.startsWith(today)).length;
  const paidMonth = payments.filter((p) => p.status === "PAID" && p.paid_at >= monthStart).length;
  const failed = payments.filter((p) => p.status === "FAILED").length;
  const revenueMonth = payments
    .filter((p) => p.status === "PAID" && p.paid_at >= monthStart)
    .reduce((sum, p) => sum + parseFloat(p.final_amount || "0"), 0);

  return { pending, paidToday, paidMonth, failed, revenueMonth };
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function BillingPage() {
  // Data
  const [plans, setPlans] = useState<PlanDef[]>([]);
  const [coupons, setCoupons] = useState<CouponDef[]>([]);
  const [subs, setSubs] = useState<any[]>([]);
  const [payments, setPayments] = useState<any[]>([]);
  const [subTotal, setSubTotal] = useState(0);
  const [payTotal, setPayTotal] = useState(0);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<BillingTab>("plans");

  // Plan editing
  const [editingPlan, setEditingPlan] = useState<PlanDef | null>(null);
  const [creatingPlan, setCreatingPlan] = useState(false);
  const [planForm, setPlanForm] = useState<any>({});
  const [confirmDeletePlan, setConfirmDeletePlan] = useState<PlanDef | null>(null);
  const [confirmRestore, setConfirmRestore] = useState(false);

  // Coupon editing
  const [editingCoupon, setEditingCoupon] = useState<CouponDef | null>(null);
  const [creatingCoupon, setCreatingCoupon] = useState(false);
  const [couponForm, setCouponForm] = useState<any>({});
  const [confirmDeleteCoupon, setConfirmDeleteCoupon] = useState<CouponDef | null>(null);

  // Subscription
  const [confirmCancelSub, setConfirmCancelSub] = useState<any>(null);

  const [saving, setSaving] = useState(false);

  // ---------------------------------------------------------------------------
  // Load data
  // ---------------------------------------------------------------------------
  const load = useCallback(async () => {
    try {
      const [p, c, s, pay] = await Promise.all([
        listPlans(),
        listCoupons(),
        listSubscriptions("?limit=100"),
        listPayments("?limit=100"),
      ]);
      setPlans(p.items);
      setCoupons(c.items);
      setSubs(s.items);
      setSubTotal(s.total);
      setPayments(pay.items);
      setPayTotal(pay.total);
    } catch (e) {
      setError(parseApiError(e));
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // ---------------------------------------------------------------------------
  // Plan handlers
  // ---------------------------------------------------------------------------
  const emptyPlanForm = {
    name: "",
    price_usd: "",
    price_eur: "",
    price_mad: "",
    duration_days: "",
    description: "",
    badge: "",
    display_order: 0,
    on_sale: false,
    features: {} as Record<string, boolean>,
  };

  const openCreatePlan = () => {
    setPlanForm({ ...emptyPlanForm });
    setCreatingPlan(true);
  };

  const openEditPlan = (p: PlanDef) => {
    setPlanForm({
      name: p.name,
      price_usd: p.price_usd ?? "",
      price_eur: p.price_eur ?? "",
      price_mad: p.price_mad ?? "",
      duration_days: p.duration_days ?? "",
      description: p.description ?? "",
      badge: p.badge ?? "",
      display_order: p.display_order ?? 0,
      on_sale: p.on_sale ?? false,
      features: parseFeatures(p.features_json),
    });
    setEditingPlan(p);
  };

  const handleSavePlan = async () => {
    setSaving(true);
    setError("");
    try {
      const body: any = { ...planForm };
      // Clean numeric fields
      for (const k of ["price_usd", "price_eur", "price_mad", "duration_days", "display_order"]) {
        if (body[k] !== "" && body[k] !== null && body[k] !== undefined) {
          body[k] = Number(body[k]);
        } else {
          body[k] = null;
        }
      }
      body.features_json = body.features;
      delete body.features;

      if (creatingPlan) {
        await createPlan(body);
        setCreatingPlan(false);
      } else if (editingPlan) {
        await updatePlan(editingPlan.id, body);
        setEditingPlan(null);
      }
      load();
    } catch (e) {
      setError(parseApiError(e));
    } finally {
      setSaving(false);
    }
  };

  const handleDeletePlan = async (p: PlanDef) => {
    setSaving(true);
    try {
      await deletePlan(p.id);
      setConfirmDeletePlan(null);
      load();
    } catch (e) {
      setError(parseApiError(e));
    } finally {
      setSaving(false);
    }
  };

  const handleArchivePlan = async (p: PlanDef) => {
    try {
      await updatePlan(p.id, { is_archived: !p.is_archived });
      load();
    } catch (e) {
      setError(parseApiError(e));
    }
  };

  const handleRestore = async () => {
    setSaving(true);
    try {
      await restoreDefaultPlans();
      setConfirmRestore(false);
      load();
    } catch (e) {
      setError(parseApiError(e));
    } finally {
      setSaving(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Coupon handlers
  // ---------------------------------------------------------------------------
  const emptyCouponForm = {
    code: "",
    name: "",
    description: "",
    discount_type: "percentage",
    discount_value: "",
    currency: "USD",
    valid_from: "",
    valid_until: "",
    max_redemptions: "",
    max_per_user: 1,
    min_subscription_value: "",
    active: true,
  };

  const openCreateCoupon = () => {
    setCouponForm({ ...emptyCouponForm });
    setCreatingCoupon(true);
  };

  const openEditCoupon = (c: CouponDef) => {
    setCouponForm({
      code: c.code,
      name: c.name,
      description: c.description ?? "",
      discount_type: c.discount_type,
      discount_value: c.discount_value ?? "",
      currency: c.currency ?? "USD",
      valid_from: c.valid_from ? c.valid_from.slice(0, 16) : "",
      valid_until: c.valid_until ? c.valid_until.slice(0, 16) : "",
      max_redemptions: c.max_redemptions ?? "",
      max_per_user: c.max_per_user ?? 1,
      min_subscription_value: c.min_subscription_value ?? "",
      active: c.active,
    });
    setEditingCoupon(c);
  };

  const handleSaveCoupon = async () => {
    setSaving(true);
    setError("");
    try {
      const body: any = { ...couponForm };
      // Clean numeric fields
      for (const k of ["discount_value", "min_subscription_value"]) {
        if (body[k] !== "" && body[k] !== null && body[k] !== undefined) {
          body[k] = Number(body[k]);
        } else {
          body[k] = null;
        }
      }
      for (const k of ["max_redemptions", "max_per_user"]) {
        if (body[k] !== "" && body[k] !== null && body[k] !== undefined) {
          body[k] = Number(body[k]);
        } else {
          body[k] = null;
        }
      }
      // Clean datetime fields
      for (const k of ["valid_from", "valid_until"]) {
        body[k] = body[k] || null;
      }
      // percentage coupons don't use currency
      if (body.discount_type === "percentage") {
        body.currency = null;
      }

      if (creatingCoupon) {
        await createCoupon(body);
        setCreatingCoupon(false);
      } else if (editingCoupon) {
        await updateCoupon(editingCoupon.id, body);
        setEditingCoupon(null);
      }
      load();
    } catch (e) {
      setError(parseApiError(e));
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteCoupon = async (c: CouponDef) => {
    setSaving(true);
    try {
      await deleteCoupon(c.id);
      setConfirmDeleteCoupon(null);
      load();
    } catch (e) {
      setError(parseApiError(e));
    } finally {
      setSaving(false);
    }
  };

  const handleToggleCoupon = async (c: CouponDef) => {
    try {
      await toggleCoupon(c.id);
      load();
    } catch (e) {
      setError(parseApiError(e));
    }
  };

  // ---------------------------------------------------------------------------
  // Subscription handlers
  // ---------------------------------------------------------------------------
  const handleCancelSub = async (id: string) => {
    setSaving(true);
    try {
      await cancelSubscription(id);
      setConfirmCancelSub(null);
      load();
    } catch (e) {
      setError(parseApiError(e));
    } finally {
      setSaving(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Tabs
  // ---------------------------------------------------------------------------
  const TABS: { key: BillingTab; label: string; icon: IconName }[] = [
    { key: "plans", label: "Plans", icon: "tag" },
    { key: "coupons", label: "Coupons", icon: "key" },
    { key: "subscriptions", label: "Subscriptions", icon: "users" },
    { key: "payments", label: "Payments", icon: "receipt" },
  ];

  return (
    <OwnerPermissionGuard permission="subscriptions.read">
      <div className="flex flex-col gap-5 max-w-6xl">
        <PageHeader
          title="Billing Oversight"
          subtitle="Plans, coupons, subscriptions and the payments ledger."
          actions={
            <div className="flex gap-2">
              {TABS.map((t) => (
                <Button
                  key={t.key}
                  size="sm"
                  variant={tab === t.key ? "primary" : "secondary"}
                  icon={t.icon}
                  onClick={() => setTab(t.key)}
                >
                  {t.label}
                </Button>
              ))}
            </div>
          }
        />

        {error && (
          <div className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
            {error}
          </div>
        )}

        {/* Payment Overview Stats */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          <StatCard
            label="Pending Verification"
            value={computePaymentStats(payments).pending}
            icon="clock"
            tone="amber"
            mono
          />
          <StatCard
            label="Paid Today"
            value={computePaymentStats(payments).paidToday}
            icon="check-circle"
            tone="green"
            mono
          />
          <StatCard
            label="Paid This Month"
            value={computePaymentStats(payments).paidMonth}
            icon="receipt"
            tone="blue"
            mono
          />
          <StatCard
            label="Failed"
            value={computePaymentStats(payments).failed}
            icon="alert-triangle"
            tone="red"
            mono
          />
          <StatCard
            label="Revenue This Month"
            value={`$${computePaymentStats(payments).revenueMonth.toFixed(2)}`}
            icon="dollar"
            tone="green"
            mono
          />
        </div>

        {/* ================================================================ */}
        {/* PLANS TAB                                                        */}
        {/* ================================================================ */}
        {tab === "plans" && (
          <>
            <div className="flex justify-end gap-2">
              <Button size="sm" variant="primary" icon="plus" onClick={openCreatePlan}>
                Create Plan
              </Button>
              <Button size="sm" variant="secondary" icon="refresh" onClick={() => setConfirmRestore(true)}>
                Restore Defaults
              </Button>
            </div>

            {!plans.length && !error ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-64 rounded-xl" />)}
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {plans.map((p) => {
                  const features = parseFeatures(p.features_json);
                  return (
                    <div key={p.id} className={`bg-raised border rounded-xl p-5 relative flex flex-col ${
                      p.is_archived ? "border-line opacity-60" : "border-line"
                    }`}>
                      {p.badge && (
                        <div className="absolute -top-2.5 left-3 bg-brand-500 text-white text-[10px] font-bold px-2.5 py-0.5 rounded-full">
                          {p.badge}
                        </div>
                      )}
                      <div className="flex items-center justify-between mb-1">
                        <div className="text-base font-bold text-ink">{p.name}</div>
                        <Badge tone={p.is_archived ? "gray" : "green"}>
                          {p.is_archived ? "Archived" : "Active"}
                        </Badge>
                      </div>

                      {p.is_archived && (
                        <div className="text-[10px] text-ink-muted mb-1 italic">Archived</div>
                      )}

                      {/* Multi-currency prices */}
                      <div className="flex flex-col gap-1 mb-2">
                        {p.price_usd != null && (
                          <div className="text-lg font-bold text-ink font-display">
                            {formatPrice(p.price_usd, "USD")}
                            {p.duration_days ? <span className="text-xs text-ink-muted font-normal"> / {p.duration_days}d</span> : null}
                          </div>
                        )}
                        <div className="flex gap-3 text-xs text-ink-muted">
                          {p.price_eur != null && <span>€{p.price_eur}</span>}
                          {p.price_mad != null && <span>{p.price_mad} MAD</span>}
                        </div>
                      </div>

                      {p.description && (
                        <div className="text-[11px] text-ink-soft mb-2">{p.description}</div>
                      )}

                      <div className="text-[10px] text-ink-muted mb-2">
                        {p.subscriber_count} subscriber{p.subscriber_count === 1 ? "" : "s"}
                      </div>

                      {Object.keys(features).length > 0 && (
                        <div className="space-y-1 flex-1 mb-3">
                          {Object.entries(features).slice(0, 5).map(([k, v]) => (
                            <div key={k} className={`text-[10px] flex items-center gap-1.5 ${v ? "text-brand-400" : "text-ink-muted"}`}>
                              <Icon name={v ? "check" : "x-circle"} className="h-3 w-3" />
                              {k.replace(/_/g, " ")}
                            </div>
                          ))}
                          {Object.keys(features).length > 5 && (
                            <div className="text-[10px] text-ink-muted">+{Object.keys(features).length - 5} more</div>
                          )}
                        </div>
                      )}

                      <div className="flex flex-wrap gap-1.5 pt-2 border-t border-line/60">
                        <Button size="sm" variant="ghost" icon="edit" onClick={() => openEditPlan(p)}>
                          Edit
                        </Button>
                        <Button size="sm" variant="ghost" icon="upload" onClick={() => handleArchivePlan(p)}>
                          {p.is_archived ? "Unarchive" : "Archive"}
                        </Button>
                        <Button size="sm" variant="danger" icon="trash" onClick={() => setConfirmDeletePlan(p)}>
                          Delete
                        </Button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </>
        )}

        {/* ================================================================ */}
        {/* COUPONS TAB                                                      */}
        {/* ================================================================ */}
        {tab === "coupons" && (
          <>
            <div className="flex justify-end">
              <Button size="sm" variant="primary" icon="plus" onClick={openCreateCoupon}>
                Create Coupon
              </Button>
            </div>

            {coupons.length === 0 && !error ? (
              <EmptyState
                icon="key"
                title="No coupons yet"
                description="Create a coupon to offer discounts on subscriptions."
              />
            ) : (
              <Card title={`Coupons (${coupons.length})`} icon="key" bodyClassName="p-0">
                <Table columns={["Code", "Name", "Type", "Value", "Currency", "Redemptions", "Status", "Actions"]}>
                  {coupons.map((c) => (
                    <tr key={c.id} className="hover:bg-hover transition-colors">
                      <Td mono className="text-xs font-semibold text-ink">{c.code}</Td>
                      <Td className="text-xs text-ink-soft">{c.name}</Td>
                      <Td>
                        <Badge tone={c.discount_type === "percentage" ? "blue" : "green"}>
                          {c.discount_type === "percentage" ? "%" : "Fixed"}
                        </Badge>
                      </Td>
                      <Td mono className="text-xs">
                        {c.discount_type === "percentage" ? `${c.discount_value}%` : formatPrice(c.discount_value, c.currency || "USD")}
                      </Td>
                      <Td className="text-xs text-ink-muted">{c.currency || "Any"}</Td>
                      <Td mono className="text-xs text-ink-soft">
                        {c.total_redemptions}{c.max_redemptions ? ` / ${c.max_redemptions}` : ""}
                      </Td>
                      <Td>
                        <Badge tone={c.active ? "green" : "gray"}>{c.active ? "Active" : "Inactive"}</Badge>
                      </Td>
                      <Td>
                        <div className="flex gap-1">
                          <Button size="sm" variant="ghost" icon="edit" onClick={() => openEditCoupon(c)} />
                          <Button size="sm" variant="ghost" icon={c.active ? "pause" : "play"} onClick={() => handleToggleCoupon(c)} />
                          <Button size="sm" variant="danger" icon="trash" onClick={() => setConfirmDeleteCoupon(c)} />
                        </div>
                      </Td>
                    </tr>
                  ))}
                </Table>
              </Card>
            )}
          </>
        )}

        {/* ================================================================ */}
        {/* SUBSCRIPTIONS TAB                                                */}
        {/* ================================================================ */}
        {tab === "subscriptions" && (
          <Card title={`Subscriptions (${subTotal})`} icon="credit-card" bodyClassName="p-0">
            {subs.length === 0 && !error ? (
              <EmptyState
                icon="credit-card"
                title="No subscriptions yet"
                description="Subscriptions will appear here once users start subscribing."
              />
            ) : (
              <Table columns={["User", "Plan", "Cycle", "Price", "Currency", "Start", "End", "Status", "Actions"]}>
                {subs.map((s) => (
                  <tr key={s.id} className="hover:bg-hover transition-colors">
                    <Td mono className="text-xs text-ink-soft">{s.user_id?.slice(0, 8)}</Td>
                    <Td>
                      <Badge tone="blue">{s.plan_name || s.plan}</Badge>
                    </Td>
                    <Td className="text-xs text-ink-soft">{s.billing_cycle || "—"}</Td>
                    <Td mono className="text-xs">{formatPrice(s.plan_price_paid, s.plan_currency)}</Td>
                    <Td className="text-xs text-ink-muted">{s.plan_currency || "USD"}</Td>
                    <Td className="text-xs text-ink-muted">{s.start_date ? new Date(s.start_date).toLocaleDateString() : "—"}</Td>
                    <Td className="text-xs text-ink-muted">{s.end_date ? new Date(s.end_date).toLocaleDateString() : "—"}</Td>
                    <Td>
                      <Badge tone={s.active ? "green" : "gray"}>{s.active ? "active" : "cancelled"}</Badge>
                    </Td>
                    <Td>
                      {s.active && (
                        <Button size="sm" variant="danger" icon="trash" onClick={() => setConfirmCancelSub(s)}>
                          Cancel
                        </Button>
                      )}
                    </Td>
                  </tr>
                ))}
              </Table>
            )}
          </Card>
        )}

        {/* ================================================================ */}
        {/* PAYMENTS TAB                                                     */}
        {/* ================================================================ */}
        {tab === "payments" && (
          <Card title={`Payment History (${payTotal})`} icon="receipt" bodyClassName="p-0">
            {payments.length === 0 && !error ? (
              <EmptyState
                icon="receipt"
                title="No payments yet"
                description="Payments will appear here once users start subscribing."
              />
            ) : (
              <Table columns={["Date", "User", "Action", "Amount", "Currency", "Status"]}>
                {payments.map((p) => (
                  <tr key={p.id} className="hover:bg-hover transition-colors">
                    <Td className="text-xs text-ink-muted whitespace-nowrap">
                      {p.timestamp ? new Date(p.timestamp).toLocaleString() : "—"}
                    </Td>
                    <Td mono className="text-xs text-ink-soft">{p.user_id?.slice(0, 8) || "—"}</Td>
                    <Td className="text-xs text-ink">{p.action}</Td>
                    <Td mono className="text-xs">{formatPrice(p.amount, p.currency)}</Td>
                    <Td className="text-xs text-ink-soft">{p.currency || "USD"}</Td>
                    <Td>
                      <Badge tone={payTone(p.status)}>{p.status}</Badge>
                    </Td>
                  </tr>
                ))}
              </Table>
            )}
          </Card>
        )}

        {/* ================================================================ */}
        {/* PLAN CREATE/EDIT MODAL                                           */}
        {/* ================================================================ */}
        <Modal
          open={creatingPlan || !!editingPlan}
          onClose={() => { setCreatingPlan(false); setEditingPlan(null); }}
          title={creatingPlan ? "Create Plan" : `Edit Plan: ${editingPlan?.name || ""}`}
          icon="info"
          size="lg"
        >
          <div className="space-y-4 text-sm">
            {/* Name + Badge + Duration */}
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="block text-xs font-medium text-ink-soft mb-1">Plan Name *</label>
                <input className={inputCls} value={planForm.name || ""} onChange={(e) => setPlanForm({ ...planForm, name: e.target.value })} placeholder="e.g. Starter" />
              </div>
              <div>
                <label className="block text-xs font-medium text-ink-soft mb-1">Badge Label</label>
                <input className={inputCls} value={planForm.badge || ""} onChange={(e) => setPlanForm({ ...planForm, badge: e.target.value })} placeholder="e.g. Popular" />
              </div>
              <div>
                <label className="block text-xs font-medium text-ink-soft mb-1">Duration (days)</label>
                <input type="number" className={inputCls} value={planForm.duration_days ?? ""} onChange={(e) => setPlanForm({ ...planForm, duration_days: e.target.value })} placeholder="e.g. 30" />
              </div>
            </div>

            {/* Multi-currency prices */}
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="block text-xs font-medium text-ink-soft mb-1">Price USD ($)</label>
                <input type="number" step="0.01" className={inputCls} value={planForm.price_usd ?? ""} onChange={(e) => setPlanForm({ ...planForm, price_usd: e.target.value })} placeholder="0.00" />
              </div>
              <div>
                <label className="block text-xs font-medium text-ink-soft mb-1">Price EUR (€)</label>
                <input type="number" step="0.01" className={inputCls} value={planForm.price_eur ?? ""} onChange={(e) => setPlanForm({ ...planForm, price_eur: e.target.value })} placeholder="0.00" />
              </div>
              <div>
                <label className="block text-xs font-medium text-ink-soft mb-1">Price MAD (MAD)</label>
                <input type="number" step="0.01" className={inputCls} value={planForm.price_mad ?? ""} onChange={(e) => setPlanForm({ ...planForm, price_mad: e.target.value })} placeholder="0.00" />
              </div>
            </div>

            {/* Description */}
            <div>
              <label className="block text-xs font-medium text-ink-soft mb-1">Description</label>
              <textarea
                className={inputCls}
                rows={2}
                value={planForm.description || ""}
                onChange={(e) => setPlanForm({ ...planForm, description: e.target.value })}
                placeholder="Short description of what this plan includes"
              />
            </div>

            {/* Display order + On Sale */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-ink-soft mb-1">Display Order</label>
                <input type="number" className={inputCls} value={planForm.display_order ?? 0} onChange={(e) => setPlanForm({ ...planForm, display_order: Number(e.target.value) })} />
              </div>
              <div className="flex items-center gap-3 pt-5">
                <label className="flex items-center gap-1.5 cursor-pointer">
                  <input type="checkbox" checked={planForm.on_sale ?? false} onChange={(e) => setPlanForm({ ...planForm, on_sale: e.target.checked })} className="accent-brand-500" />
                  <span className="text-xs text-ink">On Sale</span>
                </label>
              </div>
            </div>

            {/* Features */}
            <div>
              <label className="block text-xs font-medium text-ink-soft mb-2">Features</label>
              <div className="flex flex-wrap gap-2">
                {["xauusd", "nas100", "btcusd", "multi_account", "telegram_alerts", "analytics", "api_access", "priority_support", "custom_symbols", "news_filter"].map((k) => (
                  <button
                    key={k}
                    type="button"
                    onClick={() => setPlanForm((f: any) => ({ ...f, features: { ...f.features, [k]: !f.features[k] } }))}
                    className={`flex items-center gap-1.5 text-xs px-2 py-1 rounded-lg border transition-colors ${
                      planForm.features?.[k]
                        ? "border-brand-500/50 bg-brand-tint text-brand-400"
                        : "border-line text-ink-soft hover:border-line-strong"
                    }`}
                  >
                    <Icon name={planForm.features?.[k] ? "check" : "x-circle"} className="h-3.5 w-3.5" />
                    {k.replace(/_/g, " ")}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <Button variant="ghost" onClick={() => { setCreatingPlan(false); setEditingPlan(null); }}>Cancel</Button>
              <Button onClick={handleSavePlan} loading={saving}>{saving ? "Saving..." : creatingPlan ? "Create Plan" : "Save"}</Button>
            </div>
          </div>
        </Modal>

        {/* ================================================================ */}
        {/* COUPON CREATE/EDIT MODAL                                         */}
        {/* ================================================================ */}
        <Modal
          open={creatingCoupon || !!editingCoupon}
          onClose={() => { setCreatingCoupon(false); setEditingCoupon(null); }}
          title={creatingCoupon ? "Create Coupon" : `Edit Coupon: ${editingCoupon?.code || ""}`}
          icon="info"
          size="lg"
        >
          <div className="space-y-4 text-sm">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-ink-soft mb-1">Code *</label>
                <input className={inputCls} value={couponForm.code || ""} onChange={(e) => setCouponForm({ ...couponForm, code: e.target.value.toUpperCase() })} placeholder="e.g. SUMMER20" />
                <p className="text-[10px] text-ink-muted mt-1">3-50 chars: A-Z, 0-9, _ or -</p>
              </div>
              <div>
                <label className="block text-xs font-medium text-ink-soft mb-1">Name *</label>
                <input className={inputCls} value={couponForm.name || ""} onChange={(e) => setCouponForm({ ...couponForm, name: e.target.value })} placeholder="e.g. Summer Sale" />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-ink-soft mb-1">Description</label>
              <input className={inputCls} value={couponForm.description || ""} onChange={(e) => setCouponForm({ ...couponForm, description: e.target.value })} />
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="block text-xs font-medium text-ink-soft mb-1">Discount Type *</label>
                <select className={inputCls} value={couponForm.discount_type} onChange={(e) => setCouponForm({ ...couponForm, discount_type: e.target.value })}>
                  <option value="percentage">Percentage (%)</option>
                  <option value="fixed_amount">Fixed Amount</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-ink-soft mb-1">
                  {couponForm.discount_type === "percentage" ? "Percentage (%)" : "Amount"}
                </label>
                <input type="number" step="0.01" className={inputCls} value={couponForm.discount_value ?? ""} onChange={(e) => setCouponForm({ ...couponForm, discount_value: e.target.value })} />
              </div>
              {couponForm.discount_type === "fixed_amount" && (
                <div>
                  <label className="block text-xs font-medium text-ink-soft mb-1">Currency</label>
                  <select className={inputCls} value={couponForm.currency} onChange={(e) => setCouponForm({ ...couponForm, currency: e.target.value })}>
                    {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
                  </select>
                </div>
              )}
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-ink-soft mb-1">Valid From</label>
                <input type="datetime-local" className={inputCls} value={couponForm.valid_from || ""} onChange={(e) => setCouponForm({ ...couponForm, valid_from: e.target.value })} />
              </div>
              <div>
                <label className="block text-xs font-medium text-ink-soft mb-1">Valid Until</label>
                <input type="datetime-local" className={inputCls} value={couponForm.valid_until || ""} onChange={(e) => setCouponForm({ ...couponForm, valid_until: e.target.value })} />
              </div>
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="block text-xs font-medium text-ink-soft mb-1">Max Redemptions</label>
                <input type="number" className={inputCls} value={couponForm.max_redemptions ?? ""} onChange={(e) => setCouponForm({ ...couponForm, max_redemptions: e.target.value })} placeholder="Unlimited" />
              </div>
              <div>
                <label className="block text-xs font-medium text-ink-soft mb-1">Max Per User</label>
                <input type="number" className={inputCls} value={couponForm.max_per_user ?? 1} onChange={(e) => setCouponForm({ ...couponForm, max_per_user: Number(e.target.value) })} />
              </div>
              <div>
                <label className="block text-xs font-medium text-ink-soft mb-1">Min Subscription Value</label>
                <input type="number" step="0.01" className={inputCls} value={couponForm.min_subscription_value ?? ""} onChange={(e) => setCouponForm({ ...couponForm, min_subscription_value: e.target.value })} placeholder="None" />
              </div>
            </div>

            <label className="flex items-center gap-1.5 cursor-pointer">
              <input type="checkbox" checked={couponForm.active ?? true} onChange={(e) => setCouponForm({ ...couponForm, active: e.target.checked })} className="accent-brand-500" />
              <span className="text-xs text-ink">Active</span>
            </label>

            <div className="flex justify-end gap-2 pt-2">
              <Button variant="ghost" onClick={() => { setCreatingCoupon(false); setEditingCoupon(null); }}>Cancel</Button>
              <Button onClick={handleSaveCoupon} loading={saving}>{saving ? "Saving..." : creatingCoupon ? "Create Coupon" : "Save"}</Button>
            </div>
          </div>
        </Modal>

        {/* ================================================================ */}
        {/* CONFIRM DIALOGS                                                  */}
        {/* ================================================================ */}
        <ConfirmDialog
          open={!!confirmDeletePlan}
          title="Delete plan"
          description={
            confirmDeletePlan
              ? `Permanently delete "${confirmDeletePlan.name}"? ${confirmDeletePlan.subscriber_count > 0 ? `This plan has ${confirmDeletePlan.subscriber_count} subscriber(s) — consider archiving instead.` : "This action cannot be undone."}`
              : undefined
          }
          confirmLabel="Delete"
          tone="danger"
          loading={saving}
          onConfirm={() => confirmDeletePlan && handleDeletePlan(confirmDeletePlan)}
          onCancel={() => setConfirmDeletePlan(null)}
        />

        <ConfirmDialog
          open={confirmRestore}
          title="Restore default plans"
          description="Restore all plans to their factory defaults? Custom pricing and features will be overwritten."
          confirmLabel="Restore Defaults"
          tone="danger"
          loading={saving}
          onConfirm={handleRestore}
          onCancel={() => setConfirmRestore(false)}
        />

        <ConfirmDialog
          open={!!confirmCancelSub}
          title="Cancel subscription"
          description={
            confirmCancelSub
              ? `Cancel the ${confirmCancelSub.plan_name || confirmCancelSub.plan} subscription for ${confirmCancelSub.user_id?.slice(0, 8)}? The client will lose plan access. This action is audited.`
              : undefined
          }
          confirmLabel="Cancel Subscription"
          tone="danger"
          loading={saving}
          onConfirm={() => confirmCancelSub && handleCancelSub(confirmCancelSub.id)}
          onCancel={() => setConfirmCancelSub(null)}
        />

        <ConfirmDialog
          open={!!confirmDeleteCoupon}
          title="Delete coupon"
          description={
            confirmDeleteCoupon
              ? `Deactivate coupon "${confirmDeleteCoupon.code}"? It will no longer be valid for new redemptions.`
              : undefined
          }
          confirmLabel="Deactivate"
          tone="danger"
          loading={saving}
          onConfirm={() => confirmDeleteCoupon && handleDeleteCoupon(confirmDeleteCoupon)}
          onCancel={() => setConfirmDeleteCoupon(null)}
        />
      </div>
    </OwnerPermissionGuard>
  );
}
