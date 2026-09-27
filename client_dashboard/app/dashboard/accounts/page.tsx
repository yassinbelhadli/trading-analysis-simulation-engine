"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  listClientAccounts,
  addClientAccount,
  renameClientAccount,
  deleteClientAccount,
  disconnectClientAccount,
  reconnectClientAccount,
  type ClientAccount,
  type AccountLimits,
} from "@/lib/api";
import { Notice, type NoticeState } from "@/components/Notice";
import { PageHeader, Card, Button, Badge, StatusPill, EmptyState, TextField, SelectField, Skeleton } from "@ds/components/ui";
import { ConfirmDialog } from "@ds/components/Modal";
import { parseApiError } from "@/lib/errors";
import { useLocale } from "@/components/LocaleContext";

export default function AccountsPage() {
  const { t } = useLocale();
  const [accounts, setAccounts] = useState<ClientAccount[]>([]);
  const [limits, setLimits] = useState<AccountLimits | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState<NoticeState>(null);
  const [busy, setBusy] = useState(false);

  const [platform, setPlatform] = useState("MT5");
  const [server, setServer] = useState("");
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [accountType, setAccountType] = useState("PERSONAL");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [showAdd, setShowAdd] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<ClientAccount | null>(null);

  const refresh = () =>
    listClientAccounts()
      .then((r) => { setAccounts(r.items); setLimits(r.limits); })
      .catch((e) => setError(parseApiError(e)))
      .finally(() => setLoading(false));

  useEffect(() => { refresh(); }, []);

  const handleAdd = async () => {
    setStatus(null);
    setBusy(true);
    try {
      const res = await addClientAccount({ platform, server, login, password, name, account_type: accountType });
      setStatus({ ok: true, text: t("accounts.added", { platform: res.account.platform }) });
      setServer(""); setLogin(""); setPassword(""); setName(""); setAccountType("PERSONAL"); setShowAdd(false);
      refresh();
    } catch (err) {
      setStatus({ ok: false, text: err instanceof Error ? err.message : t("accounts.addFailed") });
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async (a: ClientAccount) => {
    setDeleteTarget(null);
    setStatus(null);
    try {
      await deleteClientAccount(a.id);
      setStatus({ ok: true, text: t("accounts.removed") });
      refresh();
    } catch (err) {
      setStatus({ ok: false, text: err instanceof Error ? err.message : t("accounts.removeFailed") });
    }
  };

  const handleToggleConnection = async (a: ClientAccount) => {
    setStatus(null);
    try {
      if (a.connected) {
        await disconnectClientAccount(a.id);
        setStatus({ ok: true, text: t("accounts.disconnectedMsg") });
      } else {
        await reconnectClientAccount(a.id);
        setStatus({ ok: true, text: t("accounts.reconnectedMsg") });
      }
      refresh();
    } catch (err) {
      setStatus({ ok: false, text: err instanceof Error ? err.message : t("accounts.opFailed") });
    }
  };

  const handleRenameSave = async (a: ClientAccount) => {
    setStatus(null);
    try {
      await renameClientAccount(a.id, editName);
      setEditingId(null);
      setStatus({ ok: true, text: t("accounts.renamedMsg") });
      refresh();
    } catch (err) {
      setStatus({ ok: false, text: err instanceof Error ? err.message : t("accounts.renameFailed") });
    }
  };

  const usedLabel = limits?.unlimited
    ? t("accounts.unlimited")
    : t("accounts.usedLabel", { used: limits?.used ?? 0, max: limits?.max ?? 0 });

  const noLicense = !!limits && !limits.unlimited && limits.max === 0;

  if (loading) {
    return (
      <div className="max-w-4xl flex flex-col gap-5">
        <div className="h-8 w-64 rounded bg-hover animate-pulse" />
        <Skeleton className="h-64 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }
  if (error) {
    return (
      <EmptyState icon="alert-triangle" title={t("accounts.loadError")} description={error} />
    );
  }

  return (
    <div className="max-w-4xl flex flex-col gap-5">
      <PageHeader title={t("accounts.title")} subtitle={t("accounts.subtitle", { used: usedLabel })} />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <Button
          variant={showAdd ? "secondary" : "primary"}
          icon={showAdd ? "close" : "plus"}
          onClick={() => setShowAdd((v) => !v)}
          disabled={noLicense}
        >
          {showAdd ? t("accounts.cancel") : t("accounts.add")}
        </Button>
        {noLicense && (
          <p className="text-xs text-ink-muted">
            {t("accounts.noLicenseHint")}
          </p>
        )}
      </div>

      {noLicense && (
        <EmptyState
          icon="key"
          title={t("accounts.noLicenseTitle")}
          description={t("accounts.noLicenseDesc")}
          action={
            <Link href="/dashboard/license">
              <Button size="sm" icon="key">{t("accounts.viewLicense")}</Button>
            </Link>
          }
        />
      )}

      <Notice state={status} />

      {showAdd && (
        <Card title={t("accounts.addTitle")} icon="plug">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <SelectField
              label={t("accounts.platform")}
              value={platform}
              onChange={(e) => setPlatform(e.target.value)}
            >
              <option>MT5</option>
            </SelectField>
            <SelectField
              label={t("accounts.accountType")}
              value={accountType}
              onChange={(e) => setAccountType(e.target.value)}
            >
              <option value="PERSONAL">{t("accounts.personal")}</option>
              <option value="FUNDED">{t("accounts.funded")}</option>
            </SelectField>
            <TextField
              label={t("accounts.displayName")}
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. FTMO Demo"
            />
            <TextField
              label={t("accounts.server")}
              value={server}
              onChange={(e) => setServer(e.target.value)}
              placeholder="e.g. FTMO-Demo"
            />
            <TextField
              label={t("accounts.accountNumber")}
              value={login}
              onChange={(e) => {
                const v = e.target.value;
                // Only allow digits — MT5 account numbers are numeric
                if (v === "" || /^\d+$/.test(v)) setLogin(v);
              }}
              placeholder="e.g. 12345678"
            />
            {login && !/^\d+$/.test(login) && (
              <p className="text-xs text-danger -mt-2">{t("accounts.digitsOnly")}</p>
            )}
            <div className="sm:col-span-2">
              <TextField
                label={t("accounts.password")}
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Investor / master password"
              />
            </div>
          </div>
          <div className="mt-4 flex justify-end">
            <Button
              icon="plug"
              onClick={handleAdd}
              disabled={busy || !server || !login || !password}
              loading={busy}
            >
              {busy ? t("accounts.connecting") : t("accounts.verifyConnect")}
            </Button>
          </div>
          <p className="text-xs text-ink-muted mt-3">
            {t("accounts.credentialsNote")}
          </p>
        </Card>
      )}

      {accounts.length === 0 && !showAdd ? (
        <EmptyState
          icon="server"
          title={t("accounts.noAccountsTitle")}
          description={t("accounts.noAccountsDesc")}
        />
      ) : (
        <div className="flex flex-col gap-3">
          {accounts.map((a) => (
            <Card key={a.id} bodyClassName="p-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <Link href={`/dashboard/accounts/${a.id}`} className="min-w-0 flex-1 hover:opacity-80">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-semibold truncate text-ink">{a.name}</span>
                    <Badge tone="blue">{a.platform}</Badge>
                    <StatusPill status={a.connected ? "active" : "error"}>
                      {a.connected ? t("accounts.connected") : t("accounts.disconnected")}
                    </StatusPill>
                  </div>
                  <div className="text-xs text-ink-muted mt-1">
                    {a.broker} · {a.server || "—"} · #{a.login || "—"} · {a.leverage || "—"}
                  </div>
                </Link>
                <div className="flex items-center gap-2">
                  {editingId === a.id ? (
                    <>
                      <div className="w-40">
                        <TextField
                          value={editName}
                          onChange={(e) => setEditName(e.target.value)}
                          autoFocus
                        />
                      </div>
                      <Button size="sm" icon="check" onClick={() => handleRenameSave(a)}>
                        {t("accounts.save")}
                      </Button>
                      <Button size="sm" variant="secondary" icon="close" onClick={() => setEditingId(null)}>
                        {t("accounts.cancel")}
                      </Button>
                    </>
                  ) : (
                    <Button
                      size="sm"
                      variant="secondary"
                      icon="edit"
                      onClick={() => { setEditingId(a.id); setEditName(a.name); }}
                    >
                      {t("accounts.rename")}
                    </Button>
                  )}
                  <Button
                    size="sm"
                    variant="secondary"
                    icon="power"
                    onClick={() => handleToggleConnection(a)}
                  >
                    {a.connected ? t("accounts.disconnect") : t("accounts.reconnect")}
                  </Button>
                  <Button
                    size="sm"
                    variant="danger"
                    icon="trash"
                    onClick={() => setDeleteTarget(a)}
                  >
                    {t("accounts.remove")}
                  </Button>
                </div>
              </div>

              <div className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-x-4 gap-y-2 text-sm border-t border-line/60 pt-3">
                <Stat k={t("accounts.balance")} v={`${a.currency} ${a.balance != null ? a.balance.toLocaleString() : "—"}`} />
                <Stat k={t("accounts.equity")} v={`${a.currency} ${a.equity != null ? a.equity.toLocaleString() : "—"}`} />
                <Stat k={t("accounts.engine")} v={a.engine_status} warn={a.engine_status !== "ACTIVE"} />
                <Stat k={t("accounts.lastSync")} v={a.last_sync ? new Date(a.last_sync).toLocaleString() : "—"} />
              </div>
            </Card>
          ))}
        </div>
      )}

      <ConfirmDialog
        open={!!deleteTarget}
        title={t("accounts.removeTitle")}
        description={t("accounts.removeDesc", { name: deleteTarget?.name ?? "" })}
        confirmLabel={t("accounts.remove")}
        tone="danger"
        loading={busy}
        onConfirm={() => deleteTarget && handleDelete(deleteTarget)}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}

function Stat({ k, v, warn }: { k: string; v: string; warn?: boolean }) {
  return (
    <div>
      <div className="text-xs text-ink-muted">{k}</div>
      <div className={`mt-0.5 ${warn ? "text-warn font-medium" : "text-ink"}`}>{v}</div>
    </div>
  );
}
