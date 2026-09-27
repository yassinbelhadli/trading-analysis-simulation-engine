"use client";

import { useEffect, useState, useCallback } from "react";
import OwnerPermissionGuard from "@/components/auth/owner_permission_guard";
import {
  listPaymentConfigs,
  updatePaymentConfig,
  createPaymentConfig,
  archivePaymentConfig,
  FIELD_TYPES,
  type FieldType,
  type PaymentConfig,
  type ClientFieldDef,
  type InfoBlock,
} from "@/lib/api";
import { PageHeader, Card, Table, Td, Badge, Button, Skeleton, EmptyState } from "@ds/components/ui";
import { Modal, ConfirmDialog } from "@ds/components/Modal";
import { parseApiError } from "@/lib/errors";

const inputCls = "w-full px-2 py-1.5 rounded-lg bg-input border border-line text-xs text-ink focus:outline-none focus:border-brand-500";
const selectCls = "w-full px-2 py-1.5 rounded-lg bg-input border border-line text-xs text-ink focus:outline-none focus:border-brand-500";

const emptyForm = {
  method_id: "",
  display_name: "",
  method_type: "manual" as "manual" | "automatic" | "manual_crypto",
  description: "",
  information: [] as InfoBlock[],
  client_fields: [] as ClientFieldDef[],
  receipt_required: true,
  beneficiary_name: "",
  account_rib: "",
  phone_number: "",
  branch: "",
  instructions: "",
  reference_instructions: "",
  reference_required: true,
  required_fields: "",
  optional_fields: "",
  wallet_address: "",
  network: "",
  expires_hours: 72,
  provider_name: "",
  currencies: "",
  gateway_status: "",
  is_active: true,
  display_order: 0,
};

type FormState = typeof emptyForm;

export default function PaymentMethodsPage() {
  const [configs, setConfigs] = useState<PaymentConfig[]>([]);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState<PaymentConfig | null>(null);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState<FormState>(emptyForm);
  const [saving, setSaving] = useState(false);
  const [removing, setRemoving] = useState<PaymentConfig | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await listPaymentConfigs();
      setConfigs(res.configs);
    } catch (e) {
      setError(parseApiError(e));
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const openEdit = (c: PaymentConfig) => {
    setForm({
      method_id: c.method_id,
      display_name: c.display_name,
      method_type: (c.method_type as FormState["method_type"]) || "manual",
      description: c.description ?? "",
      information: Array.isArray(c.information) ? c.information : [],
      client_fields: Array.isArray(c.client_fields) ? c.client_fields : [],
      receipt_required: c.receipt_required ?? true,
      beneficiary_name: c.beneficiary_name ?? "",
      account_rib: c.account_rib ?? "",
      phone_number: c.phone_number ?? "",
      branch: c.branch ?? "",
      instructions: c.instructions ?? "",
      reference_instructions: c.reference_instructions ?? "",
      reference_required: c.reference_required,
      required_fields: Array.isArray(c.required_fields) ? c.required_fields.join(", ") : "",
      optional_fields: Array.isArray(c.optional_fields) ? c.optional_fields.join(", ") : "",
      wallet_address: c.wallet_address ?? "",
      network: c.network ?? "",
      expires_hours: c.expires_hours ?? 72,
      provider_name: c.provider_name ?? "",
      currencies: Array.isArray(c.currencies) ? c.currencies.join(", ") : "",
      gateway_status: c.gateway_status ?? "",
      is_active: c.is_active,
      display_order: c.display_order,
    });
    setEditing(c);
  };

  const openCreate = () => {
    setForm({ ...emptyForm });
    setCreating(true);
  };

  // ---- Information blocks editor ----
  const updateInfo = (idx: number, patch: Partial<InfoBlock>) => {
    setForm((f) => ({
      ...f,
      information: f.information.map((b, i) => (i === idx ? { ...b, ...patch } : b)),
    }));
  };
  const addInfo = () => setForm((f) => ({ ...f, information: [...f.information, { label: "", value: "" }] }));
  const removeInfo = (idx: number) => setForm((f) => ({ ...f, information: f.information.filter((_, i) => i !== idx) }));

  // ---- Client fields editor ----
  const updateField = (idx: number, patch: Partial<ClientFieldDef>) => {
    setForm((f) => ({
      ...f,
      client_fields: f.client_fields.map((fd, i) => (i === idx ? { ...fd, ...patch } : fd)),
    }));
  };
  const addField = () => setForm((f) => ({
    ...f,
    client_fields: [...f.client_fields, { key: "", label: "", type: "text", required: true, placeholder: "", validation: "" }],
  }));
  const removeField = (idx: number) => setForm((f) => ({ ...f, client_fields: f.client_fields.filter((_, i) => i !== idx) }));

  const buildBody = (): Record<string, unknown> => {
    const body: Record<string, unknown> = {};
    const isManual = form.method_type === "manual";
    const isCrypto = form.method_type === "manual_crypto";
    const isAuto = form.method_type === "automatic";

    body.display_name = form.display_name;
    body.description = form.description.trim() || null;
    body.is_active = form.is_active;
    body.display_order = Number(form.display_order ?? 0);

    if (isManual || isCrypto) {
      body.information = form.information.filter((b) => b.label.trim() || b.value.trim());
      body.client_fields = form.client_fields.filter((fd) => fd.key.trim() || fd.label.trim());
      body.receipt_required = form.receipt_required;
      body.reference_required = form.reference_required ?? true;
      body.expires_hours = Math.max(1, Number(form.expires_hours ?? 72));
      const req = form.required_fields.split(",").map((s) => s.trim()).filter(Boolean);
      const opt = form.optional_fields.split(",").map((s) => s.trim()).filter(Boolean);
      body.required_fields = req.length ? req : null;
      body.optional_fields = opt.length ? opt : null;
    }
    if (isManual) {
      for (const k of ["beneficiary_name", "account_rib", "phone_number", "branch", "instructions", "reference_instructions"]) {
        const v = form[k as keyof FormState];
        body[k] = typeof v === "string" && v === "" ? null : v;
      }
    }
    if (isCrypto) {
      body.wallet_address = form.wallet_address.trim() || null;
      body.network = form.network.trim() || null;
      body.instructions = form.instructions.trim() || null;
      body.reference_instructions = form.reference_instructions.trim() || null;
    }
    if (isAuto) {
      body.provider_name = form.provider_name.trim() || null;
      body.gateway_status = form.gateway_status.trim() || null;
      body.currencies = form.currencies.split(",").map((s) => s.trim().toUpperCase()).filter(Boolean);
    }
    return body;
  };

  const handleSave = async () => {
    if (!editing) return;
    setSaving(true);
    setError("");
    try {
      await updatePaymentConfig(editing.method_id, buildBody());
      setEditing(null);
      load();
    } catch (e) {
      setError(parseApiError(e));
    } finally {
      setSaving(false);
    }
  };

  const handleCreate = async () => {
    setSaving(true);
    setError("");
    try {
      const body = buildBody();
      body.method_id = form.method_id.trim().toLowerCase();
      body.method_type = form.method_type;
      await createPaymentConfig(body);
      setCreating(false);
      load();
    } catch (e) {
      setError(parseApiError(e));
    } finally {
      setSaving(false);
    }
  };

  const toggleActive = async (c: PaymentConfig) => {
    try {
      await updatePaymentConfig(c.method_id, { is_active: !c.is_active });
      load();
    } catch (e) {
      setError(parseApiError(e));
    }
  };

  const handleRemove = async () => {
    if (!removing) return;
    setSaving(true);
    setError("");
    try {
      await archivePaymentConfig(removing.method_id);
      setRemoving(null);
      load();
    } catch (e) {
      setError(parseApiError(e));
    } finally {
      setSaving(false);
    }
  };

  const modalOpen = !!editing || creating;
  const modalTitle = creating ? "Add Payment Method" : `Edit: ${editing?.display_name || ""}`;
  const isManualEditing = creating || editing?.method_type === "manual" || editing?.method_type === "manual_crypto";
  const isManualOnly = creating || editing?.method_type === "manual";
  const isCryptoEditing = creating || editing?.method_type === "manual_crypto";
  const isAutoEditing = creating || editing?.method_type === "automatic";

  return (
    <OwnerPermissionGuard permission="billing.update">
      <div className="flex flex-col gap-5 max-w-6xl">
        <PageHeader
          title="Payment Methods"
          subtitle="Configuration-driven payment methods. Define the description, information and client input fields for each method — the client form renders them dynamically. No code changes needed to add a new method."
        />

        {error && (
          <div className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
            {error}
          </div>
        )}

        <div className="flex justify-end">
          <Button size="sm" icon="plus" onClick={openCreate}>Add Payment Method</Button>
        </div>

        {!configs.length && !error ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {[0, 1].map((i) => <Skeleton key={i} className="h-48 rounded-xl" />)}
          </div>
        ) : configs.length === 0 ? (
          <EmptyState
            icon="info"
            title="No payment methods configured"
            description="Add a manual method (e.g. Cash Plus, CIH Bank, Crypto) or an automatic provider."
          />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {configs.map((c) => (
              <div
                key={c.id}
                className={`bg-raised border rounded-xl p-5 flex flex-col ${
                  c.is_active ? "border-line" : "border-line opacity-60"
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <div className="text-base font-bold text-ink">{c.display_name}</div>
                  <Badge tone={c.is_active ? "green" : "gray"}>
                    {c.is_active ? "Active" : "Inactive"}
                  </Badge>
                </div>

                <div className="flex items-center gap-1.5 mb-1">
                  <span className="text-[10px] text-ink-muted font-mono">method_id: {c.method_id}</span>
                  <Badge tone={c.method_type === "manual" ? "amber" : c.method_type === "manual_crypto" ? "blue" : "blue"}>
                    {c.method_type === "manual" ? "Manual" : c.method_type === "manual_crypto" ? "Crypto" : "Automatic"}
                  </Badge>
                </div>

                <div className="space-y-1 text-[11px] text-ink-soft flex-1 mb-3">
                  {c.description && (
                    <div className="text-ink-muted leading-relaxed">{c.description}</div>
                  )}
                  {c.method_type === "manual" && (
                    <>
                      {c.beneficiary_name && (
                        <div><span className="text-ink-muted">Beneficiary:</span> {c.beneficiary_name}</div>
                      )}
                      {c.account_rib && (
                        <div><span className="text-ink-muted">RIB:</span> <span className="font-mono">{c.account_rib}</span></div>
                      )}
                      {c.phone_number && (
                        <div><span className="text-ink-muted">Phone:</span> <span className="font-mono">{c.phone_number}</span></div>
                      )}
                      {c.branch && (
                        <div><span className="text-ink-muted">Branch:</span> {c.branch}</div>
                      )}
                      {c.instructions && (
                        <div className="mt-1.5 text-ink-muted leading-relaxed">{c.instructions}</div>
                      )}
                    </>
                  )}
                  {c.method_type === "manual_crypto" && (
                    <>
                      {c.wallet_address && (
                        <div><span className="text-ink-muted">Wallet:</span> <span className="font-mono break-all">{c.wallet_address}</span></div>
                      )}
                      {c.network && (
                        <div><span className="text-ink-muted">Network:</span> {c.network}</div>
                      )}
                    </>
                  )}
                  {c.method_type === "automatic" && (
                    <>
                      {c.provider_name && (
                        <div><span className="text-ink-muted">Provider:</span> {c.provider_name}</div>
                      )}
                      {Array.isArray(c.currencies) && c.currencies.length > 0 && (
                        <div><span className="text-ink-muted">Currencies:</span> {c.currencies.join(", ")}</div>
                      )}
                      {c.gateway_status && (
                        <div><span className="text-ink-muted">Gateway:</span> {c.gateway_status}</div>
                      )}
                    </>
                  )}
                  {Array.isArray(c.information) && c.information.length > 0 && (
                    <div className="mt-1.5">
                      <div className="text-ink-muted font-medium mb-0.5">Information:</div>
                      {c.information.map((b, i) => (
                        <div key={i}><span className="text-ink-muted">{b.label}:</span> {b.value}</div>
                      ))}
                    </div>
                  )}
                  <div className="mt-1.5 flex flex-wrap gap-1.5">
                    {c.receipt_required && <Badge tone="amber">Receipt required</Badge>}
                    <Badge tone={c.reference_required ? "amber" : "gray"}>
                      {c.reference_required ? "Reference required" : "No reference"}
                    </Badge>
                    <Badge tone="blue">Expires: {c.expires_hours ?? 72}h</Badge>
                    {Array.isArray(c.client_fields) && c.client_fields.length > 0 && (
                      <Badge tone="blue">{c.client_fields.length} field{c.client_fields.length > 1 ? "s" : ""}</Badge>
                    )}
                  </div>
                </div>

                <div className="text-[10px] text-ink-muted mb-2">Order: {c.display_order}</div>

                <div className="flex flex-wrap gap-1.5 pt-2 border-t border-line/60">
                  <Button size="sm" variant="ghost" icon="edit" onClick={() => openEdit(c)}>
                    Edit
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    icon={c.is_active ? "pause" : "play"}
                    onClick={() => toggleActive(c)}
                  >
                    {c.is_active ? "Disable" : "Enable"}
                  </Button>
                  <Button size="sm" variant="ghost" icon="trash" onClick={() => setRemoving(c)}>
                    Remove
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* ================================================================ */}
        {/* EDIT / CREATE MODAL                                              */}
        {/* ================================================================ */}
        <Modal
          open={modalOpen}
          onClose={() => { setEditing(null); setCreating(false); }}
          title={modalTitle}
          icon="info"
          size="lg"
        >
          <div className="space-y-4 text-sm">
            {creating && (
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-medium text-ink-soft mb-1">Method ID *</label>
                  <input
                    className={inputCls}
                    value={(form.method_id as string) || ""}
                    onChange={(e) => setForm({ ...form, method_id: e.target.value })}
                    placeholder="e.g. inwi_money"
                  />
                  <p className="text-[10px] text-ink-muted mt-1">Lowercase letters, digits, underscores.</p>
                </div>
                <div>
                  <label className="block text-xs font-medium text-ink-soft mb-1">Display Name *</label>
                  <input
                    className={inputCls}
                    value={(form.display_name as string) || ""}
                    onChange={(e) => setForm({ ...form, display_name: e.target.value })}
                    placeholder="e.g. Inwi Money"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-ink-soft mb-1">Method Type *</label>
                  <select
                    className={selectCls}
                    value={form.method_type}
                    onChange={(e) => setForm({ ...form, method_type: e.target.value as FormState["method_type"] })}
                  >
                    <option value="manual">Manual</option>
                    <option value="manual_crypto">Crypto</option>
                    <option value="automatic">Automatic</option>
                  </select>
                </div>
              </div>
            )}

            {!creating && (
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-ink-soft mb-1">Display Name *</label>
                  <input
                    className={inputCls}
                    value={(form.display_name as string) || ""}
                    onChange={(e) => setForm({ ...form, display_name: e.target.value })}
                  />
                </div>
                <div className="flex items-end pb-1">
                  <Badge tone={form.method_type === "manual" ? "amber" : form.method_type === "manual_crypto" ? "blue" : "blue"}>
                    {form.method_type === "manual" ? "Manual" : form.method_type === "manual_crypto" ? "Crypto" : "Automatic"}
                  </Badge>
                </div>
              </div>
            )}

            {/* DESCRIPTION — separate from information and client fields */}
            <div>
              <label className="block text-xs font-medium text-ink-soft mb-1">Description</label>
              <textarea
                className={inputCls}
                rows={2}
                value={(form.description as string) || ""}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                placeholder="Short description shown to the client, e.g. Transfer the exact amount to the account below."
              />
              <p className="text-[10px] text-ink-muted mt-1">Shown as the method&apos;s intro text. Separate from the information blocks and client fields.</p>
            </div>

            {isManualEditing && (
              <>
                {/* INFORMATION — structured key/value blocks */}
                <div className="rounded-lg border border-line p-3">
                  <div className="flex items-center justify-between mb-2">
                    <label className="text-xs font-semibold text-ink">Information / Instructions</label>
                    <Button size="sm" variant="ghost" icon="plus" onClick={addInfo}>Add Block</Button>
                  </div>
                  <p className="text-[10px] text-ink-muted mb-2">
                    Structured details the client must see (e.g. Beneficiary, RIB, Phone). Each block is a label + value.
                  </p>
                  {form.information.length === 0 && (
                    <p className="text-[11px] text-ink-muted italic">No information blocks yet.</p>
                  )}
                  <div className="space-y-2">
                    {form.information.map((b, i) => (
                      <div key={i} className="flex items-center gap-2">
                        <input
                          className={inputCls}
                          value={b.label}
                          onChange={(e) => updateInfo(i, { label: e.target.value })}
                          placeholder="Label (e.g. Beneficiary)"
                        />
                        <input
                          className={inputCls}
                          value={b.value}
                          onChange={(e) => updateInfo(i, { value: e.target.value })}
                          placeholder="Value (e.g. Company SARL)"
                        />
                        <button
                          type="button"
                          onClick={() => removeInfo(i)}
                          className="text-danger hover:text-danger/70 text-sm px-1"
                          aria-label="Remove block"
                        >
                          &times;
                        </button>
                      </div>
                    ))}
                  </div>
                </div>

                {/* CLIENT FIELDS — dynamic input definitions */}
                <div className="rounded-lg border border-line p-3">
                  <div className="flex items-center justify-between mb-2">
                    <label className="text-xs font-semibold text-ink">Client Input Fields</label>
                    <Button size="sm" variant="ghost" icon="plus" onClick={addField}>Add Field</Button>
                  </div>
                  <p className="text-[10px] text-ink-muted mb-2">
                    Fields the client must fill in. The client form renders these dynamically — no code changes needed.
                  </p>
                  {form.client_fields.length === 0 && (
                    <p className="text-[11px] text-ink-muted italic">No client fields yet.</p>
                  )}
                  <div className="space-y-3">
                    {form.client_fields.map((fd, i) => (
                      <div key={i} className="rounded-md border border-line/70 bg-input/40 p-2.5 space-y-2">
                        <div className="flex items-center gap-2">
                          <input
                            className={inputCls}
                            value={fd.key}
                            onChange={(e) => updateField(i, { key: e.target.value })}
                            placeholder="Key (e.g. payment_reference)"
                          />
                          <input
                            className={inputCls}
                            value={fd.label}
                            onChange={(e) => updateField(i, { label: e.target.value })}
                            placeholder="Label (e.g. Payment Reference)"
                          />
                          <button
                            type="button"
                            onClick={() => removeField(i)}
                            className="text-danger hover:text-danger/70 text-sm px-1"
                            aria-label="Remove field"
                          >
                            &times;
                          </button>
                        </div>
                        <div className="flex items-center gap-2">
                          <select
                            className={selectCls}
                            value={fd.type}
                            onChange={(e) => updateField(i, { type: e.target.value as FieldType })}
                          >
                            {FIELD_TYPES.map((ft) => (
                              <option key={ft.value} value={ft.value}>{ft.label}</option>
                            ))}
                          </select>
                          <input
                            className={inputCls}
                            value={fd.placeholder ?? ""}
                            onChange={(e) => updateField(i, { placeholder: e.target.value })}
                            placeholder="Placeholder (optional)"
                          />
                          <label className="flex items-center gap-1.5 whitespace-nowrap cursor-pointer">
                            <input
                              type="checkbox"
                              checked={fd.required}
                              onChange={(e) => updateField(i, { required: e.target.checked })}
                              className="accent-brand-500"
                            />
                            <span className="text-[11px] text-ink">Required</span>
                          </label>
                        </div>
                        <input
                          className={inputCls}
                          value={fd.validation ?? ""}
                          onChange={(e) => updateField(i, { validation: e.target.value })}
                          placeholder="Validation rule (optional, e.g. min:0, max:10000, pattern:^[0-9+ ]{8,15}$)"
                        />
                      </div>
                    ))}
                  </div>
                </div>

                {/* RECEIPT REQUIREMENT — mandatory for manual methods */}
                <div className="flex items-center gap-2">
                  <label className="flex items-center gap-1.5 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={form.receipt_required ?? true}
                      onChange={(e) => setForm({ ...form, receipt_required: e.target.checked })}
                      className="accent-brand-500"
                    />
                    <span className="text-xs text-ink">Client must upload a receipt / photo of payment</span>
                  </label>
                </div>
              </>
            )}

            {isManualOnly && (
              <>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-ink-soft mb-1">Beneficiary Name</label>
                    <input
                      className={inputCls}
                      value={(form.beneficiary_name as string) || ""}
                      onChange={(e) => setForm({ ...form, beneficiary_name: e.target.value })}
                      placeholder="e.g. Company Name SARL"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-ink-soft mb-1">Account RIB</label>
                    <input
                      className={inputCls}
                      value={(form.account_rib as string) || ""}
                      onChange={(e) => setForm({ ...form, account_rib: e.target.value })}
                      placeholder="e.g. 011 780 0001 234567890123 45"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-ink-soft mb-1">Phone Number</label>
                    <input
                      className={inputCls}
                      value={(form.phone_number as string) || ""}
                      onChange={(e) => setForm({ ...form, phone_number: e.target.value })}
                      placeholder="e.g. +212 6 00 00 00 00"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-ink-soft mb-1">Branch</label>
                    <input
                      className={inputCls}
                      value={(form.branch as string) || ""}
                      onChange={(e) => setForm({ ...form, branch: e.target.value })}
                      placeholder="e.g. Agence Maarif, Casablanca"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium text-ink-soft mb-1">Payment Instructions</label>
                  <textarea
                    className={inputCls}
                    rows={3}
                    value={(form.instructions as string) || ""}
                    onChange={(e) => setForm({ ...form, instructions: e.target.value })}
                    placeholder="Step-by-step instructions for the client"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-ink-soft mb-1">Reference Instructions</label>
                  <textarea
                    className={inputCls}
                    rows={2}
                    value={(form.reference_instructions as string) || ""}
                    onChange={(e) => setForm({ ...form, reference_instructions: e.target.value })}
                    placeholder="What the client should enter as payment reference"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-ink-soft mb-1">Expires After (hours)</label>
                    <input
                      type="number"
                      min={1}
                      className={inputCls}
                      value={form.expires_hours ?? 72}
                      onChange={(e) => setForm({ ...form, expires_hours: Number(e.target.value) })}
                    />
                    <p className="text-[10px] text-ink-muted mt-1">Checkouts for this method expire after this many hours.</p>
                  </div>
                  <div className="flex items-end pb-1">
                    <label className="flex items-center gap-1.5 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={form.reference_required ?? true}
                        onChange={(e) => setForm({ ...form, reference_required: e.target.checked })}
                        className="accent-brand-500"
                      />
                      <span className="text-xs text-ink">Client must enter a payment reference</span>
                    </label>
                  </div>
                </div>
              </>
            )}

            {isCryptoEditing && (
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-ink-soft mb-1">Wallet Address</label>
                  <input
                    className={inputCls}
                    value={(form.wallet_address as string) || ""}
                    onChange={(e) => setForm({ ...form, wallet_address: e.target.value })}
                    placeholder="e.g. bc1q... or 0x..."
                  />
                  <p className="text-[10px] text-ink-muted mt-1">Clients pay to this address. Empty = method hidden from clients.</p>
                </div>
                <div>
                  <label className="block text-xs font-medium text-ink-soft mb-1">Network</label>
                  <input
                    className={inputCls}
                    value={(form.network as string) || ""}
                    onChange={(e) => setForm({ ...form, network: e.target.value })}
                    placeholder="e.g. TRC20, ERC20, BEP20"
                  />
                </div>
              </div>
            )}

            {isAutoEditing && (
              <>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-ink-soft mb-1">Provider Name</label>
                    <input
                      className={inputCls}
                      value={(form.provider_name as string) || ""}
                      onChange={(e) => setForm({ ...form, provider_name: e.target.value })}
                      placeholder="e.g. Stripe, CMI, Payzone"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-ink-soft mb-1">Gateway Status</label>
                    <input
                      className={inputCls}
                      value={(form.gateway_status as string) || ""}
                      onChange={(e) => setForm({ ...form, gateway_status: e.target.value })}
                      placeholder="e.g. live, test, pending"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-medium text-ink-soft mb-1">Supported Currencies (comma separated)</label>
                  <input
                    className={inputCls}
                    value={(form.currencies as string) || ""}
                    onChange={(e) => setForm({ ...form, currencies: e.target.value })}
                    placeholder="e.g. MAD, USD, EUR"
                  />
                  <p className="text-[10px] text-ink-muted mt-1">Automatic gateways do not require beneficiary/receipt fields.</p>
                </div>
              </>
            )}

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-ink-soft mb-1">Display Order</label>
                <input
                  type="number"
                  className={inputCls}
                  value={form.display_order ?? 0}
                  onChange={(e) => setForm({ ...form, display_order: Number(e.target.value) })}
                />
              </div>
              <div className="flex items-end pb-1">
                <label className="flex items-center gap-1.5 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={form.is_active ?? true}
                    onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                    className="accent-brand-500"
                  />
                  <span className="text-xs text-ink">Active</span>
                </label>
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <Button variant="ghost" onClick={() => { setEditing(null); setCreating(false); }}>Cancel</Button>
              <Button onClick={creating ? handleCreate : handleSave} loading={saving}>
                {saving ? "Saving..." : creating ? "Create" : "Save"}
              </Button>
            </div>
          </div>
        </Modal>

        {/* ================================================================ */}
        {/* REMOVE CONFIRM                                                    */}
        {/* ================================================================ */}
        <ConfirmDialog
          open={!!removing}
          title={`Remove ${removing?.display_name || ""}?`}
          description="This archives the payment method. It will no longer be shown to clients, but existing payments are kept."
          confirmLabel="Remove"
          tone="danger"
          loading={saving}
          onConfirm={handleRemove}
          onCancel={() => setRemoving(null)}
        />
      </div>
    </OwnerPermissionGuard>
  );
}