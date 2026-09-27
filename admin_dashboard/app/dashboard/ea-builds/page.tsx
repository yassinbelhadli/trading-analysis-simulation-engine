"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import PermissionGuard from "@/components/auth/permission_guard";
import { ConfirmDialog, Modal } from "@ds/components/Modal";
import {
  createEABuild,
  deleteEABuild,
  listEABuilds,
  setLatestEABuild,
  updateEABuild,
  uploadEABuildFile,
  approveEABuild,
  rejectEABuild,
  type EABuildAdminItem,
} from "@/lib/api";
import { PageHeader, Card, Button, Badge, EmptyState, Skeleton, Table, Td } from "@ds/components/ui";
import { Icon } from "@ds/components/Icon";

type Notice = { ok: boolean; text: string } | null;

const inputCls =
  "w-full h-9 px-3 rounded-lg bg-input border border-line text-sm text-ink focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500 transition-colors";
const areaCls =
  "w-full px-3 py-2 rounded-lg bg-input border border-line text-sm text-ink focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500 transition-colors min-h-[80px]";

export default function EABuildsPage() {
  const [items, setItems] = useState<EABuildAdminItem[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState<Notice>(null);

  // create / edit form
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<EABuildAdminItem | null>(null);
  const [form, setForm] = useState({ version: "", release_notes: "", changelog: "" });
  const [formBusy, setFormBusy] = useState(false);

  // upload
  const [uploadingId, setUploadingId] = useState<string | null>(null);
  const [uploadName, setUploadName] = useState<string | null>(null);
  const fileRefs = useRef<Record<string, HTMLInputElement | null>>({});

  // delete confirm
  const [confirmDelete, setConfirmDelete] = useState<EABuildAdminItem | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await listEABuilds();
      setItems(r.items);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load downloads");
    } finally {
      setLoaded(true);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const openCreate = () => {
    setEditing(null);
    setForm({ version: "", release_notes: "", changelog: "" });
    setShowForm(true);
  };

  const openEdit = (b: EABuildAdminItem) => {
    setEditing(b);
    setForm({ version: b.version, release_notes: b.release_notes || "", changelog: b.changelog || "" });
    setShowForm(true);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setNotice(null);
    setFormBusy(true);
    try {
      if (editing) {
        const res = await updateEABuild(editing.id, {
          release_notes: form.release_notes,
          changelog: form.changelog,
        });
        setNotice({ ok: true, text: res.message });
      } else {
        const version = form.version.trim().replace(/^v/, "");
        const res = await createEABuild({
          version,
          release_notes: form.release_notes,
          changelog: form.changelog,
        });
        setNotice({ ok: true, text: res.message });
      }
      setShowForm(false);
      load();
    } catch (err) {
      setNotice({ ok: false, text: err instanceof Error ? err.message : "Save failed" });
    } finally {
      setFormBusy(false);
    }
  };

  const handleUpload = async (b: EABuildAdminItem, file: File | undefined) => {
    setNotice(null);
    if (!file) return;
    const name = file.name.toLowerCase();
    const allowedExts = [".ex4", ".ex5", ".exe", ".msi", ".zip", ".pdf", ".dmg", ".apk", ".ipa"];
    const hasValidExt = allowedExts.some((ext) => name.endsWith(ext));
    if (!hasValidExt) {
      setNotice({ ok: false, text: "File type not allowed. Accepted: .ex4 .ex5 .exe .msi .zip .pdf .dmg .apk .ipa" });
      return;
    }
    const MIN_SIZE = 1 * 1024 * 1024;
    const MAX_SIZE = 1.5 * 1024 * 1024 * 1024;
    if (file.size < MIN_SIZE) {
      setNotice({ ok: false, text: "File is too small. Minimum size is 1 MB." });
      return;
    }
    if (file.size > MAX_SIZE) {
      setNotice({ ok: false, text: "File exceeds the 1.5 GB upload limit." });
      return;
    }
    setUploadingId(b.id);
    setUploadName(file.name);
    try {
      const res = await uploadEABuildFile(b.id, file);
      setNotice({ ok: true, text: `${res.message} (${res.windows_file}, ${res.size_bytes} bytes)` });
      load();
    } catch (err) {
      setNotice({ ok: false, text: err instanceof Error ? err.message : "Upload failed" });
    } finally {
      setUploadingId(null);
      setUploadName(null);
      if (fileRefs.current[b.id]) fileRefs.current[b.id]!.value = "";
    }
  };

  const handleSetLatest = async (b: EABuildAdminItem) => {
    setNotice(null);
    try {
      const res = await setLatestEABuild(b.id);
      setNotice({ ok: true, text: res.message });
      load();
    } catch (err) {
      setNotice({ ok: false, text: err instanceof Error ? err.message : "Failed to mark latest" });
    }
  };

  const handleDelete = async () => {
    if (!confirmDelete) return;
    setDeleteBusy(true);
    setNotice(null);
    try {
      const res = await deleteEABuild(confirmDelete.id);
      setNotice({ ok: true, text: `${res.message}${res.file_removed ? " (artifact removed)" : ""}` });
      setConfirmDelete(null);
      load();
    } catch (err) {
      setNotice({ ok: false, text: err instanceof Error ? err.message : "Delete failed" });
    } finally {
      setDeleteBusy(false);
    }
  };

  const handleApprove = async (b: EABuildAdminItem) => {
    setNotice(null);
    try {
      const res = await approveEABuild(b.id);
      setNotice({ ok: true, text: res.message });
      load();
    } catch (err) {
      setNotice({ ok: false, text: err instanceof Error ? err.message : "Approve failed" });
    }
  };

  const handleReject = async (b: EABuildAdminItem) => {
    setNotice(null);
    const reason = window.prompt("Rejection reason (optional):") || "";
    try {
      const res = await rejectEABuild(b.id, reason);
      setNotice({ ok: true, text: res.message });
      load();
    } catch (err) {
      setNotice({ ok: false, text: err instanceof Error ? err.message : "Reject failed" });
    }
  };

  if (!loaded) {
    return (
      <PermissionGuard permission="ea.read">
        <div className="flex flex-col gap-5">
          <div className="h-8 w-56 rounded bg-hover animate-pulse" />
          <Skeleton className="h-48 w-full" />
        </div>
      </PermissionGuard>
    );
  }

  return (
    <PermissionGuard permission="ea.read">
      <div className="flex flex-col gap-5">
        <PageHeader
          title="Downloads"
          subtitle="Manage files for licensed clients. Upload EA builds or other downloadable resources."
          actions={
            <PermissionGuard permission="ea.publish" fallback={null}>
              <Button icon="plus" onClick={openCreate}>New Release</Button>
            </PermissionGuard>
          }
        />

        {notice && (
          <div
            className={`flex items-center gap-2 text-sm px-3 py-2 rounded-lg border ${
              notice.ok ? "text-ok border-ok/30 bg-ok/10" : "text-danger border-danger/30 bg-danger/10"
            }`}
          >
            <Icon name={notice.ok ? "check-circle" : "alert-triangle"} className="h-4 w-4 shrink-0" />
            {notice.text}
          </div>
        )}

        {error && !items.length && (
          <EmptyState icon="alert-triangle" title="Could not load builds" description={error} />
        )}

        {items.length === 0 && !error && (
          <EmptyState
            icon="wrench"
            variant="gap"
            title="No releases yet"
            description="Create the first release, then upload a file. Clients only see releases that have been approved."
            action={<PermissionGuard permission="ea.publish" fallback={null}><Button icon="plus" onClick={openCreate}>Create Release</Button></PermissionGuard>}
          />
        )}

        {items.length > 0 && (
          <Card title={`Releases (${items.length})`} icon="layers">
            <Table
              columns={["Version", "Status", "Approval", "File", "Released", "Actions"]}
            >
              {items.map((b) => (
                <tr key={b.id} className="border-b border-line last:border-0">
                  <Td mono>v{b.version}</Td>
                  <Td>
                    <Badge tone={b.is_latest ? "green" : "gray"}>{b.is_latest ? "Latest" : "Previous"}</Badge>
                  </Td>
                  <Td>
                    {b.approved ? (
                      <Badge tone="green">Approved</Badge>
                    ) : b.rejection_reason ? (
                      <span title={b.rejection_reason || ""}>
                        <Badge tone="red">Rejected</Badge>
                      </span>
                    ) : (
                      <Badge tone="amber">Pending Review</Badge>
                    )}
                  </Td>
                  <Td>
                    {b.windows_available ? (
                      <span className="inline-flex items-center gap-1.5 text-sm text-ink">
                        <Icon name="check-circle" className="h-4 w-4 text-ok" /> Uploaded
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1.5 text-sm text-ink-muted">
                        <Icon name="clock" className="h-4 w-4" /> No file yet
                      </span>
                    )}
                  </Td>
                  <Td className="text-sm text-ink-muted">
                    {b.released_at ? new Date(b.released_at).toLocaleDateString() : "—"}
                  </Td>
                  <Td>
                    <PermissionGuard permission="ea.publish" fallback={null}>
                      <div className="flex flex-wrap items-center gap-1.5">
                        <label className="cursor-pointer">
                          <input
                            ref={(el) => { fileRefs.current[b.id] = el; }}
                            type="file"
                            accept=".ex4,.ex5,.exe,.msi,.zip,.pdf,.dmg,.apk,.ipa"
                            className="hidden"
                            disabled={uploadingId === b.id}
                            onChange={(e) => handleUpload(b, e.target.files?.[0])}
                          />
                          <span className="inline-flex items-center gap-1.5 rounded-lg border border-line px-2.5 py-1.5 text-xs font-medium text-ink hover:bg-hover">
                            <Icon name="upload" className="h-3.5 w-3.5" />
                            {uploadingId === b.id ? "Uploading…" : b.windows_available ? "Replace file" : "Upload file"}
                          </span>
                        </label>
                        {!b.approved && (
                          <Button variant="ghost" size="sm" onClick={() => handleApprove(b)}>Approve</Button>
                        )}
                        {b.approved && (
                          <Button variant="ghost" size="sm" onClick={() => handleReject(b)}>Reject</Button>
                        )}
                        {!b.is_latest && (
                          <Button variant="ghost" size="sm" onClick={() => handleSetLatest(b)}>Set latest</Button>
                        )}
                        <Button variant="ghost" size="sm" icon="edit" onClick={() => openEdit(b)}>Edit</Button>
                        <Button variant="danger" size="sm" icon="trash" onClick={() => setConfirmDelete(b)}>Delete</Button>
                      </div>
                    </PermissionGuard>
                  </Td>
                </tr>
              ))}
            </Table>
            <div className="mt-3 text-xs text-ink-muted">
              {uploadName ? `Last upload: ${uploadName}` : "Files require approval before clients can see them."}
            </div>
          </Card>
        )}

        <Modal
          open={showForm}
          onClose={() => setShowForm(false)}
          title={editing ? `Edit release v${editing.version}` : "New release"}
          subtitle={editing ? "Release notes and changelog only — version is immutable." : "Create the release first, then upload the compiled artifact."}
          footer={
            <>
              <Button variant="ghost" onClick={() => setShowForm(false)} disabled={formBusy}>Cancel</Button>
              <Button onClick={handleSave} loading={formBusy} disabled={!form.version.trim() && !editing}>
                {editing ? "Save changes" : "Create release"}
              </Button>
            </>
          }
        >
          <form onSubmit={handleSave} className="flex flex-col gap-3">
            {!editing && (
              <div>
                <label className="text-xs font-medium text-ink-soft mb-1.5 block">Version *</label>
                <input
                  value={form.version}
                  onChange={(e) => setForm({ ...form, version: e.target.value })}
                  placeholder="e.g. 1.3.0"
                  className={inputCls}
                  disabled={formBusy}
                />
                <p className="text-xs text-ink-muted mt-1">Dotted numeric version (e.g. 1.3.0). Must not already exist.</p>
              </div>
            )}
            <div>
              <label className="text-xs font-medium text-ink-soft mb-1.5 block">Release notes</label>
              <textarea
                value={form.release_notes}
                onChange={(e) => setForm({ ...form, release_notes: e.target.value })}
                className={areaCls}
                disabled={formBusy}
              />
            </div>
            <div>
              <label className="text-xs font-medium text-ink-soft mb-1.5 block">Changelog</label>
              <textarea
                value={form.changelog}
                onChange={(e) => setForm({ ...form, changelog: e.target.value })}
                className={areaCls}
                disabled={formBusy}
              />
            </div>
          </form>
        </Modal>

        <ConfirmDialog
          open={confirmDelete !== null}
          title={`Delete release v${confirmDelete?.version ?? ""}?`}
          description="This removes the release and its published artifact. Clients will no longer be able to download this version."
          confirmLabel="Delete release"
          tone="danger"
          loading={deleteBusy}
          onConfirm={handleDelete}
          onCancel={() => setConfirmDelete(null)}
        />
      </div>
    </PermissionGuard>
  );
}
