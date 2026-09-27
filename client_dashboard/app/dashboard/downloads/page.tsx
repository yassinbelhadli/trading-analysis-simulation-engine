"use client";

import { useEffect, useState } from "react";
import { getEABuilds, checkEAUpdates, downloadEABuild, type EABuildInfo } from "@/lib/api";
import { PageHeader, Card, Button, Badge, EmptyState, TextField } from "@ds/components/ui";
import { Icon } from "@ds/components/Icon";
import { parseApiError } from "@/lib/errors";
import { useLocale } from "@/components/LocaleContext";

export default function DownloadsPage() {
  const { t } = useLocale();
  const [latest, setLatest] = useState<EABuildInfo | null>(null);
  const [changelog, setChangelog] = useState<EABuildInfo[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState<{ ok: boolean; text: string } | null>(null);
  const [currentVersion, setCurrentVersion] = useState("");
  const [updateCheck, setUpdateCheck] = useState<{ available: boolean; latest: string | null } | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getEABuilds()
      .then((r) => { setLatest(r.latest); setChangelog(r.changelog); })
      .catch((e) => setError(parseApiError(e)));
  }, []);

  const handleDownload = async (buildId: string) => {
    setNotice(null);
    setBusy(true);
    try {
      const res = await downloadEABuild(buildId);
      if (!res.ok) {
        const body = await res.text().catch(() => "");
        throw new Error(body || `HTTP ${res.status}`);
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = res.headers.get("content-disposition")?.match(/filename="?([^"]+)"?/)?.[1] || "ICT_Funded_EA.zip";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      setNotice({ ok: true, text: t("downloads.downloadStarted") });
    } catch (err) {
      setNotice({ ok: false, text: err instanceof Error ? err.message : t("downloads.downloadFailed") });
    } finally {
      setBusy(false);
    }
  };

  const handleCheckUpdates = async () => {
    setNotice(null);
    if (!currentVersion.trim()) {
      setNotice({ ok: false, text: t("downloads.enterVersion") });
      return;
    }
    setBusy(true);
    try {
      const res = await checkEAUpdates(currentVersion.trim());
      setUpdateCheck({ available: res.update_available, latest: res.latest_version });
      setNotice({
        ok: res.update_available,
        text: res.update_available
          ? t("downloads.updateAvailable", { v: res.latest_version || "unknown" })
          : t("downloads.upToDate", { v: res.latest_version || "unknown" }),
      });
    } catch (err) {
      setNotice({ ok: false, text: err instanceof Error ? err.message : t("downloads.checkFailed") });
    } finally {
      setBusy(false);
    }
  };

  if (error) return <EmptyState icon="alert-triangle" title={t("downloads.loadError")} description={error} />;

  return (
    <div className="max-w-3xl flex flex-col gap-5">
      <PageHeader title={t("downloads.title")} subtitle={t("downloads.subtitle")} />

      {notice && (
        <div
          className={`flex items-center gap-2 text-sm px-3 py-2 rounded-lg border ${
            notice.ok
              ? "text-ok border-ok/30 bg-ok/10"
              : "text-danger border-danger/30 bg-danger/10"
          }`}
        >
          <Icon name={notice.ok ? "check-circle" : "alert-triangle"} className="h-4 w-4 shrink-0" />
          {notice.text}
        </div>
      )}

      {latest && (
        <Card>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="text-xs font-medium uppercase tracking-wide text-ink-muted">{t("downloads.latestVersion")}</div>
              <div className="font-mono text-3xl font-bold text-brand-400 mt-1">v{latest.version}</div>
              {latest.released_at && (
                <div className="text-xs text-ink-muted mt-1">
                  {t("downloads.released")} {new Date(latest.released_at).toLocaleDateString()}
                </div>
              )}
            </div>
            <div className="flex flex-col gap-2 items-end">
              <Button
                icon="download"
                onClick={() => handleDownload(latest.id)}
                disabled={busy || !latest.windows_available}
                loading={busy}
              >
                {latest.windows_available ? t("downloads.downloadWindows") : t("downloads.buildPending")}
              </Button>
              <span className="inline-flex items-center gap-1 text-xs text-ink-muted">
                <Icon name="clock" className="h-3.5 w-3.5" />
                {t("downloads.macosSoon")}
              </span>
            </div>
          </div>
          {latest.release_notes && (
            <div className="mt-4 pt-4 border-t border-line">
              <div className="text-xs font-semibold uppercase tracking-wide text-ink-muted mb-2">{t("downloads.releaseNotes")}</div>
              <p className="text-sm text-ink-soft whitespace-pre-line">{latest.release_notes}</p>
            </div>
          )}
        </Card>
      )}

      <Card title={t("downloads.checkUpdates")} icon="refresh">
        <div className="flex flex-wrap items-end gap-2">
          <div className="flex-1 min-w-[220px]">
            <TextField
              label={t("downloads.yourVersion")}
              value={currentVersion}
              onChange={(e) => setCurrentVersion(e.target.value)}
              placeholder="e.g. 1.1.0"
              icon="tag"
            />
          </div>
          <Button variant="secondary" icon="refresh" onClick={handleCheckUpdates} disabled={busy} loading={busy}>
            {t("downloads.checkUpdates")}
          </Button>
        </div>
        {updateCheck && (
          <div
            className={`mt-3 flex items-center gap-2 text-sm px-3 py-2 rounded-lg border ${
              updateCheck.available
                ? "text-warn border-warn/30 bg-warn/10"
                : "text-ok border-ok/30 bg-ok/10"
            }`}
          >
            <Icon name={updateCheck.available ? "alert-triangle" : "check-circle"} className="h-4 w-4 shrink-0" />
            {updateCheck.available
              ? t("downloads.newerAvailable", { v: updateCheck.latest || "unknown" })
              : t("downloads.runningLatest", { v: updateCheck.latest || "unknown" })}
          </div>
        )}
      </Card>

      {changelog.length > 0 && (
        <Card title={t("downloads.changelog")} icon="scroll">
          <div className="flex flex-col gap-3">
            {changelog.map((b) => (
              <div key={b.id} className="border border-line rounded-lg p-4">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-sm text-brand-400">v{b.version}</span>
                    <Badge tone={b.version === latest?.version ? "green" : "gray"}>
                      {b.version === latest?.version ? t("downloads.latest") : t("downloads.previous")}
                    </Badge>
                  </div>
                  <Button
                    variant="secondary"
                    size="sm"
                    icon="download"
                    onClick={() => handleDownload(b.id)}
                    disabled={busy || !b.windows_available}
                  >
                    {t("downloads.download")}
                  </Button>
                </div>
                {b.changelog && (
                  <div className="text-sm text-ink-soft mt-2 whitespace-pre-line">{b.changelog}</div>
                )}
                {b.released_at && (
                  <div className="text-xs text-ink-muted mt-2">
                    {new Date(b.released_at).toLocaleDateString()}
                  </div>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
