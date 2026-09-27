"use client";

import { useEffect, useState, useCallback } from "react";
import PermissionGuard from "@/components/auth/permission_guard";
import { listAdminAccounts, updateAdminAccount, pauseAdminAccount, resumeAdminAccount, disableAdminAccount } from "@/lib/api";
import { Badge, Button, Card, PageHeader, Table, Td, Skeleton, type BadgeTone } from "@ds/components/ui";
import { hasPermission } from "@/lib/auth";

const ENGINE_TONE: Record<string, BadgeTone> = {
  ACTIVE: "green",
  WAITING_ACTIVATION: "amber",
  SUSPENDED: "red",
  DISABLED: "gray",
  REMOVED: "gray",
  STOPPED: "gray",
};

export default function MT5AccountsPage() {
  const [accounts, setAccounts] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);

  const canUpdate = hasPermission("accounts.update");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listAdminAccounts("?limit=200");
      setAccounts(res.items || []);
      setTotal(res.total);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const run = async (id: string, fn: () => Promise<unknown>) => {
    setBusyId(id);
    setError("");
    try {
      await fn();
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusyId(null);
    }
  };

  const toggleRealTrading = (acc: any) =>
    run(acc.id, () => updateAdminAccount(acc.id, { real_trading_enabled: !acc.real_trading_enabled }));

  const activeCount = accounts.filter((a) => a.active).length;
  const verifiedCount = accounts.filter((a) => a.verified).length;

  return (
    <PermissionGuard permission="accounts.read">
      <div>
        <PageHeader
          title="MT5 Accounts"
          subtitle={`${total} account${total !== 1 ? "s" : ""} · ${activeCount} active · ${verifiedCount} verified`}
        />

        {error && (
          <div className="bg-danger/10 border border-danger/30 text-danger text-xs px-3 py-2 rounded-lg mb-3">
            {error}
          </div>
        )}

        <Card bodyClassName="p-0">
          <Table columns={["Owner", "Account", "Type", "Balance / Equity", "Engine", "Status", "Real Trading", "Actions"]}>
            {loading ? (
              <tr>
                <td colSpan={8} className="px-4 py-4">
                  <div className="flex flex-col gap-2">
                    <Skeleton className="h-9 w-full" />
                    <Skeleton className="h-9 w-full" />
                    <Skeleton className="h-9 w-full" />
                  </div>
                </td>
              </tr>
            ) : accounts.length === 0 ? (
              <tr>
                <td colSpan={8} className="text-center py-16 text-ink-muted text-sm">
                  <p>No trading accounts found</p>
                  <p className="text-xs mt-1">Accounts appear here once clients connect their MT4/MT5 accounts.</p>
                </td>
              </tr>
            ) : (
            accounts.map((a) => (
              <tr key={a.id} className="hover:bg-hover/60 transition-colors">
                <Td>
                  <div className="text-xs text-ink">{a.user_email || "—"}</div>
                  <div className="text-[10px] text-ink-muted">{a.user_id?.slice(0, 8)}</div>
                </Td>
                <Td>
                  <div className="text-xs font-mono text-ink">{a.login || "—"}</div>
                  <div className="text-[10px] text-ink-muted">{a.broker || "—"}{a.server ? ` @ ${a.server}` : ""}</div>
                  <div className="text-[10px] text-ink-muted">{a.platform || "—"}{a.demo_real ? ` · ${a.demo_real}` : ""}</div>
                </Td>
                <Td>
                  <Badge tone={a.account_type === "FUNDED" ? "green" : a.account_type === "CHALLENGE" ? "amber" : "blue"}>
                    {a.account_type || "—"}
                  </Badge>
                  {a.prop_firm && <div className="text-[10px] text-ink-muted mt-0.5">{a.prop_firm}</div>}
                </Td>
                <Td className="text-xs">
                  <div className="text-ink">${a.balance_snapshot?.toLocaleString() ?? "—"}</div>
                  <div className="text-[10px] text-ink-muted">Eq ${a.equity_snapshot?.toLocaleString() ?? "—"}</div>
                </Td>
                <Td>
                  <Badge tone={ENGINE_TONE[a.engine_status] || "gray"}>{a.engine_status || "—"}</Badge>
                </Td>
                <Td>
                  <div className="flex flex-col gap-0.5">
                    <Badge tone={a.active ? "green" : "gray"}>{a.active ? "Active" : "Inactive"}</Badge>
                    <Badge tone={a.verified ? "green" : "gray"}>{a.verified ? "Verified" : "Unverified"}</Badge>
                  </div>
                </Td>
                <Td>
                  <button type="button" onClick={() => canUpdate && toggleRealTrading(a)} disabled={!canUpdate || busyId === a.id} title="Toggle real trading">
                    <Badge tone={a.real_trading_enabled ? "green" : "gray"}>
                      {a.real_trading_enabled ? "Enabled" : "Disabled"}
                    </Badge>
                  </button>
                </Td>
                <Td>
                  {canUpdate && (
                    <div className="flex gap-1.5">
                      {a.active ? (
                        <Button size="sm" variant="ghost" loading={busyId === a.id} onClick={() => run(a.id, () => pauseAdminAccount(a.id))}>Pause</Button>
                      ) : (
                        <Button size="sm" variant="ghost" loading={busyId === a.id} onClick={() => run(a.id, () => resumeAdminAccount(a.id))}>Resume</Button>
                      )}
                      <Button size="sm" variant="danger" loading={busyId === a.id} onClick={() => run(a.id, () => disableAdminAccount(a.id))}>Disable</Button>
                    </div>
                  )}
                </Td>
              </tr>
            ))
            )}
          </Table>
        </Card>
      </div>
    </PermissionGuard>
  );
}