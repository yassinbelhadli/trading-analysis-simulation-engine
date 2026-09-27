"use client";

import { useEffect, useState, useCallback } from "react";
import OwnerPermissionGuard from "@/components/auth/owner_permission_guard";
import {
  listPayments,
  listPendingPayments,
  approvePayment,
  rejectPayment,
  getPaymentMethodLabel,
  fetchProofObjectUrl,
} from "@/lib/api";
import { PageHeader, Card, Table, Td, Badge, Button, EmptyState, Skeleton, type BadgeTone } from "@ds/components/ui";
import { Modal } from "@ds/components/Modal";
import { parseApiError } from "@/lib/errors";
import { formatPrice } from "@/lib/currency";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
type FilterTab = "all" | "pending" | "paid" | "rejected" | "expired";

interface PaymentItem {
  id: string;
  payment_number?: string;
  user_id: string;
  user_email?: string;
  user_first_name?: string;
  user_last_name?: string;
  plan_id?: string;
  plan_name?: string;
  plan_duration_days?: number | null;
  original_amount?: number;
  discount_amount?: number;
  final_amount?: number;
  amount?: number;
  currency: string;
  coupon_code?: string | null;
  payment_provider?: string;
  payment_method?: string | null;
  payment_method_type?: string | null;
  status: string;
  failure_reason?: string | null;
  created_at?: string;
  updated_at?: string;
  paid_at?: string | null;
  failed_at?: string | null;
  cancelled_at?: string | null;
  refunded_at?: string | null;
  rejected_at?: string | null;
  rejection_reason?: string | null;
  approved_by?: string | null;
  approved_at?: string | null;
  internal_notes?: string | null;
  manual_reference?: string | null;
  manual_proof_url?: string | null;
  payer_name?: string | null;
  payer_phone?: string | null;
  payment_date?: string | null;
  manual_instructions?: string | null;
  // Crypto fields
  deposit_address?: string | null;
  deposit_network?: string | null;
  coin_ticker?: string | null;
  transaction_hash?: string | null;
  sender_address?: string | null;
  confirmation_count?: number | null;
  expected_amount?: number | null;
  detected_at?: string | null;
  confirmed_at?: string | null;
  expired_at?: string | null;
  verification_type?: string | null;
  verified_by?: string | null;
  proof_screenshot_url?: string | null;
  proof_submitted_at?: string | null;
  proof_tx_hash?: string | null;
  proof_amount?: number | null;
  proof_note?: string | null;
}

// Canonical pending statuses (must match backend list_pending_manual_payments)
const PENDING_STATUSES = [
  "pending",
  "pending_verification",
  "awaiting_payment",
  "transaction_detected",
  "confirming",
  "manual_review",
];

function isPendingStatus(s: string | undefined): boolean {
  return PENDING_STATUSES.includes(s?.toLowerCase() || "");
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function statusBadgeTone(status: string): BadgeTone {
  const s = status?.toLowerCase();
  if (s === "paid" || s === "completed" || s === "succeeded") return "green";
  if (isPendingStatus(s)) return "amber";
  if (s === "failed" || s === "rejected") return "red";
  if (s === "awaiting_payment") return "blue";
  if (s === "expired" || s === "cancelled" || s === "refunded") return "gray";
  return "gray";
}

function statusLabel(status: string): string {
  const s = status?.toLowerCase();
  if (s === "pending_verification") return "Pending Verification";
  if (s === "awaiting_payment") return "Awaiting Payment";
  if (s === "transaction_detected") return "Transaction Detected";
  if (s === "manual_review") return "Manual Review";
  return s?.charAt(0).toUpperCase() + s?.slice(1) || "—";
}

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "—";
  return d.toLocaleString();
}

function paymentMethodLabel(p: PaymentItem): string {
  return getPaymentMethodLabel(p.payment_method || p.payment_provider);
}

const inputCls =
  "w-full px-2 py-1.5 rounded-lg bg-input border border-line text-xs text-ink focus:outline-none focus:border-brand-500";

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function PaymentVerificationPage() {
  const [payments, setPayments] = useState<PaymentItem[]>([]);
  const [total, setTotal] = useState(0);
  const [pendingPayments, setPendingPayments] = useState<PaymentItem[]>([]);
  const [pendingTotal, setPendingTotal] = useState(0);
  const [filter, setFilter] = useState<FilterTab>("all");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);

  // Detail view state
  const [detailTarget, setDetailTarget] = useState<PaymentItem | null>(null);

  // Reject dialog state
  const [rejectTarget, setRejectTarget] = useState<PaymentItem | null>(null);
  const [rejectReason, setRejectReason] = useState("");

  // ---------------------------------------------------------------------------
  // Load data
  // ---------------------------------------------------------------------------
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [all, pending] = await Promise.all([
        listPayments("?limit=200"),
        listPendingPayments("?limit=200"),
      ]);
      setPayments(all.items);
      setTotal(all.total);
      setPendingPayments(pending.items);
      setPendingTotal(pending.total);
    } catch (e) {
      setError(parseApiError(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // ---------------------------------------------------------------------------
  // Filtered list
  // ---------------------------------------------------------------------------
  const filteredPayments = payments.filter((p) => {
    const s = p.status?.toLowerCase();
    switch (filter) {
      case "pending":
        return isPendingStatus(s);
      case "paid":
        return s === "paid" || s === "completed" || s === "succeeded";
      case "rejected":
        return s === "failed" || s === "rejected";
      case "expired":
        return s === "expired" || s === "cancelled" || s === "refunded";
      default:
        return true;
    }
  });

  // ---------------------------------------------------------------------------
  // Actions
  // ---------------------------------------------------------------------------
  const handleApprove = async (payment: PaymentItem) => {
    setSaving(true);
    setError("");
    try {
      await approvePayment(payment.id);
      setDetailTarget(null);
      await load();
    } catch (e) {
      setError(parseApiError(e));
    } finally {
      setSaving(false);
    }
  };

  const openReject = (payment: PaymentItem) => {
    setDetailTarget(null);
    setRejectTarget(payment);
    setRejectReason("");
  };

  const handleReject = async () => {
    if (!rejectTarget || !rejectReason.trim()) return;
    setSaving(true);
    setError("");
    try {
      await rejectPayment(rejectTarget.id, rejectReason.trim());
      setRejectTarget(null);
      setRejectReason("");
      await load();
    } catch (e) {
      setError(parseApiError(e));
    } finally {
      setSaving(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Filter tabs
  // ---------------------------------------------------------------------------
  const FILTER_TABS: { key: FilterTab; label: string; count: number }[] = [
    { key: "all", label: "All", count: total },
    { key: "pending", label: "Pending", count: pendingTotal },
    { key: "paid", label: "Paid", count: payments.filter((p) => ["paid", "completed", "succeeded"].includes(p.status?.toLowerCase())).length },
    { key: "rejected", label: "Rejected", count: payments.filter((p) => ["failed", "rejected"].includes(p.status?.toLowerCase())).length },
    { key: "expired", label: "Expired", count: payments.filter((p) => ["expired", "cancelled", "refunded"].includes(p.status?.toLowerCase())).length },
  ];

  const detail = detailTarget;

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------
  return (
    <OwnerPermissionGuard permission="subscriptions.read">
      <div className="flex flex-col gap-5 max-w-7xl">
        <PageHeader
          title="Payment Verification"
          subtitle="Review, approve or reject pending manual payments."
          actions={
            <div className="flex gap-2">
              {FILTER_TABS.map((t) => (
                <Button
                  key={t.key}
                  size="sm"
                  variant={filter === t.key ? "primary" : "secondary"}
                  onClick={() => setFilter(t.key)}
                >
                  {t.label}
                  {t.key === "pending" && t.count > 0 && (
                    <span className="ml-1.5 inline-flex items-center justify-center min-w-[18px] h-[18px] rounded-full bg-danger text-white text-[10px] font-bold px-1">
                      {t.count}
                    </span>
                  )}
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

        <Card
          title={`Payments (${filteredPayments.length})`}
          icon="receipt"
          bodyClassName="p-0"
        >
          {loading ? (
            <div className="p-4 flex flex-col gap-2">
              <Skeleton className="h-9 w-full" />
              <Skeleton className="h-9 w-full" />
              <Skeleton className="h-9 w-full" />
              <Skeleton className="h-9 w-full" />
            </div>
          ) : filteredPayments.length === 0 && !error ? (
            <EmptyState
              icon="receipt"
              title={
                filter === "pending"
                  ? "No pending payments"
                  : filter === "all"
                    ? "No payments yet"
                    : `No ${filter} payments`
              }
              description={
                filter === "pending"
                  ? "All manual payments have been reviewed."
                  : "Payments will appear here once users start subscribing."
              }
            />
          ) : (
            <Table
              columns={[
                "Date",
                "Payment #",
                "Client",
                "Plan",
                "Amount",
                "Currency",
                "Method",
                "Status",
                "Actions",
              ]}
            >
              {filteredPayments.map((p) => {
                const isPending = isPendingStatus(p.status);

                return (
                  <tr key={p.id} className="hover:bg-hover transition-colors">
                    <Td className="text-xs text-ink-muted whitespace-nowrap">
                      {fmtDate(p.created_at)}
                    </Td>
                    <Td mono className="text-xs font-semibold text-ink">
                      {p.payment_number || p.id?.slice(0, 8) || "—"}
                    </Td>
                    <Td className="text-xs text-ink-soft">
                      {p.user_email || p.user_id?.slice(0, 8) || "—"}
                    </Td>
                    <Td>
                      <Badge tone="blue">{p.plan_name || "—"}</Badge>
                    </Td>
                    <Td mono className="text-xs">
                      {formatPrice(p.final_amount ?? p.amount, p.currency)}
                    </Td>
                    <Td className="text-xs text-ink-muted">
                      {p.currency || "USD"}
                    </Td>
                    <Td className="text-xs text-ink-soft">
                      {paymentMethodLabel(p)}
                    </Td>
                    <Td>
                      <Badge tone={statusBadgeTone(p.status)}>
                        {statusLabel(p.status)}
                      </Badge>
                    </Td>
                    <Td>
                      <div className="flex gap-1">
                        <Button
                          size="sm"
                          variant="ghost"
                          icon="eye"
                          onClick={() => setDetailTarget(p)}
                        >
                          View
                        </Button>
                        {isPending && (
                          <>
                            <Button
                              size="sm"
                              variant="ghost"
                              icon="check"
                              onClick={() => handleApprove(p)}
                              loading={saving}
                            >
                              Approve
                            </Button>
                            <Button
                              size="sm"
                              variant="danger"
                              icon="trash"
                              onClick={() => openReject(p)}
                            >
                              Reject
                            </Button>
                          </>
                        )}
                      </div>
                    </Td>
                  </tr>
                );
              })}
            </Table>
          )}
        </Card>

        {/* ================================================================ */}
        {/* PAYMENT DETAIL MODAL                                              */}
        {/* ================================================================ */}
        <Modal
          open={!!detail}
          onClose={() => setDetailTarget(null)}
          title={`Payment ${detail?.payment_number || ""}`}
          subtitle={detail ? `${statusLabel(detail.status)} · ${fmtDate(detail.created_at)}` : ""}
          icon="info"
          size="lg"
          footer={
            detail && isPendingStatus(detail.status) ? (
              <div className="flex justify-end gap-2 pt-3 border-t border-line">
                <Button variant="danger" icon="trash" onClick={() => openReject(detail)}>
                  Reject
                </Button>
                <Button variant="primary" icon="check" loading={saving} onClick={() => handleApprove(detail)}>
                  {saving ? "Approving..." : "Approve Payment"}
                </Button>
              </div>
            ) : undefined
          }
        >
          {detail && (
            <div className="space-y-4 text-sm overflow-y-auto max-h-[60vh] pr-1">
              {/* Client */}
              <section>
                <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-muted mb-2">Client</h3>
                <div className="rounded-lg border border-line bg-surface p-3 grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
                  <div className="flex justify-between"><span className="text-ink-muted">Name:</span><span className="font-medium text-ink">{[detail.user_first_name, detail.user_last_name].filter(Boolean).join(" ") || "—"}</span></div>
                  <div className="flex justify-between"><span className="text-ink-muted">Email:</span><span className="font-medium text-ink">{detail.user_email || "—"}</span></div>
                  <div className="flex justify-between col-span-2"><span className="text-ink-muted">Client ID:</span><span className="font-medium text-ink font-mono">{detail.user_id || "—"}</span></div>
                </div>
              </section>

              {/* Payment */}
              <section>
                <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-muted mb-2">Payment</h3>
                <div className="rounded-lg border border-line bg-surface p-3 grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
                  <div className="flex justify-between"><span className="text-ink-muted">Payment #:</span><span className="font-medium text-ink font-mono">{detail.payment_number || "—"}</span></div>
                  <div className="flex justify-between"><span className="text-ink-muted">Reference ID:</span><span className="font-medium text-ink font-mono">{detail.id?.slice(0, 8) || "—"}</span></div>
                  <div className="flex justify-between"><span className="text-ink-muted">Plan:</span><span className="font-medium text-ink">{detail.plan_name || "—"}</span></div>
                  <div className="flex justify-between"><span className="text-ink-muted">Duration:</span><span className="font-medium text-ink">{detail.plan_duration_days ? `${detail.plan_duration_days} days` : "—"}</span></div>
                  <div className="flex justify-between"><span className="text-ink-muted">Method:</span><span className="font-medium text-ink">{paymentMethodLabel(detail)}</span></div>
                  <div className="flex justify-between"><span className="text-ink-muted">Type:</span><span className="font-medium text-ink">{detail.payment_method_type || "—"}</span></div>
                  <div className="flex justify-between"><span className="text-ink-muted">Original:</span><span className="font-medium text-ink">{formatPrice(detail.original_amount, detail.currency)}</span></div>
                  <div className="flex justify-between"><span className="text-ink-muted">Discount:</span><span className="font-medium text-ink text-danger">-{formatPrice(detail.discount_amount, detail.currency)}</span></div>
                  <div className="flex justify-between"><span className="text-ink-muted">Coupon:</span><span className="font-medium text-ink">{detail.coupon_code || "—"}</span></div>
                  <div className="flex justify-between"><span className="text-ink-muted">Final Amount:</span><span className="font-medium text-ink text-brand-400">{formatPrice(detail.final_amount ?? detail.amount, detail.currency)}</span></div>
                  <div className="flex justify-between"><span className="text-ink-muted">Status:</span><span className="font-medium text-ink">{statusLabel(detail.status)}</span></div>
                  <div className="flex justify-between"><span className="text-ink-muted">Created:</span><span className="font-medium text-ink">{fmtDate(detail.created_at)}</span></div>
                  <div className="flex justify-between"><span className="text-ink-muted">Paid:</span><span className="font-medium text-ink">{fmtDate(detail.paid_at)}</span></div>
                  <div className="flex justify-between"><span className="text-ink-muted">Expires:</span><span className="font-medium text-ink">{fmtDate(detail.expired_at)}</span></div>
                  {detail.rejected_at && (
                    <div className="flex justify-between col-span-2"><span className="text-ink-muted">Rejected:</span><span className="font-medium text-ink">{fmtDate(detail.rejected_at)}</span></div>
                  )}
                  {detail.rejection_reason && (
                    <div className="flex justify-between col-span-2"><span className="text-ink-muted">Rejection Reason:</span><span className="font-medium text-ink text-danger">{detail.rejection_reason}</span></div>
                  )}
                  {detail.failure_reason && (
                    <div className="flex justify-between col-span-2"><span className="text-ink-muted">Failure Reason:</span><span className="font-medium text-ink text-danger">{detail.failure_reason}</span></div>
                  )}
                </div>
              </section>

              {/* Manual payment data */}
              {(detail.manual_reference || detail.manual_instructions || detail.manual_proof_url || detail.proof_screenshot_url) && (
                <section>
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-muted mb-2">Manual Payment Data</h3>
                  <div className="rounded-lg border border-line bg-surface p-3 grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
                    {detail.manual_reference && (
                      <div className="flex justify-between col-span-2"><span className="text-ink-muted">Reference:</span><span className="font-medium text-ink font-mono">{detail.manual_reference}</span></div>
                    )}
                    {detail.payer_name && (
                      <div className="flex justify-between"><span className="text-ink-muted">Payer Name:</span><span className="font-medium text-ink">{detail.payer_name}</span></div>
                    )}
                    {detail.payer_phone && (
                      <div className="flex justify-between"><span className="text-ink-muted">Payer Phone:</span><span className="font-medium text-ink">{detail.payer_phone}</span></div>
                    )}
                    {detail.payment_date && (
                      <div className="flex justify-between"><span className="text-ink-muted">Payment Date:</span><span className="font-medium text-ink">{fmtDate(detail.payment_date)}</span></div>
                    )}
                    {detail.proof_submitted_at && (
                      <div className="flex justify-between col-span-2"><span className="text-ink-muted">Submitted:</span><span className="font-medium text-ink">{fmtDate(detail.proof_submitted_at)}</span></div>
                    )}
                    {detail.manual_instructions && (
                      <div className="col-span-2">
                        <p className="text-ink-muted mb-1">Instructions used at checkout:</p>
                        <pre className="whitespace-pre-wrap text-xs text-ink bg-base rounded-lg p-2 border border-line">{detail.manual_instructions}</pre>
                      </div>
                    )}
                  </div>
                </section>
              )}

              {/* Crypto data */}
              {(detail.coin_ticker || detail.deposit_address || detail.transaction_hash) && (
                <section>
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-muted mb-2">Crypto Payment</h3>
                  <div className="rounded-lg border border-line bg-surface p-3 grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
                    <div className="flex justify-between"><span className="text-ink-muted">Coin:</span><span className="font-medium text-ink">{detail.coin_ticker || "—"}</span></div>
                    <div className="flex justify-between"><span className="text-ink-muted">Network:</span><span className="font-medium text-ink">{detail.deposit_network || "—"}</span></div>
                    <div className="flex justify-between col-span-2"><span className="text-ink-muted">Destination Address:</span><span className="font-medium text-ink font-mono break-all">{detail.deposit_address || "—"}</span></div>
                    <div className="flex justify-between col-span-2"><span className="text-ink-muted">Transaction Hash:</span><span className="font-medium text-ink font-mono break-all">{detail.transaction_hash || detail.proof_tx_hash || "—"}</span></div>
                    <div className="flex justify-between"><span className="text-ink-muted">Expected Amount:</span><span className="font-medium text-ink">{detail.expected_amount ?? "—"}</span></div>
                    <div className="flex justify-between"><span className="text-ink-muted">Confirmations:</span><span className="font-medium text-ink">{detail.confirmation_count ?? "—"}</span></div>
                    <div className="flex justify-between"><span className="text-ink-muted">Verification:</span><span className="font-medium text-ink">{detail.verification_type || "—"}</span></div>
                    <div className="flex justify-between"><span className="text-ink-muted">Detected:</span><span className="font-medium text-ink">{fmtDate(detail.detected_at)}</span></div>
                    <div className="flex justify-between"><span className="text-ink-muted">Confirmed:</span><span className="font-medium text-ink">{fmtDate(detail.confirmed_at)}</span></div>
                  </div>
                </section>
              )}

              {/* Proof */}
              {(detail.manual_proof_url || detail.proof_screenshot_url) && (
                <section>
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-muted mb-2">Proof of Payment</h3>
                  <div className="rounded-lg border border-line bg-surface p-3">
                    <ProofViewer
                      proofUrl={detail.proof_screenshot_url || detail.manual_proof_url || ""}
                    />
                  </div>
                </section>
              )}

              {/* Internal notes */}
              {detail.internal_notes && (
                <section>
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-muted mb-2">Internal Notes</h3>
                  <div className="rounded-lg border border-line bg-surface p-3 text-xs text-ink">{detail.internal_notes}</div>
                </section>
              )}
            </div>
          )}
        </Modal>

        {/* ================================================================ */}
        {/* REJECT REASON MODAL                                              */}
        {/* ================================================================ */}
        <Modal
          open={!!rejectTarget}
          onClose={() => { setRejectTarget(null); setRejectReason(""); }}
          title={`Reject Payment ${rejectTarget?.payment_number || rejectTarget?.id?.slice(0, 8) || ""}`}
          icon="danger"
          size="md"
        >
          <div className="space-y-4 text-sm">
            <div className="rounded-lg border border-line bg-surface p-3 text-xs text-ink-soft">
              <div className="flex justify-between mb-1">
                <span>Client:</span>
                <span className="font-medium text-ink">{rejectTarget?.user_email || rejectTarget?.user_id?.slice(0, 8)}</span>
              </div>
              <div className="flex justify-between mb-1">
                <span>Amount:</span>
                <span className="font-medium text-ink">
                  {formatPrice(rejectTarget?.final_amount ?? rejectTarget?.amount, rejectTarget?.currency)}
                </span>
              </div>
              <div className="flex justify-between">
                <span>Plan:</span>
                <span className="font-medium text-ink">{rejectTarget?.plan_name || "—"}</span>
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-ink-soft mb-1">
                Rejection Reason *
              </label>
              <textarea
                className={inputCls}
                rows={3}
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                placeholder="Enter the reason for rejecting this payment..."
              />
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <Button
                variant="ghost"
                onClick={() => { setRejectTarget(null); setRejectReason(""); }}
              >
                Cancel
              </Button>
              <Button
                variant="danger"
                loading={saving}
                disabled={!rejectReason.trim()}
                onClick={handleReject}
              >
                {saving ? "Rejecting..." : "Reject Payment"}
              </Button>
            </div>
          </div>
        </Modal>
      </div>
    </OwnerPermissionGuard>
  );
}

// ---------------------------------------------------------------------------
// ProofViewer — loads the proof through the authenticated admin route and
// renders it as a blob URL (an <img src> cannot carry the Bearer token).
// ---------------------------------------------------------------------------
function ProofViewer({ proofUrl }: { proofUrl: string }) {
  const [objectUrl, setObjectUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let createdUrl: string | null = null;
    setError(null);
    setObjectUrl(null);
    fetchProofObjectUrl(proofUrl)
      .then((url) => {
        if (cancelled) {
          URL.revokeObjectURL(url);
          return;
        }
        createdUrl = url;
        setObjectUrl(url);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load proof");
      });
    return () => {
      cancelled = true;
      if (createdUrl) URL.revokeObjectURL(createdUrl);
    };
  }, [proofUrl]);

  if (error) {
    return <p className="text-[11px] text-danger break-all">{error}</p>;
  }
  if (!objectUrl) {
    return <p className="text-[11px] text-ink-muted">Loading proof…</p>;
  }

  const isImage = /\.(png|jpe?g|gif|webp|bmp)(\?|$)/i.test(proofUrl);
  return (
    <div className="space-y-2">
      {isImage ? (
        <a href={objectUrl} target="_blank" rel="noopener noreferrer" className="block">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={objectUrl}
            alt="Payment proof"
            className="max-h-64 w-auto rounded-lg border border-line bg-base object-contain"
          />
        </a>
      ) : (
        <a
          href={objectUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 rounded-lg border border-line bg-base px-3 py-2 text-xs text-brand-400 hover:bg-hover"
        >
          <span>Open proof file</span>
        </a>
      )}
      <p className="text-[11px] text-ink-muted break-all">{proofUrl}</p>
    </div>
  );
}