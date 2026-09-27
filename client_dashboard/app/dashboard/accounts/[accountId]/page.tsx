"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  listClientAccounts,
  renameClientAccount,
  disconnectClientAccount,
  reconnectClientAccount,
  deleteClientAccount,
  type ClientAccount,
} from "@/lib/api";
import { Notice, type NoticeState } from "@/components/Notice";
import { PageHeader, Card, Button, Badge, StatusPill, EmptyState, TextField, Skeleton } from "@ds/components/ui";
import { Icon } from "@ds/components/Icon";
import { ConfirmDialog } from "@ds/components/Modal";
import { useLocale } from "@/components/LocaleContext";

function maskLogin(login: string | null): string {
  if (!login) return "—";
  if (login.length <= 4) return "•".repeat(login.length);
  return `${login.slice(0, 2)}••••${login.slice(-4)}`;
}

export default function AccountDetailsPage() {
  const { t } = useLocale();
  const params = useParams<{ accountId: string }>();
  const accountId = params.accountId;
  const router = useRouter();

  const [account, setAccount] = useState<ClientAccount | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState("");
  const [status, setStatus] = useState<NoticeState>(null);
  const [busy, setBusy] = useState(false);

  const [editing, setEditing] = useState(false);
  const [name, setName] = useState("");
  const [reconnectPw, setReconnectPw] = useState("");
  const [confirmRemove, setConfirmRemove] = useState(false);
  const [confirmDisconnect, setConfirmDisconnect] = useState(false);

  const refresh = () =>
    listClientAccounts()
      .then((r) => {
        const found = r.items.find((a) => a.id === accountId) || null;
        if (!found) {
          setNotFound(true);
        } else {
          setAccount(found);
        }
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));

  useEffect(() => { refresh(); }, [accountId]);

  const handleRename = async () => {
    if (!account) return;
    setStatus(null);
    try {
      const res = await renameClientAccount(account.id, name);
      setAccount(res.account);
      setEditing(false);
      setStatus({ ok: true, text: t("accountDetail.renamedMsg") });
    } catch (err) {
      setStatus({ ok: false, text: err instanceof Error ? err.message : t("accountDetail.renameFailed") });
    }
  };

  const handleDisconnect = async () => {
    if (!account) return;
    setConfirmDisconnect(false);
    setStatus(null);
    setBusy(true);
    try {
      const res = await disconnectClientAccount(account.id);
      setAccount(res.account);
      setStatus({ ok: true, text: t("accountDetail.disconnectedMsg") });
    } catch (err) {
      setStatus({ ok: false, text: err instanceof Error ? err.message : t("accountDetail.disconnectFailed") });
    } finally {
      setBusy(false);
    }
  };

  const handleReconnect = async () => {
    if (!account) return;
    setStatus(null);
    setBusy(true);
    try {
      const res = await reconnectClientAccount(account.id, reconnectPw);
      setAccount(res.account);
      setReconnectPw("");
      setStatus({ ok: true, text: t("accountDetail.reconnectedMsg") });
    } catch (err) {
      setStatus({ ok: false, text: err instanceof Error ? err.message : t("accountDetail.reconnectFailed") });
    } finally {
      setBusy(false);
    }
  };

  const handleRemove = async () => {
    if (!account) return;
    setConfirmRemove(false);
    setStatus(null);
    setBusy(true);
    try {
      await deleteClientAccount(account.id);
      router.replace("/dashboard/accounts");
    } catch (err) {
      setStatus({ ok: false, text: err instanceof Error ? err.message : t("accountDetail.removeFailed") });
      setBusy(false);
    }
  };

  if (loading) {
    return (
      <div className="max-w-3xl flex flex-col gap-5">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-80 w-full" />
      </div>
    );
  }
  if (notFound) {
    return (
      <div className="max-w-xl mx-auto">
        <EmptyState
          icon="search"
          title={t("accountDetail.notFoundTitle")}
          description={t("accountDetail.notFoundDesc")}
          action={
            <Link href="/dashboard/accounts">
              <Button size="sm" icon="arrow-left">{t("accountDetail.backToAccounts")}</Button>
            </Link>
          }
        />
      </div>
    );
  }
  if (error) {
    return <EmptyState icon="alert-triangle" title={t("accountDetail.loadError")} description={error} />;
  }
  if (!account) return null;

  return (
    <div className="max-w-3xl flex flex-col gap-5">
      <PageHeader
        title={account.name}
        subtitle={
          <Link href="/dashboard/accounts" className="inline-flex items-center gap-1 text-xs text-ink-muted hover:text-brand-400">
            <Icon name="arrow-left" className="h-3.5 w-3.5" />
            {t("accountDetail.backToAccounts")}
          </Link>
        }
        actions={
          <Button variant="danger" size="sm" icon="trash" onClick={() => setConfirmRemove(true)}>
            {t("accountDetail.removeAccount")}
          </Button>
        }
      />

      <Notice state={status} />

      <Card>
        <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
          <div className="flex items-center gap-2">
            <Badge tone="blue">{account.platform}</Badge>
            <StatusPill status={account.connected ? "active" : "error"}>
              {account.connected ? t("accountDetail.connected") : t("accountDetail.disconnected")}
            </StatusPill>
            <Badge tone={account.verified ? "green" : "amber"}>
              {account.verified ? t("accountDetail.verified") : t("accountDetail.pending")}
            </Badge>
          </div>
          {editing ? (
            <div className="flex items-center gap-2">
              <div className="w-44">
                <TextField
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  autoFocus
                />
              </div>
              <Button size="sm" icon="check" onClick={handleRename}>{t("accountDetail.save")}</Button>
              <Button size="sm" variant="secondary" icon="close" onClick={() => setEditing(false)}>{t("accountDetail.cancel")}</Button>
            </div>
          ) : (
            <Button
              size="sm"
              variant="secondary"
              icon="edit"
              onClick={() => { setEditing(true); setName(account.name); }}
            >
              {t("accountDetail.rename")}
            </Button>
          )}
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-4 gap-y-3 text-sm">
          <InfoRow k={t("accountDetail.fieldPlatform")} v={account.platform} />
          <InfoRow k={t("accountDetail.fieldServer")} v={account.server || "—"} />
          <InfoRow k={t("accountDetail.fieldLogin")} v={maskLogin(account.login)} />
          <InfoRow k={t("accountDetail.fieldBroker")} v={account.broker || "—"} />
          <InfoRow k={t("accountDetail.fieldAccountType")} v={account.account_type || "—"} />
          <InfoRow k={t("accountDetail.fieldType")} v={account.demo_real || "—"} />
          <InfoRow k={t("accountDetail.fieldBalance")} v={`${account.currency} ${account.balance != null ? account.balance.toLocaleString() : "—"}`} />
          <InfoRow k={t("accountDetail.fieldEquity")} v={`${account.currency} ${account.equity != null ? account.equity.toLocaleString() : "—"}`} />
          <InfoRow k={t("accountDetail.fieldLeverage")} v={account.leverage || "—"} />
          <InfoRow k={t("accountDetail.fieldEngineStatus")} v={account.engine_status || "—"} warn={account.engine_status !== "ACTIVE"} />
          <InfoRow k={t("accountDetail.fieldLastSync")} v={account.last_sync ? new Date(account.last_sync).toLocaleString() : "—"} />
          <InfoRow k={t("accountDetail.fieldLicense")} v={account.license_id ? t("accountDetail.bound") : t("accountDetail.notBound")} />
        </div>

        <div className="mt-5 pt-4 border-t border-line/60 flex flex-wrap gap-2">
          {account.connected ? (
            <Button variant="secondary" icon="power" onClick={() => setConfirmDisconnect(true)} disabled={busy}>
              {t("accountDetail.disconnect")}
            </Button>
          ) : (
            <>
              <div className="flex-1 min-w-[200px]">
                <TextField
                  type="password"
                  value={reconnectPw}
                  onChange={(e) => setReconnectPw(e.target.value)}
                  placeholder={t("accountDetail.brokerPwPh")}
                />
              </div>
              <Button icon="plug" onClick={handleReconnect} disabled={busy} loading={busy}>
                {t("accountDetail.reconnect")}
              </Button>
            </>
          )}
        </div>
        <p className="text-xs text-ink-muted mt-3">
          {t("accountDetail.credentialsNote")}
        </p>
      </Card>

      <ConfirmDialog
        open={confirmDisconnect}
        title={t("accountDetail.disconnectTitle")}
        description={t("accountDetail.disconnectDesc", { name: account.name })}
        confirmLabel={t("accountDetail.disconnect")}
        loading={busy}
        onConfirm={handleDisconnect}
        onCancel={() => setConfirmDisconnect(false)}
      />
      <ConfirmDialog
        open={confirmRemove}
        title={t("accountDetail.removeTitle")}
        description={t("accountDetail.removeDesc", { name: account.name })}
        confirmLabel={t("accountDetail.remove")}
        tone="danger"
        requireText={account.name}
        loading={busy}
        onConfirm={handleRemove}
        onCancel={() => setConfirmRemove(false)}
      />
    </div>
  );
}

function InfoRow({ k, v, warn }: { k: string; v: string; warn?: boolean }) {
  return (
    <div>
      <div className="text-xs text-ink-muted">{k}</div>
      <div className={`mt-0.5 ${warn ? "text-warn font-medium" : "text-ink"}`}>{v}</div>
    </div>
  );
}
