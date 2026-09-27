"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import PermissionGuard from "@/components/auth/permission_guard";
import { getClient, suspendClient, activateClient, ClientDetail } from "@/lib/api";
import { Badge, Button, Card, PageHeader } from "@ds/components/ui";
import { ConfirmDialog } from "@ds/components/Modal";

function InfoItem({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-[10px] text-ink-muted uppercase tracking-wider font-medium">{label}</div>
      <div className="mt-1">{children}</div>
    </div>
  );
}

export default function ClientDetailPage() {
  const params = useParams<{ clientId: string }>();
  const clientId = params.clientId;
  const [detail, setDetail] = useState<ClientDetail | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirmSuspend, setConfirmSuspend] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await getClient(clientId);
      setDetail(res);
    } catch (e) {
      setError((e as Error).message);
    }
  }, [clientId]);

  useEffect(() => { load(); }, [load]);

  const handleSuspend = async () => {
    setBusy(true);
    try {
      await suspendClient(clientId);
      setConfirmSuspend(false);
      await load();
    }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  };

  const handleActivate = async () => {
    setBusy(true);
    try { await activateClient(clientId); await load(); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  };

  if (error && !detail) {
    return (
      <PermissionGuard permission="clients.read">
        <div className="text-danger text-sm py-8 text-center">{error}</div>
      </PermissionGuard>
    );
  }

  return (
    <PermissionGuard permission="clients.read">
      <div>
        <PageHeader
          title={
            detail
              ? `${detail.first_name || ""} ${detail.last_name || ""}`.trim() || "Client"
              : "Client Details"
          }
          subtitle={
            <>
              <Link href="/dashboard/clients" className="text-xs text-brand-400 hover:underline inline-flex items-center gap-1">
                Back to Clients
              </Link>
            </>
          }
          actions={
            detail && (
              <div className="flex gap-2">
                {detail.account_status === "active" ? (
                  <Button variant="secondary" disabled={busy} onClick={() => setConfirmSuspend(true)}>
                    Suspend
                  </Button>
                ) : (
                  <Button variant="success" icon="play" disabled={busy} onClick={handleActivate}>
                    Activate
                  </Button>
                )}
              </div>
            )
          }
        />

        {error && <div className="text-danger text-sm mb-3">{error}</div>}

        {!detail ? (
          <div className="text-ink-muted text-sm py-16 text-center">Loading client details...</div>
        ) : (
          <div className="space-y-4 text-sm">
            <Card bodyClassName="p-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                <InfoItem label="Email">
                  <span className="font-mono text-xs">{detail.email || "—"}</span>
                </InfoItem>
                <InfoItem label="Status">
                  <Badge tone={detail.account_status === "active" ? "green" : detail.account_status === "suspended" ? "amber" : "gray"}>
                    {detail.account_status}
                  </Badge>
                </InfoItem>
                <InfoItem label="Telegram">
                  {detail.telegram_username ? `@${detail.telegram_username}` : detail.telegram_id || "—"}
                </InfoItem>
                <InfoItem label="Language">{detail.language || "—"}</InfoItem>
                <InfoItem label="Timezone">{detail.timezone || "—"}</InfoItem>
                <InfoItem label="Created">
                  {detail.created_at ? new Date(detail.created_at).toLocaleDateString() : "—"}
                </InfoItem>
              </div>
            </Card>

            <Card title="Subscription" bodyClassName="p-4">
              {detail.subscription ? (
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div>
                    Plan: <span className="font-medium">{detail.subscription.plan || "—"}</span>
                  </div>
                  <div>
                    Active:{" "}
                    <span className={detail.subscription.active ? "text-ok" : "text-danger"}>
                      {detail.subscription.active ? "Yes" : "No"}
                    </span>
                  </div>
                  <div>
                    Start: {detail.subscription.start_date ? new Date(detail.subscription.start_date).toLocaleDateString() : "—"}
                  </div>
                  <div>
                    End: {detail.subscription.end_date ? new Date(detail.subscription.end_date).toLocaleDateString() : "—"}
                  </div>
                </div>
              ) : (
                <div className="text-ink-muted text-xs">No subscription</div>
              )}
            </Card>

            <Card title={`Licenses (${detail.licenses.length})`} bodyClassName="p-4">
              {detail.licenses.length === 0 ? (
                <div className="text-ink-muted text-xs">No licenses</div>
              ) : (
                <div className="space-y-1">
                  {detail.licenses.map((l) => (
                    <div
                      key={l.id}
                      className="flex items-center justify-between bg-input rounded-lg px-3 py-2 text-xs"
                    >
                      <span className="font-mono truncate max-w-[220px]">{l.license_key}</span>
                      <div className="flex items-center gap-2">
                        <span className="text-ink-muted">{l.plan}</span>
                        <Badge tone={l.status === "active" ? "green" : l.status === "revoked" ? "red" : "gray"}>
                          {l.status}
                        </Badge>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>

            <Card title={`MT Accounts (${detail.accounts.length})`} bodyClassName="p-4">
              {detail.accounts.length === 0 ? (
                <div className="text-ink-muted text-xs">No accounts</div>
              ) : (
                <div className="space-y-1">
                  {detail.accounts.map((a) => (
                    <div
                      key={a.id}
                      className="flex items-center justify-between bg-input rounded-lg px-3 py-2 text-xs"
                    >
                      <span className="font-mono">{a.login || "—"}</span>
                      <div className="flex items-center gap-2">
                        <span className="text-ink-muted">{a.platform}</span>
                        <span className="text-ink-muted">{a.broker || "—"}</span>
                        <Badge
                          tone={a.active ? "green" : "gray"}
                        >
                          {a.engine_status || (a.active ? "active" : "inactive")}
                        </Badge>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </div>
        )}

        <ConfirmDialog
          open={confirmSuspend}
          title="Suspend Client"
          description="This will suspend the client account immediately. The client will lose access until reactivated."
          confirmLabel="Suspend"
          tone="danger"
          loading={busy}
          onConfirm={handleSuspend}
          onCancel={() => setConfirmSuspend(false)}
        />
      </div>
    </PermissionGuard>
  );
}
