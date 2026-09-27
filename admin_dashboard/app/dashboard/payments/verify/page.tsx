"use client";

import { useEffect, useState, useCallback } from "react";
import PermissionGuard from "@/components/auth/permission_guard";
import StatusBadge from "@/components/StatusBadge";
import { listPendingPayments, approvePayment, rejectPayment, getPaymentMethodLabel, listPaymentsFiltered } from "@/lib/api";
import { Button, Card, PageHeader, Table, Td, Badge } from "@ds/components/ui";
import { formatPrice } from "@/lib/currency";

type FilterTab = "all" | "pending" | "paid" | "rejected";

export default function PaymentVerifyPage() {
  const [payments, setPayments] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<FilterTab>("pending");
  const [actionBusy, setActionBusy] = useState<string | null>(null);
  const [rejectModal, setRejectModal] = useState<{ id: string; reason: string } | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      if (tab === "pending") {
        const res = await listPendingPayments({ limit: 100 });
        setPayments(res.items || []);
        setTotal(res.total || 0);
      } else {
        const statusMap: Record<string, string> = {
          paid: "PAID",
          rejected: "REJECTED",
          all: "",
        };
        const statusFilter = statusMap[tab];
        const params = statusFilter ? `?status=${statusFilter}&limit=100` : "?limit=100";
        const res = await listPaymentsFiltered(params);
        setPayments(res.items || []);
        setTotal(res.total || 0);
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [tab]);

  useEffect(() => { load(); }, [load]);

  const handleApprove = async (paymentId: string) => {
    setActionBusy(paymentId);
    try {
      await approvePayment(paymentId);
      load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setActionBusy(null);
    }
  };

  const handleReject = async () => {
    if (!rejectModal || !rejectModal.reason.trim()) return;
    setActionBusy(rejectModal.id);
    try {
      await rejectPayment(rejectModal.id, rejectModal.reason.trim());
      setRejectModal(null);
      load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setActionBusy(null);
    }
  };

  const statusBadge = (status: string) => {
    switch (status) {
      case "PAID": return <Badge tone="green">Paid</Badge>;
      case "PENDING": return <Badge tone="amber">Pending</Badge>;
      case "PENDING_VERIFICATION": return <Badge tone="amber">Awaiting Review</Badge>;
      case "PROCESSING": return <Badge tone="blue">Processing</Badge>;
      case "FAILED": return <Badge tone="red">Failed</Badge>;
      case "CANCELLED": return <Badge tone="gray">Cancelled</Badge>;
      case "REJECTED": return <Badge tone="red">Rejected</Badge>;
      case "REFUNDED": return <Badge tone="amber">Refunded</Badge>;
      default: return <Badge tone="gray">{status}</Badge>;
    }
  };

  const tabs: { key: FilterTab; label: string }[] = [
    { key: "all", label: "All" },
    { key: "pending", label: "Pending" },
    { key: "paid", label: "Paid" },
    { key: "rejected", label: "Rejected" },
  ];

  return (
    <PermissionGuard permission="billing.read">
      <div>
        <PageHeader
          title="Payment Verification"
          subtitle="Review and approve or reject pending payments"
          actions={<Button onClick={load}>Refresh</Button>}
        />

        {error && <div className="text-danger text-sm mb-3">{error}</div>}

        {/* Filter tabs */}
        <div className="flex gap-1 mb-4 border-b border-line">
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                tab === t.key
                  ? "border-brand-500 text-brand-400"
                  : "border-transparent text-ink-muted hover:text-ink"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        <Card title="Payments" subtitle={`${total} payment${total !== 1 ? "s" : ""}`} bodyClassName="p-0">
          {loading ? (
            <div className="py-12 text-center text-ink-muted text-sm">Loading...</div>
          ) : payments.length === 0 ? (
            <div className="py-12 text-center text-ink-muted text-sm">
              {tab === "pending"
                ? "No pending payments to review."
                : "No payments match the selected filter."}
            </div>
          ) : (
            <Table columns={["Date", "Payment #", "User", "Plan", "Amount", "Method", "Status", "Actions"]}>
              {payments.map((p) => (
                <tr key={p.id}>
                  <Td className="text-xs whitespace-nowrap">
                    {p.created_at ? new Date(p.created_at).toLocaleDateString() : "—"}
                  </Td>
                  <Td mono className="text-xs">{p.payment_number || "—"}</Td>
                  <Td mono className="text-xs">{p.user_id?.slice(0, 8) || "—"}</Td>
                  <Td>{p.plan_name || p.plan_id || "—"}</Td>
                  <Td mono>{formatPrice(p.final_amount || p.amount, p.currency)}</Td>
                  <Td className="text-xs">{getPaymentMethodLabel(p.payment_method || p.payment_provider)}</Td>
                  <Td>{statusBadge(p.status)}</Td>
                  <Td>
                    {(p.status === "PENDING" || p.status === "PENDING_VERIFICATION") ? (
                      <div className="flex gap-1">
                        <Button
                          size="sm"
                          variant="primary"
                          disabled={actionBusy === p.id}
                          onClick={() => handleApprove(p.id)}
                        >
                          {actionBusy === p.id ? "..." : "Approve"}
                        </Button>
                        <Button
                          size="sm"
                          variant="danger"
                          disabled={actionBusy === p.id}
                          onClick={() => setRejectModal({ id: p.id, reason: "" })}
                        >
                          Reject
                        </Button>
                      </div>
                    ) : p.status === "REJECTED" && p.rejection_reason ? (
                      <span className="text-xs text-danger" title={p.rejection_reason}>Rejected</span>
                    ) : "—"}
                  </Td>
                </tr>
              ))}
            </Table>
          )}
        </Card>

        {/* Reject modal */}
        {rejectModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
            <div className="bg-surface rounded-xl border border-line shadow-xl w-full max-w-md p-6 flex flex-col gap-4">
              <h3 className="text-base font-semibold text-ink">Reject Payment</h3>
              <p className="text-sm text-ink-soft">Provide a reason for rejecting this payment:</p>
              <textarea
                value={rejectModal.reason}
                onChange={(e) => setRejectModal({ ...rejectModal, reason: e.target.value })}
                placeholder="Rejection reason..."
                className="h-24 px-3 py-2 rounded-lg bg-input border border-line text-sm text-ink resize-none focus:outline-none focus:ring-2 focus:ring-brand-500/40"
                autoFocus
              />
              <div className="flex gap-2 justify-end">
                <Button variant="ghost" onClick={() => setRejectModal(null)}>
                  Cancel
                </Button>
                <Button
                  variant="danger"
                  disabled={!rejectModal.reason.trim() || actionBusy === rejectModal.id}
                  loading={actionBusy === rejectModal.id}
                  onClick={handleReject}
                >
                  Reject Payment
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>
    </PermissionGuard>
  );
}
