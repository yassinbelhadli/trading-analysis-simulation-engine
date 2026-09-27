"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getMyLicense, listClientAccounts, type ClientLicense, type LicenseHistoryEntry } from "@/lib/api";
import { PageHeader, Card, Badge, Button, EmptyState, Skeleton, Table, Td } from "@ds/components/ui";
import { useLocale } from "@/components/LocaleContext";

export default function LicensePage() {
  const { t } = useLocale();
  const [licenses, setLicenses] = useState<ClientLicense[]>([]);
  const [history, setHistory] = useState<LicenseHistoryEntry[]>([]);
  const [accountLimits, setAccountLimits] = useState<{ used: number; max: number; unlimited: boolean } | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Single data source: account usage is read from the accounts service so
    // the license page can never disagree with the MT5 Accounts page.
    Promise.all([getMyLicense(), listClientAccounts()])
      .then(([licRes, accRes]) => {
        setLicenses(licRes.items);
        setHistory(licRes.activation_history);
        setAccountLimits({
          used: accRes.limits.used,
          max: accRes.limits.max,
          unlimited: accRes.limits.unlimited,
        });
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="max-w-3xl space-y-4">
        <div className="h-8 w-40 rounded bg-hover animate-pulse" />
        <Skeleton className="h-56 w-full" />
      </div>
    );
  }
  if (error) return <EmptyState icon="alert-triangle" title={t("license.loadError")} description={error} />;

  const used = accountLimits?.used;
  const max = accountLimits?.max;
  // Keep the License page consistent with the MT5 Accounts page: when the
  // active plan is unlimited (enterprise/infinity/unlimited or max>=999),
  // show "Unlimited" instead of a misleading "used / max" ratio.
  const unlimited = accountLimits?.unlimited ?? false;
  const accountsLabel = unlimited ? t("accounts.unlimited") : `${used ?? 0} / ${max ?? 0}`;
  const accountsWarn = !unlimited && used != null && max != null && used >= max;

  return (
    <div className="max-w-3xl flex flex-col gap-5">
      <PageHeader title={t("license.title")} subtitle={t("license.subtitle")} />

      {licenses.length === 0 ? (
        <EmptyState
          icon="key"
          title={t("license.noLicensesTitle")}
          description={t("license.noLicensesDesc")}
        />
      ) : (
        <div className="flex flex-col gap-4">
          {licenses.map((l) => (
            <Card
              key={l.id}
              title={t("license.key")}
              icon="key"
              actions={
                <Badge
                  tone={
                    l.status === "active" ? "green" : l.status === "expired" ? "red" : "amber"
                  }
                >
                  {l.status === "active" ? t("license.active") : l.status.toUpperCase()}
                </Badge>
              }
            >
              <div className="font-mono text-lg tracking-widest text-brand-400 break-all">
                {l.license_key}
              </div>

              <div className="mt-4 grid grid-cols-2 sm:grid-cols-3 gap-x-4 gap-y-3 text-sm">
                <Info k={t("license.plan")} v={l.plan} />
                <Info k={t("license.expires")} v={l.expires_at ? new Date(l.expires_at).toLocaleDateString() : t("license.lifetime")} />
                <Info k={t("license.activated")} v={l.created_at ? new Date(l.created_at).toLocaleDateString() : "—"} />
                <Info
                  k={t("license.mt5Accounts")}
                  v={unlimited ? t("accounts.unlimited") : `${used ?? l.used_accounts} / ${max ?? l.max_accounts}`}
                  warn={accountsWarn}
                />
                <Info k={t("license.boundAccount")} v={l.bound_account_id ? `${l.bound_account_id.slice(0, 8)}…` : t("license.notBound")} />
                <Info k={t("license.daysRemaining")} v={l.days_remaining != null ? String(l.days_remaining) : "∞"} />
                <Info k={t("license.transfer")} v={l.transfer_locked ? t("license.transferLocked") : t("license.transferOpen")} />
              </div>

              <div className="mt-5 flex justify-end">
                <Link href="/dashboard/downloads">
                  <Button size="sm" icon="download">{t("license.downloadEa")}</Button>
                </Link>
              </div>
            </Card>
          ))}

          {history.length > 0 && (
            <Card title={t("license.history")} icon="scroll">
              <Table
                columns={[t("license.event"), t("license.date"), t("license.details")]}
              >
                {history.map((h, i) => (
                  <tr key={`${h.event_type}-${i}`}>
                    <Td mono className="text-xs text-brand-400">{h.event_type}</Td>
                    <Td className="text-ink-soft text-xs">
                      {h.created_at ? new Date(h.created_at).toLocaleString() : "—"}
                    </Td>
                    <Td className="text-ink-soft text-xs">{h.message}</Td>
                  </tr>
                ))}
              </Table>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}

function Info({ k, v, warn }: { k: string; v: string; warn?: boolean }) {
  return (
    <div>
      <div className="text-xs text-ink-muted">{k}</div>
      <div className={`mt-0.5 ${warn ? "text-warn font-medium" : "text-ink"}`}>{v}</div>
    </div>
  );
}
