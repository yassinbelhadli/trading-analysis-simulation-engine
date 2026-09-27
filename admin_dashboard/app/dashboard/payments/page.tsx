"use client";

import { useEffect, useState, useCallback } from "react";
import StatusBadge from "@/components/StatusBadge";
import PermissionGuard from "@/components/auth/permission_guard";
import { listPayments, getPaymentMethodLabel } from "@/lib/api";
import { Button, Card, PageHeader, Table, Td, StatCard } from "@ds/components/ui";
import { formatPrice } from "@/lib/currency";

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

export default function PaymentsPage() {
  const [payments, setPayments] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const res = await listPayments("?limit=100");
      setPayments(res.items);
      setTotal(res.total);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <PermissionGuard permission="billing.read">
      <div>
        <PageHeader
          title="Payments"
          subtitle="Payment history and transactions"
          actions={<Button onClick={load}>Refresh</Button>}
        />

        {error && <div className="text-danger text-sm mb-3">{error}</div>}

        {/* Payment Overview Stats */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 mb-4">
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

        <Card title="Payment History" subtitle={`${total} payment${total !== 1 ? "s" : ""}`} bodyClassName="p-0">
          <Table columns={["Date", "Payment #", "User", "Plan", "Amount", "Currency", "Method", "Status"]}>
            {payments.length === 0 && (
              <tr>
                <td colSpan={8} className="text-center py-12 text-ink-muted text-sm px-4">
                  No payments yet. Once users start subscribing, payments will appear here.
                </td>
              </tr>
            )}
            {payments.map((p) => (
              <tr key={p.id}>
                <Td className="text-xs">{p.created_at ? new Date(p.created_at).toLocaleString() : "—"}</Td>
                <Td mono className="text-xs">{p.payment_number || "—"}</Td>
                <Td mono className="text-xs">{p.user_id?.slice(0, 8) || "—"}</Td>
                <Td className="text-xs">{p.plan_name || p.plan_id || "—"}</Td>
                <Td mono className="text-xs">{formatPrice(p.final_amount ?? p.amount_paid, p.currency)}</Td>
                <Td className="text-xs">{p.currency || "USD"}</Td>
                <Td className="text-xs">{getPaymentMethodLabel(p.payment_method || p.payment_provider)}</Td>
                <Td><StatusBadge status={p.status} /></Td>
              </tr>
            ))}
          </Table>
        </Card>
      </div>
    </PermissionGuard>
  );
}
