"use client";

import { useEffect, useState, useCallback } from "react";
import Modal from "@/components/Modal";
import PermissionGuard from "@/components/auth/permission_guard";
import {
  listUsers,
  listRoles,
  suspendUser,
  activateUser,
  assignRole,
  createUser,
  updateUser,
  deleteUser,
  PaginatedUsers,
  RoleItem,
} from "@/lib/api";
import { Button, Card, PageHeader, Table, Td, TextField, SelectField, StatusPill, Skeleton } from "@ds/components/ui";
import { ConfirmDialog } from "@ds/components/Modal";
import { hasPermission } from "@/lib/auth";
import { parseApiError } from "@/lib/errors";

const EMPTY_FORM = { email: "", password: "", first_name: "", last_name: "", role_id: "" };

type ConfirmAction = { type: "delete" | "suspend"; id: string } | null;

export default function UsersPage() {
  const [data, setData] = useState<PaginatedUsers | null>(null);
  const [roles, setRoles] = useState<RoleItem[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [assigning, setAssigning] = useState<{ userId: string; roleId: string } | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [confirm, setConfirm] = useState<ConfirmAction>(null);
  const [confirmBusy, setConfirmBusy] = useState(false);
  const [editUser, setEditUser] = useState<any | null>(null);
  const [editForm, setEditForm] = useState({ first_name: "", last_name: "", email: "", role_id: "" });

  // Role management (assign / list roles) is Owner-only — backend enforces via
  // require_role("owner") on /api/admin/roles*. Admin keeps user CRUD minus
  // role assignment.
  const canCreate = hasPermission("users.create");
  const canUpdate = hasPermission("users.update");
  const canDelete = hasPermission("users.delete");
  const isOwner = hasPermission("roles.assign");

  const LIMIT = 20;

  const load = useCallback(async (q: string, off: number) => {
    setLoading(true);
    const params = `?limit=${LIMIT}&offset=${off}${q ? `&q=${encodeURIComponent(q)}` : ""}`;
    try {
      const u = await listUsers(params);
      let r = { items: [] as RoleItem[] };
      if (isOwner) {
        try {
          r = (await listRoles()) as { items: RoleItem[] };
        } catch {
          // 403 for non-owner — role UI stays hidden for them.
        }
      }
      setData(u as PaginatedUsers);
      setRoles(r.items);
    } catch (e) {
      setError(parseApiError(e));
    } finally {
      setLoading(false);
    }
  }, [isOwner]);

  useEffect(() => { load(search, offset); }, [load, search, offset]);

  const handleSuspend = async (id: string) => {
    try {
      await suspendUser(id);
      setConfirm(null);
      load(search, offset);
    } catch (e) { setError(parseApiError(e)); }
  };

  const handleActivate = async (id: string) => {
    try { await activateUser(id); load(search, offset); }
    catch (e) { setError(parseApiError(e)); }
  };

  const handleAssignRole = async (userId: string, roleId: string) => {
    if (!roleId) return;
    try {
      await assignRole({ user_id: userId, role_id: roleId });
      setAssigning(null);
      load(search, offset);
    } catch (e) { setError(parseApiError(e)); }
  };

  const handleDelete = async (id: string) => {
    setConfirmBusy(true);
    try {
      await deleteUser(id);
      setConfirm(null);
      load(search, offset);
    } catch (e) {
      setError(parseApiError(e));
    } finally {
      setConfirmBusy(false);
    }
  };

  const handleEditStart = (u: any) => {
    setEditUser(u);
    const roleId = u.role_id || (roles.find(r => r.name === u.role)?.id) || "";
    setEditForm({ first_name: u.first_name || "", last_name: u.last_name || "", email: u.email || "", role_id: roleId });
  };

  const handleEditSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editUser) return;
    setSaving(true);
    try {
      // Role changes are Owner-only; admin keeps name/email editing.
      const payload = isOwner
        ? editForm
        : { first_name: editForm.first_name, last_name: editForm.last_name, email: editForm.email };
      await updateUser(editUser.id, payload);
      setEditUser(null);
      load(search, offset);
    } catch (err) {
      setError(parseApiError(err));
    } finally {
      setSaving(false);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await createUser(isOwner ? form : { ...form, role_id: "" });
      setShowCreate(false);
      setForm(EMPTY_FORM);
      load(search, offset);
    } catch (err) {
      setError(parseApiError(err));
    } finally {
      setSaving(false);
    }
  };

  const targetLabel = confirm?.type === "delete" ? "user" : "account access";

  return (
    <PermissionGuard permission="users.read">
      <div>
        <PageHeader
          title="Users"
          subtitle="Manage admin user accounts, roles and access status."
          actions={
            <div className="flex items-center gap-2">
              <TextField
                icon="search"
                placeholder="Search email or name..."
                value={search}
                onChange={(e) => { setSearch(e.target.value); setOffset(0); }}
                className="w-64"
              />
              {canCreate && (
                <Button icon="plus" onClick={() => setShowCreate(true)}>
                  Create
                </Button>
              )}
            </div>
          }
        />

        {error && <div className="text-danger text-sm mb-3">{error}</div>}

        <Card bodyClassName="p-0">
          <Table columns={["Name", "Email", "Role", "Status", "Last Login", "Actions"]}>
            {loading ? (
              <tr>
                <td colSpan={6} className="px-4 py-4">
                  <div className="flex flex-col gap-2">
                    <Skeleton className="h-9 w-full" />
                    <Skeleton className="h-9 w-full" />
                    <Skeleton className="h-9 w-full" />
                  </div>
                </td>
              </tr>
            ) : (!data || data.items.length === 0) ? (
              <tr>
                <td colSpan={6} className="text-center text-ink-muted py-8 px-4">
                  No users found
                </td>
              </tr>
            ) : (
            data?.items.map((u) => (
              <tr key={u.id}>
                <Td>
                  {u.first_name || u.last_name ? `${u.first_name || ""} ${u.last_name || ""}`.trim() : "—"}
                </Td>
                <Td mono>{u.email || "—"}</Td>
                <Td>
                  {isOwner ? (
                    assigning?.userId === u.id ? (
                      <select
                        value={assigning.roleId}
                        onChange={(e) => setAssigning({ userId: u.id, roleId: e.target.value })}
                        onBlur={() => handleAssignRole(u.id, assigning.roleId)}
                        className="h-8 rounded-md border border-line bg-input px-2 text-xs text-ink"
                        autoFocus
                      >
                        <option value="">Select...</option>
                        {roles.map((r) => (
                          <option key={r.id} value={r.id}>{r.name}</option>
                        ))}
                      </select>
                    ) : (
                      <button
                        onClick={() => setAssigning({ userId: u.id, roleId: u.role || "" })}
                        className="text-brand-400 hover:underline text-xs"
                      >
                        {u.role || "—"}
                      </button>
                    )
                  ) : (
                    <span className="text-xs">{u.role || "—"}</span>
                  )}
                </Td>
                <Td>
                  <StatusPill
                    status={u.account_status === "active" ? "active" : u.account_status === "suspended" ? "warning" : "inactive"}
                  >
                    {u.account_status}
                  </StatusPill>
                </Td>
                <Td className="text-ink-muted text-xs">
                  {u.last_login ? new Date(u.last_login).toLocaleString() : "—"}
                </Td>
                <Td>
                  <div className="flex gap-1">
                    {canUpdate && (
                      u.account_status === "active" ? (
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => setConfirm({ type: "suspend", id: u.id })}
                        >
                          Suspend
                        </Button>
                      ) : (
                        <Button size="sm" variant="success" icon="play" onClick={() => handleActivate(u.id)}>
                          Activate
                        </Button>
                      )
                    )}
                    {canUpdate && (
                      <Button size="sm" variant="ghost" icon="edit" onClick={() => handleEditStart(u)}>
                        Edit
                      </Button>
                    )}
                    {canDelete && (
                      <Button size="sm" variant="danger" icon="trash" onClick={() => setConfirm({ type: "delete", id: u.id })}>
                        Delete
                      </Button>
                    )}
                  </div>
                </Td>
              </tr>
            ))
            )}
          </Table>
        </Card>

        {data && data.total > LIMIT && (
          <div className="flex items-center justify-between mt-4 text-sm text-ink-muted">
            <span>{data.total} total</span>
            <div className="flex gap-2">
              <Button size="sm" variant="secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - LIMIT))}>
                Previous
              </Button>
              <Button size="sm" variant="secondary" disabled={offset + LIMIT >= data.total} onClick={() => setOffset(offset + LIMIT)}>
                Next
              </Button>
            </div>
          </div>
        )}

        {canCreate && (
        <Modal open={showCreate} onClose={() => setShowCreate(false)} title="Create User">
          <form onSubmit={handleCreate} className="flex flex-col gap-3">
            <TextField
              label="Email *"
              placeholder="Email"
              type="email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              required
            />
            <TextField
              label="Password *"
              placeholder="Password"
              type="password"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              required
            />
            <div className="grid grid-cols-2 gap-2">
              <TextField
                label="First name"
                placeholder="First name"
                value={form.first_name}
                onChange={(e) => setForm({ ...form, first_name: e.target.value })}
              />
              <TextField
                label="Last name"
                placeholder="Last name"
                value={form.last_name}
                onChange={(e) => setForm({ ...form, last_name: e.target.value })}
              />
            </div>
            {isOwner && (
              <SelectField
                label="Role"
                value={form.role_id}
                onChange={(e) => setForm({ ...form, role_id: e.target.value })}
              >
                <option value="">Select role</option>
                {roles.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
              </SelectField>
            )}
            <div className="flex justify-end gap-2 mt-2">
              <Button type="button" variant="ghost" onClick={() => setShowCreate(false)}>
                Cancel
              </Button>
              <Button type="submit" loading={saving}>
                {saving ? "Creating..." : "Create"}
              </Button>
            </div>
          </form>
        </Modal>
        )}

        {canUpdate && (
        <Modal open={!!editUser} onClose={() => setEditUser(null)} title={`Edit User${editUser ? ` — ${editUser.email || editUser.id.slice(0, 8)}` : ""}`}>
          <form onSubmit={handleEditSave} className="flex flex-col gap-3">
            <div className="grid grid-cols-2 gap-2">
              <TextField
                label="First name"
                value={editForm.first_name}
                onChange={(e) => setEditForm({ ...editForm, first_name: e.target.value })}
              />
              <TextField
                label="Last name"
                value={editForm.last_name}
                onChange={(e) => setEditForm({ ...editForm, last_name: e.target.value })}
              />
            </div>
            <TextField
              label="Email"
              value={editForm.email}
              onChange={(e) => setEditForm({ ...editForm, email: e.target.value })}
            />
            {isOwner && (
              <SelectField
                label="Role"
                value={editForm.role_id}
                onChange={(e) => setEditForm({ ...editForm, role_id: e.target.value })}
              >
                <option value="">No role</option>
                {roles.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
              </SelectField>
            )}
            <div className="flex justify-end gap-2 mt-2">
              <Button type="button" variant="ghost" onClick={() => setEditUser(null)}>
                Cancel
              </Button>
              <Button type="submit" loading={saving}>
                {saving ? "Saving..." : "Save"}
              </Button>
            </div>
          </form>
        </Modal>
        )}

        <ConfirmDialog
          open={!!confirm}
          title={confirm?.type === "delete" ? "Delete User" : "Suspend User"}
          description={
            confirm?.type === "delete"
              ? `This will permanently delete the ${targetLabel} and all associated records. This action cannot be undone.`
              : `This will suspend the ${targetLabel} immediately. The user will lose access until reactivated.`
          }
          confirmLabel={confirm?.type === "delete" ? "Delete" : "Suspend"}
          tone="danger"
          loading={confirmBusy}
          onConfirm={() => confirm && (confirm.type === "delete" ? handleDelete(confirm.id) : handleSuspend(confirm.id))}
          onCancel={() => setConfirm(null)}
        />
      </div>
    </PermissionGuard>
  );
}
