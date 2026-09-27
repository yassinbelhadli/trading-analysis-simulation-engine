"use client";

import { useEffect, useState, useCallback } from "react";
import StatusBadge from "@/components/StatusBadge";
import Modal from "@/components/Modal";
import PermissionGuard from "@/components/auth/permission_guard";
import {
  listTickets,
  getTicket,
  replyTicket,
  updateTicket,
  assignTicket,
  escalateTicket,
  banTicketUser,
  listUsers,
  type AdminTicket,
  type UserItem,
} from "@/lib/api";
import { getStoredUser } from "@/lib/auth";
import { Badge, Button, PageHeader, Table, Td, TextField, SelectField, Skeleton } from "@ds/components/ui";
import { ConfirmDialog } from "@ds/components/Modal";

const STATUS_LABELS: Record<string, string> = {
  open: "Open",
  in_progress: "In Progress",
  resolved: "Resolved",
  closed: "Closed",
};

const PRIORITY_LABELS: Record<string, string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
  urgent: "Urgent",
};

const CATEGORY_LABELS: Record<string, string> = {
  connection: "Connection",
  license: "License",
  performance: "Performance",
  billing: "Billing",
  account: "Account",
  bug: "Bug",
  other: "Other",
};

const ESCALATION_TARGETS = ["admin", "owner"];

function priorityTone(p: string): "red" | "amber" | "blue" | "gray" {
  if (p === "urgent") return "red";
  if (p === "high") return "amber";
  if (p === "medium") return "blue";
  return "gray";
}

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString();
}

export default function TicketsPage() {
  const [tickets, setTickets] = useState<AdminTicket[]>([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [escalatedOnly, setEscalatedOnly] = useState(false);
  const [assigneeFilter, setAssigneeFilter] = useState("");
  const [search, setSearch] = useState("");

  const [selected, setSelected] = useState<AdminTicket | null>(null);
  const [reply, setReply] = useState("");
  const [replyInternal, setReplyInternal] = useState(false);
  const [newStatus, setNewStatus] = useState("");
  const [newPriority, setNewPriority] = useState("");
  const [newCategory, setNewCategory] = useState("");
  const [assigneeId, setAssigneeId] = useState("");
  const [escalateTarget, setEscalateTarget] = useState("admin");
  const [escalateReason, setEscalateReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [banTarget, setBanTarget] = useState<AdminTicket | null>(null);
  const [confirmBusy, setConfirmBusy] = useState(false);
  const [staffUsers, setStaffUsers] = useState<UserItem[]>([]);
  const [toast, setToast] = useState("");
  const [loading, setLoading] = useState(true);

  const currentUser = getStoredUser();
  const isAdmin = currentUser?.role === "admin" || currentUser?.role === "owner";
  const isOwner = currentUser?.role === "owner";

  const flash = (m: string) => {
    setToast(m);
    window.setTimeout(() => setToast(""), 4000);
  };

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (statusFilter) params.set("status", statusFilter);
      if (priorityFilter) params.set("priority", priorityFilter);
      if (categoryFilter) params.set("category", categoryFilter);
      if (escalatedOnly) params.set("escalated", "true");
      if (assigneeFilter) params.set("assignee_id", assigneeFilter);
      if (search.trim()) params.set("search", search.trim());
      const data = await listTickets(params.toString());
      setTickets(data.tickets);
      setTotal(data.total);
      setError("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [statusFilter, priorityFilter, categoryFilter, escalatedOnly, assigneeFilter, search]);

  useEffect(() => { load(); }, [load]);

  // Debounced search so every keystroke does not hit the API
  useEffect(() => {
    const t = window.setTimeout(() => load(), 350);
    return () => window.clearTimeout(t);
  }, [search]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [admins, supports] = await Promise.all([
          listUsers("?role=admin&limit=200"),
          listUsers("?role=support&limit=200"),
        ]);
        const merged = new Map<string, UserItem>();
        for (const u of [...admins.items, ...supports.items]) merged.set(u.id, u);
        if (!cancelled) setStaffUsers([...merged.values()]);
      } catch {
        // assignee dropdown degrades to empty on failure
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const openTicket = async (t: AdminTicket) => {
    setSelected(t);
    setReply("");
    setReplyInternal(false);
    setNewStatus(t.status);
    setNewPriority(t.priority);
    setNewCategory(t.category);
    setAssigneeId(t.assignee_id || "");
    setEscalateTarget("admin");
    setEscalateReason("");
    try {
      const fresh = await getTicket(t.id);
      if (fresh.success && fresh.ticket) setSelected(fresh.ticket);
    } catch {
      // list payload already contains the full conversation; keep it
    }
  };

  const sendReply = async () => {
    if (!selected) return;
    if (!reply.trim()) return;
    setSaving(true);
    try {
      const res = await replyTicket(selected.id, reply.trim(), replyInternal);
      flash(res.message || "Reply sent");
      setReply("");
      setReplyInternal(false);
      await openTicket(selected);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const saveChanges = async () => {
    if (!selected) return;
    setSaving(true);
    try {
      const body: { status?: string; priority?: string; category?: string } = {};
      if (newStatus && newStatus !== selected.status) body.status = newStatus;
      if (newPriority && newPriority !== selected.priority) body.priority = newPriority;
      if (newCategory && newCategory !== selected.category) body.category = newCategory;
      if (Object.keys(body).length > 0) {
        const res = await updateTicket(selected.id, body);
        flash(res.message || "Ticket updated");
      }
      if (assigneeId !== (selected.assignee_id || "")) {
        const res = await assignTicket(selected.id, assigneeId || "none");
        flash(res.message || "Ticket assigned");
      }
      await openTicket(selected);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const escalateAction = async () => {
    if (!selected) return;
    setSaving(true);
    try {
      const res = await escalateTicket(selected.id, escalateTarget, escalateReason.trim());
      flash(res.message || "Ticket escalated");
      await openTicket(selected);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const banUser = async () => {
    if (!banTarget) return;
    setConfirmBusy(true);
    try {
      const res = await banTicketUser(banTarget.id);
      flash(res.message || "User banned");
      setBanTarget(null);
      load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setConfirmBusy(false);
    }
  };

  const staffName = (u: UserItem | null | undefined): string => {
    if (!u) return "";
    return [u.first_name, u.last_name].filter(Boolean).join(" ") || u.email || u.id.slice(0, 8);
  };

  const selectedAssigneeName = selected?.assignee
    ? [selected.assignee.first_name, selected.assignee.last_name].filter(Boolean).join(" ") ||
      selected.assignee.email ||
      selected.assignee.id.slice(0, 8)
    : "";

  return (
    <PermissionGuard roles={["owner", "admin", "support"]}>
      <div>
        <PageHeader
          title="Support Tickets"
          subtitle={`${total} ticket${total !== 1 ? "s" : ""}`}
        />

        <div className="flex gap-2 mb-4 flex-wrap">
          {["", "open", "in_progress", "resolved", "closed"].map((s) => (
            <Button
              key={s}
              size="sm"
              variant={statusFilter === s ? "primary" : "ghost"}
              onClick={() => setStatusFilter(s)}
            >
              {s ? STATUS_LABELS[s] || s : "All"}
            </Button>
          ))}
        </div>

        <div className="flex gap-3 mb-4 flex-wrap items-end">
          <div className="w-48">
            <TextField label="Search" placeholder="Subject / number / body" value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
          <div className="w-40">
            <SelectField label="Priority" value={priorityFilter} onChange={(e) => setPriorityFilter(e.target.value)}>
              <option value="">All priorities</option>
              {Object.entries(PRIORITY_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </SelectField>
          </div>
          <div className="w-44">
            <SelectField label="Category" value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)}>
              <option value="">All categories</option>
              {Object.entries(CATEGORY_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </SelectField>
          </div>
          <div className="w-52">
            <SelectField label="Assignee" value={assigneeFilter} onChange={(e) => setAssigneeFilter(e.target.value)}>
              <option value="">Anyone</option>
              <option value="none">Unassigned</option>
              {staffUsers.map((u) => <option key={u.id} value={u.id}>{staffName(u)}</option>)}
            </SelectField>
          </div>
          <Button
            size="sm"
            variant={escalatedOnly ? "primary" : "ghost"}
            onClick={() => setEscalatedOnly((v) => !v)}
          >
            Escalated only
          </Button>
        </div>

        {error && <div className="text-danger text-sm mb-4">{error}</div>}
        {toast && <div className="text-success text-sm mb-4">{toast}</div>}

        <Table columns={["Ticket", "User", "Category", "Status", "Priority", "Assignee", "Date", "Actions"]}>
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
          ) : tickets.length === 0 ? (
            <tr>
              <td colSpan={8} className="text-center py-8 text-ink-muted px-4">No tickets found</td>
            </tr>
          ) : (
          tickets.map((t) => (
            <tr key={t.id}>
              <Td mono>{t.ticket_number}</Td>
              <Td>
                <div className="text-xs text-ink">
                  {t.user?.first_name || t.user?.telegram_username || t.user_id?.slice(0, 8) || "—"}
                </div>
                {t.user?.email && <div className="text-[10px] text-ink-muted">{t.user.email}</div>}
              </Td>
              <Td>
                <div className="text-xs">{CATEGORY_LABELS[t.category] || t.category}</div>
                {t.source === "telegram" && <div className="text-[10px] text-ink-muted">Telegram</div>}
              </Td>
              <Td><StatusBadge status={t.status} /></Td>
              <Td>
                <div className="flex items-center gap-1.5">
                  <Badge tone={priorityTone(t.priority)}>{PRIORITY_LABELS[t.priority] || t.priority}</Badge>
                  {t.escalated && <Badge tone="red">Escalated</Badge>}
                </div>
              </Td>
              <Td className="text-xs text-ink-muted">
                {t.assignee
                  ? [t.assignee.first_name, t.assignee.last_name].filter(Boolean).join(" ") || t.assignee.email?.split("@")[0] || "—"
                  : <span className="text-ink-muted/60">Unassigned</span>}
              </Td>
              <Td className="text-ink-muted text-xs">
                {t.created_at ? new Date(t.created_at).toLocaleDateString() : "—"}
              </Td>
              <Td>
                <Button size="sm" variant="ghost" onClick={() => openTicket(t)}>View</Button>
                {isOwner && (
                  <Button size="sm" variant="danger" onClick={() => setBanTarget(t)}>Ban</Button>
                )}
              </Td>
            </tr>
          ))
          )}
        </Table>

        <Modal open={selected !== null} title={selected ? "Ticket " + selected.ticket_number : ""} onClose={() => setSelected(null)}>
          {selected && (
            <div className="space-y-4 max-h-[75vh] overflow-y-auto">
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div><span className="text-ink-muted">Subject:</span> <b>{selected.subject}</b></div>
                <div><span className="text-ink-muted">Source:</span> {selected.source || "dashboard"}</div>
                <div><span className="text-ink-muted">Created:</span> {fmtDate(selected.created_at)}</div>
                <div><span className="text-ink-muted">Resolved:</span> {fmtDate(selected.resolved_at)}</div>
              </div>

              <div className="bg-raised border border-line rounded-lg p-3">
                <h3 className="text-xs text-ink-muted mb-2">User Info</h3>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div><span className="text-ink-muted">Name:</span> {selected.user?.first_name || "—"}</div>
                  <div><span className="text-ink-muted">Telegram:</span> {selected.user?.telegram_username ? "@" + selected.user.telegram_username : selected.user?.telegram_id || "—"}</div>
                  <div><span className="text-ink-muted">Email:</span> {selected.user?.email || "—"}</div>
                  <div><span className="text-ink-muted">User ID:</span> <span className="font-mono text-xs">{selected.user_id?.slice(0, 12)}...</span></div>
                </div>
              </div>
              {selected.license && (
                <div className="bg-raised border border-line rounded-lg p-3">
                  <h3 className="text-xs text-ink-muted mb-2">License</h3>
                  <div className="text-sm">
                    <div><span className="text-ink-muted">Plan:</span> {selected.license.plan || "—"}</div>
                    <div><span className="text-ink-muted">Key:</span> <code className="font-mono text-xs">{selected.license.license_key || "—"}</code></div>
                  </div>
                </div>
              )}

              <div>
                <label className="block text-xs font-medium text-ink-soft mb-1.5">Conversation</label>
                <div className="space-y-2">
                  {selected.messages && selected.messages.length > 0 ? (
                    selected.messages.map((m) => (
                      <div
                        key={m.id}
                        className={
                          "rounded-lg border p-3 text-sm " +
                          (m.is_internal
                            ? "bg-amber-500/5 border-amber-500/30"
                            : m.author_role === "client"
                              ? "bg-raised border-line"
                              : "bg-brand-tint border-brand-500/30")
                        }
                      >
                        <div className="flex items-center gap-2 mb-1 text-xs text-ink-muted">
                          <b className="text-ink">{m.author_name || m.author_role}</b>
                          {m.is_internal && <Badge tone="amber">Internal note</Badge>}
                          <span>{m.kind === "note" ? "note" : m.author_role}</span>
                          <span className="ml-auto">{fmtDate(m.created_at)}</span>
                        </div>
                        <p className="whitespace-pre-wrap">{m.body}</p>
                      </div>
                    ))
                  ) : (
                    <div className="bg-raised border border-line rounded-lg p-3">
                      <p className="whitespace-pre-wrap text-sm">{selected.description}</p>
                    </div>
                  )}
                </div>
              </div>

              {selected.escalated && (
                <div className="bg-danger/10 border border-danger/40 rounded-lg p-3 text-sm text-danger">
                  <b>Escalated</b> to <b>{selected.escalation_target || "—"}</b>
                  {selected.escalation_reason ? ` — ${selected.escalation_reason}` : ""}
                  {selected.escalated_by && (
                    <div className="text-xs mt-1 text-danger/70">
                      by {selected.escalated_by.slice(0, 8)} at {fmtDate(selected.escalated_at)}
                    </div>
                  )}
                </div>
              )}

              {selected.status !== "closed" && (
                <div>
                  <div className="flex items-center gap-2 mb-1.5">
                    <label className="block text-xs font-medium text-ink-soft">Reply</label>
                    <label className="flex items-center gap-1.5 text-xs text-ink-muted cursor-pointer ml-2">
                      <input
                        type="checkbox"
                        checked={replyInternal}
                        onChange={(e) => setReplyInternal(e.target.checked)}
                        className="accent-brand-500"
                      />
                      Internal note (staff only)
                    </label>
                  </div>
                  <textarea
                    value={reply}
                    onChange={(e) => setReply(e.target.value)}
                    rows={3}
                    placeholder={replyInternal ? "Internal note for staff..." : "Write a reply..."}
                    className="w-full rounded-lg border border-line bg-input px-3 py-2 text-sm text-ink placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500"
                  />
                  <div className="mt-2">
                    <Button size="sm" onClick={sendReply} loading={saving} disabled={!reply.trim()}>
                      {replyInternal ? "Add Note" : "Send Reply"}
                    </Button>
                  </div>
                </div>
              )}

              <div className="grid grid-cols-2 gap-3">
                <SelectField label="Status" value={newStatus} onChange={(e) => setNewStatus(e.target.value)}>
                  {Object.entries(STATUS_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                </SelectField>
                <SelectField label="Priority" value={newPriority} onChange={(e) => setNewPriority(e.target.value)}>
                  {Object.entries(PRIORITY_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                </SelectField>
                <SelectField label="Category" value={newCategory} onChange={(e) => setNewCategory(e.target.value)}>
                  {Object.entries(CATEGORY_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                </SelectField>
                <div>
                  <label className="block text-xs font-medium text-ink-soft mb-1.5">Assignee</label>
                  <select
                    value={assigneeId}
                    onChange={(e) => setAssigneeId(e.target.value)}
                    className="w-full rounded-lg border border-line bg-input px-3 py-2 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500"
                  >
                    <option value="">Unassigned</option>
                    {staffUsers.map((u) => <option key={u.id} value={u.id}>{staffName(u)}</option>)}
                  </select>
                  {selectedAssigneeName && assigneeId === selected.assignee_id && (
                    <div className="text-[10px] text-ink-muted mt-1">Currently: {selectedAssigneeName}</div>
                  )}
                </div>
              </div>
              <div className="flex gap-2 flex-wrap items-center">
                <Button onClick={saveChanges} loading={saving} disabled={!isAdmin}>Save Changes</Button>
                {isAdmin && !selected.escalated && selected.status !== "closed" && (
                  <>
                    <SelectField
                      label="Escalate to"
                      value={escalateTarget}
                      onChange={(e) => setEscalateTarget(e.target.value)}
                    >
                      {ESCALATION_TARGETS.map((v) => <option key={v} value={v}>{v}</option>)}
                    </SelectField>
                    <input
                      type="text"
                      value={escalateReason}
                      onChange={(e) => setEscalateReason(e.target.value)}
                      placeholder="Escalation reason"
                      className="rounded-lg border border-line bg-input px-3 py-2 text-sm text-ink placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500"
                    />
                    <Button variant="danger" onClick={escalateAction} loading={saving}>Escalate</Button>
                  </>
                )}
                <Button variant="ghost" onClick={() => setSelected(null)}>Close</Button>
              </div>
            </div>
          )}
        </Modal>

        <ConfirmDialog
          open={!!banTarget}
          title="Ban user"
          description={`Ban the owner of ${banTarget?.ticket_number || "this ticket"} and suspend all their licenses? This cannot be undone.`}
          confirmLabel="Ban User"
          tone="danger"
          loading={confirmBusy}
          onConfirm={banUser}
          onCancel={() => setBanTarget(null)}
        />
      </div>
    </PermissionGuard>
  );
}
