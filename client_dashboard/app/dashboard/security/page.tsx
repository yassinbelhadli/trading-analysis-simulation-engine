"use client";

import { useCallback, useEffect, useState } from "react";
import {
  getMe,
  setup2FA,
  enable2FA,
  disable2FA,
  listSessions,
  revokeSession,
  type MeResponse,
  type SessionInfo,
} from "@/lib/auth";
import { Notice, type NoticeState } from "@/components/Notice";
import { PageHeader, Card, Button, Badge, StatusPill, TextField, EmptyState, Skeleton } from "@ds/components/ui";
import { ConfirmDialog } from "@ds/components/Modal";
import { useLocale } from "@/components/LocaleContext";

export default function SecurityPage() {
  const { t } = useLocale();
  const [me, setMe] = useState<MeResponse | null>(null);
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [status, setStatus] = useState<NoticeState>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const [pw, setPw] = useState("");
  const [secret, setSecret] = useState("");
  const [otpauthUri, setOtpauthUri] = useState("");
  const [enableCode, setEnableCode] = useState("");
  const [disableCode, setDisableCode] = useState("");
  const [revokeTarget, setRevokeTarget] = useState<SessionInfo | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [m, s] = await Promise.all([getMe(), listSessions()]);
      setMe(m);
      setSessions(s.sessions);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("security.loadError"));
    }
  }, [t]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const handleSetup = async () => {
    setStatus(null);
    setBusy(true);
    try {
      const res = await setup2FA(pw);
      setSecret(res.secret);
      setOtpauthUri(res.otpauth_uri);
      setPw("");
    } catch (err) {
      setStatus({ ok: false, text: err instanceof Error ? err.message : t("security.setupFailed") });
    } finally {
      setBusy(false);
    }
  };

  const handleEnable = async () => {
    setStatus(null);
    setBusy(true);
    try {
      await enable2FA(enableCode);
      setEnableCode("");
      setSecret("");
      setOtpauthUri("");
      setStatus({ ok: true, text: t("security.enabled2fa") });
      refresh();
    } catch (err) {
      setStatus({ ok: false, text: err instanceof Error ? err.message : t("security.enableFailed") });
    } finally {
      setBusy(false);
    }
  };

  const handleDisable = async () => {
    setStatus(null);
    setBusy(true);
    try {
      await disable2FA(disableCode);
      setDisableCode("");
      setStatus({ ok: true, text: t("security.disabled2fa") });
      refresh();
    } catch (err) {
      setStatus({ ok: false, text: err instanceof Error ? err.message : t("security.disableFailed") });
    } finally {
      setBusy(false);
    }
  };

  const handleCancelSetup = () => {
    setSecret("");
    setOtpauthUri("");
    setEnableCode("");
  };

  const handleRevoke = async (id: string) => {
    setRevokeTarget(null);
    setStatus(null);
    try {
      await revokeSession(id);
      setStatus({ ok: true, text: t("security.sessionRevoked") });
      refresh();
    } catch (err) {
      setStatus({ ok: false, text: err instanceof Error ? err.message : t("security.revokeFailed") });
    }
  };

  if (error && !me) {
    return <EmptyState icon="alert-triangle" title={t("security.loadError")} description={error} />;
  }
  if (!me) {
    return (
      <div className="max-w-3xl flex flex-col gap-5">
        <div className="h-8 w-44 rounded bg-hover animate-pulse" />
        <Skeleton className="h-72 w-full" />
        <Skeleton className="h-56 w-full" />
      </div>
    );
  }

  const twoFactorState = me.two_factor_enabled
    ? { tone: "green" as const, label: t("security.enabledLabel") }
    : me.two_factor_pending
      ? { tone: "blue" as const, label: t("security.setupPending") }
      : { tone: "gray" as const, label: t("security.disabledLabel") };

  return (
    <div className="max-w-3xl flex flex-col gap-5">
      <PageHeader title={t("security.title")} subtitle={t("security.subtitle")} />

      <Notice state={status} />

      {/* Two-Factor Authentication */}
      <Card
        title={t("security.2faTitle")}
        icon="shield-check"
        actions={<Badge tone={twoFactorState.tone}>{twoFactorState.label}</Badge>}
      >
        <p className="text-sm text-ink-soft mb-4">
          {me.two_factor_enabled
            ? t("security.2faEnabledDesc")
            : me.two_factor_pending
              ? t("security.2faSetupDesc")
              : t("security.2faDisabledDesc")}
        </p>

        {!me.two_factor_enabled && !secret && (
          <div className="flex flex-col gap-3 max-w-md">
            <TextField
              type="password"
              label={t("security.currentPassword")}
              value={pw}
              onChange={(e) => setPw(e.target.value)}
              placeholder={t("security.currentPassword")}
              icon="lock"
            />
            <div>
              <Button icon="shield-check" onClick={handleSetup} disabled={busy || !pw} loading={busy}>
                {busy ? t("security.working") : t("security.setup2fa")}
              </Button>
            </div>
          </div>
        )}

        {secret && (
          <div className="flex flex-col gap-3">
            <div className="rounded-lg border border-line bg-input p-4">
              <p className="text-xs text-ink-muted mb-2">
                {t("security.qrInstruction")}
              </p>
              {otpauthUri && (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={`https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(otpauthUri)}`}
                  alt="2FA QR code"
                  className="mx-auto rounded-lg"
                  width={180}
                  height={180}
                />
              )}
              <p className="text-center font-mono text-sm text-brand-400 mt-3 tracking-widest select-all">{secret}</p>
            </div>
            <div className="flex flex-col sm:flex-row gap-2 max-w-md">
              <div className="flex-1">
                <TextField
                  value={enableCode}
                  onChange={(e) => setEnableCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                  placeholder={t("security.digitCode")}
                  inputMode="numeric"
                  className="[&_input]:text-center [&_input]:font-mono [&_input]:tracking-widest"
                />
              </div>
              <div className="flex gap-2">
                <Button onClick={handleEnable} disabled={busy || enableCode.length < 6} loading={busy}>
                  {t("security.confirmEnable")}
                </Button>
                <Button variant="secondary" onClick={handleCancelSetup} disabled={busy}>
                  {t("support.cancel")}
                </Button>
              </div>
            </div>
          </div>
        )}

        {me.two_factor_enabled && (
          <div className="flex items-center gap-2 mb-3">
            <StatusPill status="active">{t("security.enabledLabel")}</StatusPill>
          </div>
        )}

        {me.two_factor_enabled && (
          <div className="flex flex-col sm:flex-row gap-2 max-w-md">
            <div className="flex-1">
              <TextField
                value={disableCode}
                onChange={(e) => setDisableCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                placeholder={t("security.disableAuthCode")}
                inputMode="numeric"
                className="[&_input]:text-center [&_input]:font-mono [&_input]:tracking-widest"
              />
            </div>
            <Button variant="danger" icon="shield" onClick={handleDisable} disabled={busy || disableCode.length < 6} loading={busy}>
              {t("security.disable2fa")}
            </Button>
          </div>
        )}
      </Card>

      {/* Active Sessions */}
      <Card
        title={t("security.activeSessions")}
        icon="server"
        actions={<Badge tone={sessions.length > 0 ? "green" : "gray"}>{sessions.length} {t("security.activeSessions")}</Badge>}
      >
        <p className="text-xs text-ink-muted mb-3">
          {t("security.sessionsNote")}
        </p>
        {sessions.length === 0 ? (
          <EmptyState icon="server" title={t("security.noSessions")} description={t("security.noSessionsDesc")} />
        ) : (
          <div className="flex flex-col gap-2.5">
            {sessions.map((s) => (
              <div key={s.id} className="flex items-center justify-between gap-3 border border-line rounded-lg px-4 py-3">
                <div className="min-w-0">
                  <div className="text-sm font-medium text-ink truncate">
                    {s.device_info || s.user_agent || t("security.unknownDevice")}
                  </div>
                  <div className="text-xs text-ink-muted truncate">
                    {s.ip_address || t("security.unknownIp")} · {s.created_at ? new Date(s.created_at).toLocaleString() : "—"}
                    {s.is_active ? "" : ` · ${t("security.revoked")}`}
                  </div>
                </div>
                {s.is_active ? (
                  <Button
                    variant="danger"
                    size="sm"
                    icon="power"
                    className="shrink-0"
                    onClick={() => setRevokeTarget(s)}
                  >
                    {t("security.revoke")}
                  </Button>
                ) : (
                  <span className="shrink-0 text-xs text-ink-muted">{t("security.revokedLabel")}</span>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>

      <ConfirmDialog
        open={!!revokeTarget}
        title={t("security.revokeTitle")}
        description={t("security.revokeDesc", {
          info: revokeTarget?.device_info || revokeTarget?.user_agent ? ` (${revokeTarget?.device_info || revokeTarget?.user_agent})` : "",
        })}
        confirmLabel={t("security.revoke")}
        tone="danger"
        onConfirm={() => revokeTarget && handleRevoke(revokeTarget.id)}
        onCancel={() => setRevokeTarget(null)}
      />
    </div>
  );
}
