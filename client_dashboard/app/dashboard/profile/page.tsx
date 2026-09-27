"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getClientProfile, updateClientProfile, type ClientProfile } from "@/lib/api";
import { changePassword, clearAuth } from "@/lib/auth";
import { Notice, type NoticeState } from "@/components/Notice";
import { PageHeader, Card, Button, TextField, SelectField, Badge, EmptyState, Skeleton } from "@ds/components/ui";
import { parseApiError } from "@/lib/errors";
import { useLocale } from "@/components/LocaleContext";

const LANGUAGES = ["EN", "AR", "FR", "ES"];

export default function ProfilePage() {
  const router = useRouter();
  const { t } = useLocale();
  const [profile, setProfile] = useState<ClientProfile | null>(null);
  const [error, setError] = useState("");
  const [status, setStatus] = useState<NoticeState>(null);
  const [saving, setSaving] = useState(false);

  const [first_name, setFirstName] = useState("");
  const [last_name, setLastName] = useState("");
  const [avatar, setAvatar] = useState("");
  const [country, setCountry] = useState("");
  const [timezone, setTimezone] = useState("");
  const [language, setLanguage] = useState("EN");

  const [curPw, setCurPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirmPw, setConfirmPw] = useState("");

  useEffect(() => {
    getClientProfile()
      .then((p) => {
        setProfile(p);
        setFirstName(p.first_name || "");
        setLastName(p.last_name || "");
        setAvatar(p.avatar || "");
        setCountry(p.country || "");
        setTimezone(p.timezone || "");
        setLanguage(p.language || "EN");
      })
      .catch((e) => setError(parseApiError(e)));
  }, []);

  const handleSave = async () => {
    setStatus(null);
    setSaving(true);
    try {
      const res = await updateClientProfile({ first_name, last_name, avatar, country, timezone, language });
      setProfile(res.profile);
      setStatus({ ok: true, text: t("profile.saved") });
    } catch (err) {
      setStatus({ ok: false, text: err instanceof Error ? err.message : t("profile.saveFailed") });
    } finally {
      setSaving(false);
    }
  };

  const handleChangePassword = async () => {
    setStatus(null);
    if (newPw !== confirmPw) {
      setStatus({ ok: false, text: t("profile.pwMismatch") });
      return;
    }
    try {
      await changePassword(curPw, newPw);
      clearAuth();
      router.replace("/login");
    } catch (err) {
      setStatus({ ok: false, text: err instanceof Error ? err.message : t("profile.pwFailed") });
    }
  };

  if (error && !profile) {
    return <EmptyState icon="alert-triangle" title={t("profile.loadError")} description={error} />;
  }
  if (!profile) {
    return (
      <div className="max-w-2xl flex flex-col gap-5">
        <div className="h-8 w-44 rounded bg-hover animate-pulse" />
        <Skeleton className="h-80 w-full" />
        <Skeleton className="h-56 w-full" />
      </div>
    );
  }

  return (
    <div className="max-w-2xl flex flex-col gap-5">
      <PageHeader title={t("profile.title")} subtitle={t("profile.subtitle")} />

      <Notice state={status} />

      <Card title={t("profile.personalInfo")} icon="user">
        <div className="flex items-center gap-4 mb-5">
          <div className="h-16 w-16 rounded-full overflow-hidden border border-line bg-input flex items-center justify-center text-xl font-semibold text-ink-soft shrink-0">
            {avatar ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={avatar} alt="avatar" className="w-full h-full object-cover" />
            ) : (
              <span>{`${(first_name || "T")[0]}${(last_name || "")[0] || ""}`.toUpperCase()}</span>
            )}
          </div>
          <div className="min-w-0">
            <div className="text-sm font-medium text-ink truncate">
              {profile?.first_name || profile?.email || ""}
            </div>
            <div className="mt-1 flex items-center gap-2">
              <Badge tone={profile.email_verified ? "green" : "amber"}>
                {profile.email_verified ? t("profile.emailVerified") : t("profile.emailNotVerified")}
              </Badge>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <TextField
            label={t("profile.firstName")}
            value={first_name}
            onChange={(e) => setFirstName(e.target.value)}
            icon="user"
          />
          <TextField
            label={t("profile.lastName")}
            value={last_name}
            onChange={(e) => setLastName(e.target.value)}
            icon="user"
          />
          <div className="sm:col-span-2">
            <TextField
              label={t("profile.avatarUrl")}
              value={avatar}
              onChange={(e) => setAvatar(e.target.value)}
              placeholder="https://..."
              icon="link"
            />
          </div>
          <TextField
            label={t("profile.country")}
            value={country}
            onChange={(e) => setCountry(e.target.value)}
            placeholder={t("profile.countryPh")}
            maxLength={100}
            icon="globe"
          />
          <TextField
            label={t("profile.timezone")}
            value={timezone}
            onChange={(e) => setTimezone(e.target.value)}
            placeholder={t("profile.timezonePh")}
            icon="clock"
          />
          <SelectField
            label={t("profile.language")}
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
          >
            {LANGUAGES.map((l) => <option key={l} value={l}>{l}</option>)}
          </SelectField>
          <TextField
            label={t("profile.emailReadonly")}
            value={profile?.email || ""}
            readOnly
            disabled
            hint={t("profile.emailHint")}
            icon="mail"
          />
        </div>

        <div className="mt-5 flex justify-end">
          <Button icon="check" onClick={handleSave} disabled={saving} loading={saving}>
            {saving ? t("profile.saving") : t("profile.save")}
          </Button>
        </div>
      </Card>

      <Card title={t("profile.changePassword")} icon="lock">
        <div className="flex flex-col gap-3">
          <TextField
            type="password"
            label={t("profile.currentPassword")}
            value={curPw}
            onChange={(e) => setCurPw(e.target.value)}
            placeholder={t("profile.currentPasswordPh")}
            icon="lock"
          />
          <TextField
            type="password"
            label={t("profile.newPassword")}
            value={newPw}
            onChange={(e) => setNewPw(e.target.value)}
            placeholder={t("profile.newPasswordPh")}
            icon="lock"
          />
          <TextField
            type="password"
            label={t("profile.confirmPassword")}
            value={confirmPw}
            onChange={(e) => setConfirmPw(e.target.value)}
            placeholder={t("profile.confirmPasswordPh")}
            icon="lock"
          />
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs text-ink-muted">{t("profile.signOutNote")}</p>
            <Button
              variant="secondary"
              size="sm"
              icon="refresh"
              onClick={handleChangePassword}
              disabled={!curPw || newPw.length < 8 || newPw !== confirmPw}
            >
              {t("profile.updatePassword")}
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
