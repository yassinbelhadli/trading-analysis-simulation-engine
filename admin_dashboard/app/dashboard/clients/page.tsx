"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import PermissionGuard from "@/components/auth/permission_guard";
import { listClients, suspendClient, activateClient, ClientItem } from "@/lib/api";
import { Badge, Button, Card, PageHeader, Table, Td, TextField, Skeleton } from "@ds/components/ui";
import { ConfirmDialog } from "@ds/components/Modal";
import { parseApiError } from "@/lib/errors";
import { hasPermission } from "@/lib/auth";

export default function ClientsPage() {
  const router = useRouter();
  const [clients, setClients] = useState<ClientItem[]>([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [suspendId, setSuspendId] = useState<string | null>(null);
  const [suspendBusy, setSuspendBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  const LIMIT = 20;
  const canUpdate = hasPermission("clients.update");
  const canSuspend = hasPermission("clients.suspend");

  const load = useCallback(async (q: string, off: number) => {
    setLoading(true);
    const params = `?limit=${LIMIT}&offset=${off}${q ? `&q=${encodeURIComponent(q)}` : ""}`;
    try {
      const res = await listClients(params);
      setClients(res.items);
      setTotal(res.total);
    } catch (e) {
      setError(parseApiError(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(search, offset); }, [load, search, offset]);

  const handleSuspend = async (id: string) => {
    setSuspendBusy(true);
    try {
      await suspendClient(id);
      setSuspendId(null);
      load(search, offset);
    } catch (e) { setError(parseApiError(e)); }
    finally { setSuspendBusy(false); }
  };

  const handleActivate = async (id: string) => {
    try { await activateClient(id); load(search, offset); }
    catch (e) { setError(parseApiError(e)); }
  };

  return (
    <PermissionGuard permission="clients.read">
      <div>
        <PageHeader
          title="Clients"
          subtitle="Client accounts, subscriptions and access status."
          actions={
            <TextField
              icon="search"
              placeholder="Search clients..."
              value={search}
              onChange={(e) => { setSearch(e.target.value); setOffset(0); }}
              className="w-64"
            />
          }
        />

        {error && <div className="text-danger text-sm mb-3">{error}</div>}

        <Card bodyClassName="p-0">
          <Table columns={["Name", "Email", "Status", "Plan", "Accounts", "Licenses", "Actions"]}>
            {loading ? (
              <tr>
                <td colSpan={7} className="px-4 py-4">
                  <div className="flex flex-col gap-2">
                    <Skeleton className="h-9 w-full" />
                    <Skeleton className="h-9 w-full" />
                    <Skeleton className="h-9 w-full" />
                  </div>
                </td>
              </tr>
            ) : clients.length === 0 ? (
              <tr>
                <td colSpan={7} className="text-center text-ink-muted py-8 px-4">
                  No clients found
                </td>
              </tr>
            ) : (
            clients.map((c) => (
              <tr key={c.id}>
                <Td>
                  {c.first_name || c.last_name ? `${c.first_name || ""} ${c.last_name || ""}`.trim() : "—"}
                </Td>
                <Td mono>{c.email || "—"}</Td>
                <Td>
                  <Badge tone={c.account_status === "active" ? "green" : c.account_status === "suspended" ? "amber" : "gray"}>
                    {c.account_status}
                  </Badge>
                </Td>
                <Td>
                  {c.subscription_plan ? (
                    <Badge tone={c.subscription_active ? "green" : "gray"}>{c.subscription_plan}</Badge>
                  ) : (
                    "—"
                  )}
                </Td>
                <Td>{c.accounts_count}</Td>
                <Td>{c.licenses_count}</Td>
                <Td>
                  <div className="flex gap-1">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => router.push(`/dashboard/clients/${c.id}`)}
                    >
                      View
                    </Button>
                    {c.account_status === "active" ? (
                      canSuspend && (
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => setSuspendId(c.id)}
                      >
                        Suspend
                      </Button>
                      )
                    ) : (
                      canSuspend && (
                      <Button size="sm" variant="success" icon="play" onClick={() => handleActivate(c.id)}>
                        Activate
                      </Button>
                      )
                    )}
                  </div>
                </Td>
              </tr>
            ))
            )}
          </Table>
        </Card>

        {total > LIMIT && (
          <div className="flex items-center justify-between mt-4 text-sm text-ink-muted">
            <span>{total} total</span>
            <div className="flex gap-2">
              <Button size="sm" variant="secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - LIMIT))}>
                Previous
              </Button>
              <Button size="sm" variant="secondary" disabled={offset + LIMIT >= total} onClick={() => setOffset(offset + LIMIT)}>
                Next
              </Button>
            </div>
          </div>
        )}

        <ConfirmDialog
          open={!!suspendId}
          title="Suspend Client"
          description="This will suspend the client account immediately. The client will lose access until reactivated."
          confirmLabel="Suspend"
          tone="danger"
          loading={suspendBusy}
          onConfirm={() => suspendId && handleSuspend(suspendId)}
          onCancel={() => setSuspendId(null)}
        />
      </div>
    </PermissionGuard>
  );
}
