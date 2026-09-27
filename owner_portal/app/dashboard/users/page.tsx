"use client";

import { useEffect, useState, useCallback } from "react";
import OwnerPermissionGuard from "@/components/auth/owner_permission_guard";
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
  UserItem,
} from "@/lib/api";
import {
  PageHeader,
  Card,
  Table,
  Td,
  Badge,
  Button,
  TextField,
  SelectField,
  Skeleton,
  EmptyState,
} from "@ds/components/ui";
import { Modal, ConfirmDialog } from "@ds/components/Modal";
import { Icon } from "@ds/components/Icon";
import { parseApiError } from "@/lib/errors";

const EMPTY_FORM = { email: "", password: "", first_name: "", last_name: "", role_id: "" };

function statusTone(status?: string): "green" | "gray" | "amber" | "red" | "blue" {
  if (status === "active") return "green";
  if (status === "pending") return "amber";
  if (status === "suspended" || status === "banned" || status === "deleted") return "red";
  return "gray";
}

export default function UsersPage() {
  const [data, setData] = useState<PaginatedUsers | null>(null);
  const [roles, setRoles] = useState<RoleItem[]>([]);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [assigning, setAssigning] = useState<{ userId: string; roleId: string } | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<UserItem | null>(null);
  const [confirmSuspend, setConfirmSuspend] = useState<UserItem | null>(null);
  const [editUser, setEditUser] = useState<UserItem | null>(null);
  const [editForm, setEditForm] = useState({ first_name: "", last_name: "", email: "", role_id: "" });

  const LIMIT = 20;

  const load = useCallback(async (q: string, off: number) => {
    const params = `?limit=${LIMIT}&offset=${off}${q ? `&q=${encodeURIComponent(q)}` : ""}`;
    try {
      const [u, r] = await Promise.all([listUsers(params), listRoles()]);
      setData(u as PaginatedUsers);
      setRoles(r.items);
    } catch (e) {
      setError(parseApiError(e));
    }
  }, []);

  useEffect(() => { load(search, offset); }, [load, search, offset]);

  const handleSuspend = async (id: string) => {
    try {
      await suspendUser(id);
      setConfirmSuspend(null);
      load(search, offset);
    } catch (e) {
      setError(parseApiError(e));
      setConfirmSuspend(null);
    }
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
    try {
      await deleteUser(id);
      setConfirmDelete(null);
      load(search, offset);
    } catch (e) {
      setError(parseApiError(e));
      setConfirmDelete(null);
    }
  };

  const handleEditStart = (u: UserItem) => {
    setEditUser(u);
    const roleId = roles.find(r => r.name === u.role)?.id || "";
    setEditForm({ first_name: u.first_name || "", last_name: u.last_name || "", email: u.email || "", role_id: roleId });
  };

  const handleEditSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editUser) return;
    setSaving(true);
    try {
      await updateUser(editUser.id, editForm);
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
      await createUser(form);
      setShowCreate(false);
      setForm(EMPTY_FORM);
      load(search, offset);
    } catch (err) {
      setError(parseApiError(err));
    } finally {
      setSaving(false);
    }
  };

  const inputCls =
    "h-9 w-full rounded-lg border border-line bg-input px-3 text-sm text-ink placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500 transition-colors";

  return (
    <OwnerPermissionGuard permission="users.read">
      <div className="flex flex-col gap-5 max-w-6xl">
        <PageHeader
          title="Users"
          subtitle="Full client base — account state, roles and access control."
          actions={
            <Button icon="plus" onClick={() => setShowCreate(true)}>
              Create
            </Button>
          }
        />

        {error && (
          <div className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
            {error}
          </div>
        )}

        <Card
          title="User directory"
          subtitle={data ? `${data.total} total` : undefined}
          icon="users"
          actions={
            <div className="flex items-center gap-2">
              <TextField
                icon="search"
                placeholder="Search email or name..."
                value={search}
                onChange={(e) => { setSearch(e.target.value); setOffset(0); }}
                className="w-64"
              />
            </div>
          }
          bodyClassName="p-0"
        >
          {!data ? (
            <div className="p-5 space-y-3">
              {[0, 1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-10 rounded-lg" />
              ))}
            </div>
          ) : data.items.length === 0 ? (
            <EmptyState
              icon="users"
              title="No users found"
              description={search ? "Try a different search term." : "Create the first user to get started."}
            />
          ) : (
            <Table columns={["Name", "Email", "Role", "Status", "Last Login", "Actions"]}>
              {data.items.map((u) => (
                <tr key={u.id}>
                  <Td>
                    <span className="text-sm font-medium text-ink">
                      {u.first_name || u.last_name ? `${u.first_name || ""} ${u.last_name || ""}`.trim() : "—"}
                    </span>
                  </Td>
                  <Td mono className="text-xs text-ink-soft">{u.email || "—"}</Td>
                  <Td>
                    {assigning?.userId === u.id ? (
                      <select
                        value={assigning.roleId}
                        onChange={(e) => setAssigning({ userId: u.id, roleId: e.target.value })}
                        onBlur={() => handleAssignRole(u.id, assigning.roleId)}
                        className="h-8 rounded-lg border border-line bg-input px-2 text-xs text-ink focus:outline-none focus:border-brand-500"
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
                        className="text-xs text-brand-400 hover:underline"
                      >
                        {u.role || "—"}
                      </button>
                    )}
                  </Td>
                  <Td>
                    <Badge tone={statusTone(u.account_status)}>{u.account_status}</Badge>
                  </Td>
                  <Td className="text-xs text-ink-muted">
                    {u.last_login ? new Date(u.last_login).toLocaleString() : "—"}
                  </Td>
                  <Td>
                    <div className="flex items-center gap-1.5">
                      {u.account_status === "active" ? (
                        <Button
                          size="sm"
                          variant="danger"
                          onClick={() => setConfirmSuspend(u)}
                        >
                          Suspend
                        </Button>
                      ) : (
                        <Button size="sm" variant="success" onClick={() => handleActivate(u.id)}>
                          {u.account_status === "deleted" ? "Reactivate" : "Activate"}
                        </Button>
                      )}
                      <Button size="sm" variant="ghost" icon="edit" onClick={() => handleEditStart(u)}>
                        Edit
                      </Button>
                      <Button
                        size="sm"
                        variant="danger"
                        icon="trash"
                        onClick={() => setConfirmDelete(u)}
                      >
                        Delete
                      </Button>
                    </div>
                  </Td>
                </tr>
              ))}
            </Table>
          )}
        </Card>

        {data && data.total > LIMIT && (
          <div className="flex items-center justify-between text-sm text-ink-soft">
            <span>{data.total} total</span>
            <div className="flex gap-2">
              <Button
                size="sm"
                variant="secondary"
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - LIMIT))}
              >
                Previous
              </Button>
              <Button
                size="sm"
                variant="secondary"
                disabled={offset + LIMIT >= data.total}
                onClick={() => setOffset(offset + LIMIT)}
              >
                Next
              </Button>
            </div>
          </div>
        )}

        <Modal
          open={showCreate}
          onClose={() => setShowCreate(false)}
          title="Create User"
          icon="info"
        >
          <form onSubmit={handleCreate} className="flex flex-col gap-3">
            <TextField label="Email" type="email" required
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })} />
            <TextField label="Password" type="password" required
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })} />
            <div className="grid grid-cols-2 gap-3">
              <TextField label="First name"
                value={form.first_name}
                onChange={(e) => setForm({ ...form, first_name: e.target.value })} />
              <TextField label="Last name"
                value={form.last_name}
                onChange={(e) => setForm({ ...form, last_name: e.target.value })} />
            </div>
            <SelectField label="Role"
              value={form.role_id}
              onChange={(e) => setForm({ ...form, role_id: e.target.value })}>
              <option value="">Select role</option>
              {roles.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
            </SelectField>
            <div className="flex justify-end gap-2 mt-2">
              <Button variant="ghost" onClick={() => setShowCreate(false)}>Cancel</Button>
              <Button type="submit" loading={saving}>{saving ? "Creating..." : "Create"}</Button>
            </div>
          </form>
        </Modal>

        <Modal
          open={!!editUser}
          onClose={() => setEditUser(null)}
          title={`Edit User${editUser ? ` — ${editUser.email || editUser.id.slice(0, 8)}` : ""}`}
          icon="info"
        >
          <form onSubmit={handleEditSave} className="flex flex-col gap-3">
            <div className="grid grid-cols-2 gap-3">
              <TextField label="First name"
                value={editForm.first_name}
                onChange={(e) => setEditForm({ ...editForm, first_name: e.target.value })} />
              <TextField label="Last name"
                value={editForm.last_name}
                onChange={(e) => setEditForm({ ...editForm, last_name: e.target.value })} />
            </div>
            <TextField label="Email"
              value={editForm.email}
              onChange={(e) => setEditForm({ ...editForm, email: e.target.value })} />
            <SelectField label="Role"
              value={editForm.role_id}
              onChange={(e) => setEditForm({ ...editForm, role_id: e.target.value })}>
              <option value="">No role</option>
              {roles.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
            </SelectField>
            <div className="flex justify-end gap-2 mt-2">
              <Button variant="ghost" onClick={() => setEditUser(null)}>Cancel</Button>
              <Button type="submit" loading={saving}>{saving ? "Saving..." : "Save"}</Button>
            </div>
          </form>
        </Modal>

        <ConfirmDialog
          open={!!confirmDelete}
          title="Delete user"
          description={
            confirmDelete
              ? `Deactivate ${confirmDelete.email || "this user"}? All sessions will be revoked and login blocked. Data is retained (soft delete) and this action is audited server-side.`
              : undefined
          }
          confirmLabel="Delete"
          cancelLabel="Cancel"
          tone="danger"
          requireText={confirmDelete?.email || undefined}
          loading={saving}
          onConfirm={() => confirmDelete && handleDelete(confirmDelete.id)}
          onCancel={() => setConfirmDelete(null)}
        />

        <ConfirmDialog
          open={!!confirmSuspend}
          title="Suspend user"
          description={
            confirmSuspend
              ? `Suspend ${confirmSuspend.email || "this user"}? They will be blocked from the platform until reactivated.`
              : undefined
          }
          confirmLabel="Suspend"
          cancelLabel="Cancel"
          tone="danger"
          onConfirm={() => confirmSuspend && handleSuspend(confirmSuspend.id)}
          onCancel={() => setConfirmSuspend(null)}
        />
      </div>
    </OwnerPermissionGuard>
  );
}
