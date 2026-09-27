"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  getMySubscription,
  cancelSubscription,
  type ClientSubscriptionResponse,
} from "@/lib/api";
import { Notice, type NoticeState } from "@/components/Notice";
import { PageHeader, Card, Button, Badge, EmptyState, Skeleton } from "@ds/components/ui";
import { ConfirmDialog } from "@ds/components/Modal";
import { parseApiError } from "@/lib/errors";
import { formatPrice } from "@/lib/currency";
import { useLocale } from "@/components/LocaleContext";
import { formatUserDate } from "@/lib/timezone";

export default function SubscriptionPage() {
  const router = useRouter();
  const { t, timezone: userTimezone } = useLocale();
  const [data, setData] = useState<ClientSubscriptionResponse | null>(null);
  const [error, setError] = useState("");
  const [status, setStatus] = useState<NoticeState>(null);
  const [busy, setBusy] = useState(false);
  const [confirmCancel, setConfirmCancel] = useState(false);

  const refresh = async () => {
    try {
      const subData = await getMySubscription();
      setData(subData);
      setError("");
    } catch (e) {
      setError(parseApiError(e));
    }
  };

  useEffect(() => { refresh(); }, []);

  const sub = data?.subscription;

  const handleCancel = async () => {
    setConfirmCancel(false);
    setStatus(null);
    setBusy(true);
    try {
      await cancelSubscription();
      setStatus({ ok: true, text: t("subscription.cancelled") });
      refresh();
    } catch (err) {
      setStatus({ ok: false, text: err instanceof Error ? err.message : t("subscription.cancelFailed") });
    } finally {
      setBusy(false);
    }
  };

  if (error) {
    return <EmptyState icon="alert-triangle" title={t("subscription.loadError")} description={error} />;
  }

  if (!data) {
    return (
      <div className="max-w-4xl flex flex-col gap-5">
        <Skeleton className="h-8 w-56" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  return (
    <div className="max-w-4xl flex flex-col gap-5">
      <PageHeader title={t("subscription.title")} subtitle={t("subscription.subtitle")} />

      <Notice state={status} />

      {/* Current Plan + Actions */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card title={t("subscription.currentPlan")} icon="credit-card">
          {sub ? (
            <div className="flex flex-col gap-2.5 text-sm">
              <Row k={t("subscription.plan")} v={sub.plan_name} strong />
              <Row k={t("subscription.status")} v={sub.active ? t("subscription.active") : t("subscription.expired")} active={sub.active} />
              <Row k={t("subscription.pricePaid")} v={formatPrice(sub.price, sub.plan_currency || "USD")} />
              <Row k={t("subscription.currency")} v={sub.plan_currency || "—"} />
              <Row k={t("subscription.billingCycle")} v={sub.billing_cycle || "—"} />
              <Row k={t("subscription.startDate")} v={sub.start_date ? formatUserDate(sub.start_date, userTimezone) : "—"} />
              <Row k={t("subscription.renewDate")} v={sub.renew_date ? formatUserDate(sub.renew_date, userTimezone) : "—"} />
              <Row
                k={t("subscription.daysRemaining")}
                v={sub.days_remaining != null ? String(sub.days_remaining) : "∞"}
                warn={sub.days_remaining != null && sub.days_remaining <= 7 && sub.days_remaining > 0}
              />
            </div>
          ) : (
            <div className="flex flex-col items-center gap-3 py-4">
              <EmptyState
                icon="credit-card"
                title={t("subscription.noActive")}
                description={t("subscription.noActiveDesc")}
              />
              <Button onClick={() => router.push("/dashboard/billing")}>
                {t("subscription.viewPlans")}
              </Button>
            </div>
          )}
        </Card>

        <Card title={t("subscription.actions")} icon="zap">
          <div className="flex flex-col gap-2">
            {sub ? (
              <>
                <Button
                  variant="danger"
                  icon="x-circle"
                  onClick={() => setConfirmCancel(true)}
                  disabled={busy}
                >
                  {t("subscription.cancel")}
                </Button>
                <p className="text-xs text-ink-muted">
                  {t("subscription.cancelNote")}
                </p>
              </>
            ) : (
              <Button onClick={() => router.push("/dashboard/billing")}>
                {t("subscription.browsePlans")}
              </Button>
            )}
          </div>
        </Card>
      </div>

      <ConfirmDialog
        open={confirmCancel}
        title={t("subscription.cancelTitle")}
        description={t("subscription.cancelDesc")}
        confirmLabel={t("subscription.cancel")}
        tone="danger"
        loading={busy}
        onConfirm={handleCancel}
        onCancel={() => setConfirmCancel(false)}
      />
    </div>
  );
}

function Row({ k, v, active, warn, strong }: { k: string; v: string; active?: boolean; warn?: boolean; strong?: boolean }) {
  const cls = active ? "text-ok" : warn ? "text-warn font-medium" : "text-ink";
  return (
    <div className="flex items-center justify-between">
      <span className="text-ink-soft">{k}</span>
      <span className={`${strong ? "font-semibold capitalize" : ""} ${cls}`}>{v}</span>
    </div>
  );
}
