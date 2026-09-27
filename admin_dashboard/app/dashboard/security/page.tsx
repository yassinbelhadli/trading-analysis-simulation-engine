"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  getMe,
  changePassword,
  twoFactorSetup,
  twoFactorEnable,
  twoFactorDisable,
  listSessions,
  revokeSession,
  clearAuth,
  type MeResponse,
  type SessionItem,
} from "@/lib/auth";
import { ConfirmDialog } from "@ds/components/Modal";
import { Badge, Button, PageHeader } from "@ds/components/ui";

type Status = { ok: boolean; text: string } | null;

function StatusBanner({ status }: { status: Status }) {
  if (!status) return null;
  return (
    <div
      className={`text-sm px-3 py-2 rounded-lg border ${
        status.ok
          ? "text-ok border-ok/40 bg-ok/10"
          : "text-danger border-danger/40 bg-danger/10"
      }`}
    >
      {status.text}
    </div>
  );
}

export default function SecurityPage() {
  const router = useRouter();
  const [me, setMe] = useState<MeResponse | null>(null);
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [status, setStatus] = useState<Status>(null);

  // 2FA state
  const [pw, setPw] = useState("");
  const [secret, setSecret] = useState("");
  const [otpauthUri, setOtpauthUri] = useState("");
  const [enableCode, setEnableCode] = useState("");
  const [disableCode, setDisableCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [revokeTarget, setRevokeTarget] = useState<SessionItem | null>(null);
  const [revokeBusy, setRevokeBusy] = useState(false);
  const [disableConfirm, setDisableConfirm] = useState(false);
  const [disableBusy, setDisableBusy] = useState(false);

  // Change password state
  const [curPw, setCurPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirmPw, setConfirmPw] = useState("");

  const refresh = useCallback(async () => {
    try {
      const [m, s] = await Promise.all([getMe(), listSessions()]);
      setMe(m);
      setSessions(s.sessions);
    } catch (err) {
      setStatus({ ok: false, text: err instanceof Error ? err.message : "Failed to load" });
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const handleSetup = async () => {
    setStatus(null);
    setBusy(true);
    try {
      const res = await twoFactorSetup(pw);
      setSecret(res.secret);
      setOtpauthUri(res.otpauth_uri);
      setPw("");
    } catch (err) {
      setStatus({ ok: false, text: err instanceof Error ? err.message : "Setup failed" });
    } finally {
      setBusy(false);
    }
  };

  const handleEnable = async () => {
    setStatus(null);
    setBusy(true);
    try {
      await twoFactorEnable(enableCode);
      setEnableCode("");
      setSecret("");
      setOtpauthUri("");
      setStatus({ ok: true, text: "Two-factor authentication enabled." });
      refresh();
    } catch (err) {
      setStatus({ ok: false, text: err instanceof Error ? err.message : "Enable failed" });
    } finally {
      setBusy(false);
    }
  };

  const handleDisable = async () => {
    setStatus(null);
    setDisableBusy(true);
    try {
      await twoFactorDisable(disableCode);
      setDisableCode("");
      setDisableConfirm(false);
      setStatus({ ok: true, text: "Two-factor authentication disabled." });
      refresh();
    } catch (err) {
      setStatus({ ok: false, text: err instanceof Error ? err.message : "Disable failed" });
    } finally {
      setDisableBusy(false);
    }
  };

  const handleChangePassword = async () => {
    setStatus(null);
    if (newPw !== confirmPw) {
      setStatus({ ok: false, text: "New passwords do not match." });
      return;
    }
    setBusy(true);
    try {
      await changePassword(curPw, newPw);
      clearAuth();
      router.replace("/login");
    } catch (err) {
      setStatus({ ok: false, text: err instanceof Error ? err.message : "Password change failed" });
    } finally {
      setBusy(false);
    }
  };

  const handleRevoke = async () => {
    if (!revokeTarget) return;
    setRevokeBusy(true);
    setStatus(null);
    try {
      await revokeSession(revokeTarget.id);
      setRevokeTarget(null);
      refresh();
    } catch (err) {
      setStatus({ ok: false, text: err instanceof Error ? err.message : "Revoke failed" });
    } finally {
      setRevokeBusy(false);
    }
  };

  const section =
    "bg-raised border border-line rounded-xl p-6";

  return (
    <div className="max-w-3xl flex flex-col gap-6">
      <PageHeader
        title="Security"
        subtitle="Manage your two-factor authentication, active sessions and password."
      />

      <StatusBanner status={status} />

      {/* Two-Factor Authentication */}
      <div className={section}>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-sm font-semibold text-ink">Two-Factor Authentication</h2>
            <p className="text-xs text-ink-muted mt-1">
              {me?.two_factor_enabled
                ? "Enabled — you are required to enter an authenticator code at login."
                : me?.two_factor_pending
                  ? "Setup started — confirm a code to enable 2FA."
                  : "Disabled — add an extra layer of security to your account."}
            </p>
          </div>
          {me?.two_factor_enabled && (
            <Badge tone="green">Enabled</Badge>
          )}
        </div>

        {!me?.two_factor_enabled && !secret && (
          <div className="flex flex-col gap-3">
            <input
              type="password"
              value={pw}
              onChange={(e) => setPw(e.target.value)}
              placeholder="Current password"
              className="w-full h-9 px-3 rounded-lg bg-input border border-line text-sm text-ink placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500 transition-colors"
            />
            <Button onClick={handleSetup} disabled={busy || !pw} loading={busy} className="w-fit">
              Set Up 2FA
            </Button>
          </div>
        )}

        {secret && (
          <div className="flex flex-col gap-3">
            <div className="rounded-lg border border-line bg-input p-4">
              <p className="text-xs text-ink-muted mb-2">
                Scan this QR code with your authenticator app, or manually enter the key:
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
              <p className="text-center font-mono text-sm mt-3 tracking-widest text-ink">{secret}</p>
            </div>
            <div className="flex flex-col sm:flex-row gap-2">
              <input
                type="text"
                inputMode="numeric"
                value={enableCode}
                onChange={(e) => setEnableCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                placeholder="6-digit code"
                className="flex-1 h-9 px-3 rounded-lg bg-input border border-line text-sm text-ink placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500 transition-colors"
              />
              <Button onClick={handleEnable} disabled={busy || enableCode.length < 6} loading={busy}>
                Confirm & Enable
              </Button>
              <Button variant="ghost" onClick={() => { setSecret(""); setOtpauthUri(""); setEnableCode(""); }}>
                Cancel
              </Button>
            </div>
          </div>
        )}

        {me?.two_factor_enabled && (
          <div className="flex flex-col sm:flex-row gap-2">
            <input
              type="text"
              inputMode="numeric"
              value={disableCode}
              onChange={(e) => setDisableCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
              placeholder="Authenticator code to disable"
              className="flex-1 h-9 px-3 rounded-lg bg-input border border-line text-sm text-ink placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500 transition-colors"
            />
            <Button
              variant="danger"
              onClick={() => setDisableConfirm(true)}
              disabled={busy || disableCode.length < 6}
            >
              Disable 2FA
            </Button>
          </div>
        )}
      </div>

      {/* Active Sessions */}
      <div className={section}>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-sm font-semibold text-ink">Active Sessions</h2>
            <p className="text-xs text-ink-muted mt-1">
              Devices currently signed in to your account.
            </p>
          </div>
          <span className="text-xs text-ink-muted">{sessions.length} session{sessions.length === 1 ? "" : "s"}</span>
        </div>

        <div className="flex flex-col gap-2">
          {sessions.length === 0 && (
            <p className="text-sm text-ink-muted">No active sessions.</p>
          )}
          {sessions.map((s) => (
            <div
              key={s.id}
              className="flex items-center justify-between gap-3 rounded-lg border border-line bg-input px-4 py-3"
            >
              <div className="min-w-0">
                <p className="text-sm font-medium text-ink truncate">
                  {s.device_info || s.user_agent || "Unknown device"}
                </p>
                <p className="text-xs text-ink-muted mt-0.5">
                  {s.ip_address || "Unknown IP"} · {s.created_at ? new Date(s.created_at).toLocaleString() : "—"}
                  {s.is_active ? "" : " · revoked"}
                </p>
              </div>
              {s.is_active ? (
                <Button size="sm" variant="ghost" onClick={() => setRevokeTarget(s)} className="shrink-0">
                  Revoke
                </Button>
              ) : (
                <span className="shrink-0 text-xs text-ink-muted">Revoked</span>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Change Password */}
      <div className={section}>
        <h2 className="text-sm font-semibold text-ink mb-4">Change Password</h2>
        <div className="flex flex-col gap-3">
          <input
            type="password"
            value={curPw}
            onChange={(e) => setCurPw(e.target.value)}
            placeholder="Current password"
            className="w-full h-9 px-3 rounded-lg bg-input border border-line text-sm text-ink placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500 transition-colors"
          />
          <input
            type="password"
            value={newPw}
            onChange={(e) => setNewPw(e.target.value)}
            placeholder="New password (min 8 characters)"
            className="w-full h-9 px-3 rounded-lg bg-input border border-line text-sm text-ink placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500 transition-colors"
          />
          <input
            type="password"
            value={confirmPw}
            onChange={(e) => setConfirmPw(e.target.value)}
            placeholder="Confirm new password"
            className="w-full h-9 px-3 rounded-lg bg-input border border-line text-sm text-ink placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500 transition-colors"
          />
          <Button
            onClick={handleChangePassword}
            disabled={busy || !curPw || newPw.length < 8 || newPw !== confirmPw}
            loading={busy}
            className="w-fit"
          >
            Update Password
          </Button>
          <p className="text-xs text-ink-muted">
            You will be signed out of all sessions after changing your password.
          </p>
        </div>
      </div>

      <ConfirmDialog
        open={!!revokeTarget}
        title="Revoke session"
        description={`Sign out "${revokeTarget?.device_info || revokeTarget?.user_agent || "this device"}"? The session will be revoked immediately.`}
        confirmLabel="Revoke"
        tone="danger"
        loading={revokeBusy}
        onConfirm={handleRevoke}
        onCancel={() => setRevokeTarget(null)}
      />

      <ConfirmDialog
        open={disableConfirm}
        title="Disable 2FA"
        description="This removes the extra authentication layer from your account. Confirm the authenticator code to continue."
        confirmLabel="Disable 2FA"
        tone="danger"
        loading={disableBusy}
        onConfirm={handleDisable}
        onCancel={() => setDisableConfirm(false)}
      />
    </div>
  );
}
