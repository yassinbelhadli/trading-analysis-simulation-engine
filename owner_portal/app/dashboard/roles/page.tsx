"use client";

import { useEffect, useState, useCallback } from "react";
import OwnerPermissionGuard from "@/components/auth/owner_permission_guard";
import { listRoles, listPermissions, createRole, updateRole, deleteRole, RoleItem, PermissionItem } from "@/lib/api";
import { PageHeader, Card, Badge, Button, TextField, SelectField, Skeleton, EmptyState } from "@ds/components/ui";
import { Modal, ConfirmDialog } from "@ds/components/Modal";
import { Icon } from "@ds/components/Icon";

export default function RolesPage() {
  const [roles, setRoles] = useState<RoleItem[]>([]);
  const [allPerms, setAllPerms] = useState<PermissionItem[]>([]);
  const [selectedRole, setSelectedRole] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [editingRole, setEditingRole] = useState<RoleItem | null>(null);
  const [formName, setFormName] = useState("");
  const [formDesc, setFormDesc] = useState("");
  const [formPerms, setFormPerms] = useState<Set<string>>(new Set());
  const [saving, setSaving] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<RoleItem | null>(null);

  const load = useCallback(async () => {
    try {
      const [r, p] = await Promise.all([listRoles(), listPermissions()]);
      setRoles(r.items);
      setAllPerms(p.items);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const selected = roles.find((r) => r.id === selectedRole);
  const permsByResource: Record<string, PermissionItem[]> = {};
  for (const p of allPerms) {
    if (!permsByResource[p.resource]) permsByResource[p.resource] = [];
    permsByResource[p.resource].push(p);
  }

  const openEdit = (role: RoleItem) => {
    setEditingRole(role);
    setFormName(role.name);
    setFormDesc(role.description || "");
    setFormPerms(new Set(role.permissions.map((p) => p.id)));
  };

  const openCreate = () => {
    setEditingRole(null);
    setFormName("");
    setFormDesc("");
    setFormPerms(new Set());
    setShowCreate(true);
  };

  const togglePerm = (pid: string) => {
    setFormPerms((prev) => {
      const next = new Set(prev);
      if (next.has(pid)) next.delete(pid);
      else next.add(pid);
      return next;
    });
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      const permIds = Array.from(formPerms);
      if (editingRole) {
        await updateRole(editingRole.id, { name: formName, description: formDesc || undefined, permission_ids: permIds });
      } else {
        await createRole({ name: formName, description: formDesc || undefined, permission_ids: permIds });
      }
      setShowCreate(false);
      setEditingRole(null);
      load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteRole(id);
      setConfirmDelete(null);
      if (selectedRole === id) setSelectedRole(null);
      load();
    } catch (e) {
      setError((e as Error).message);
      setConfirmDelete(null);
    }
  };

  const inputCls =
    "h-9 w-full rounded-lg border border-line bg-input px-3 text-sm text-ink placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500 transition-colors";

  return (
    <OwnerPermissionGuard permission="roles.read">
      <div className="flex flex-col gap-5 max-w-6xl">
        <PageHeader
          title="Roles & Permissions"
          subtitle="Role definitions and the permission grants they carry. System roles cannot be edited or deleted."
          actions={
            <Button icon="plus" onClick={openCreate}>
              Create Role
            </Button>
          }
        />

        {error && (
          <div className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
            {error}
          </div>
        )}

        {!roles.length && !error ? (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
            <Skeleton className="h-72 rounded-xl" />
            <Skeleton className="h-72 rounded-xl lg:col-span-2" />
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
            <Card title="Roles" icon="shield-check" bodyClassName="p-0">
              {roles.map((r) => (
                <div
                  key={r.id}
                  className={`flex flex-col gap-1 px-4 py-3 border-b border-line last:border-b-0 transition-colors ${
                    selectedRole === r.id ? "bg-brand-tint" : "hover:bg-hover"
                  }`}
                >
                  <button onClick={() => setSelectedRole(r.id)} className="w-full text-left">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-ink">{r.name}</span>
                      {r.is_system && <Badge tone="blue">System</Badge>}
                    </div>
                    {r.description && <div className="text-xs text-ink-muted mt-0.5">{r.description}</div>}
                    <div className="text-xs text-ink-soft mt-1">{r.permissions.length} permissions</div>
                  </button>
                  {!r.is_system && (
                    <div className="flex gap-2 mt-0.5">
                      <button onClick={() => openEdit(r)} className="text-xs text-brand-400 hover:underline">
                        Edit
                      </button>
                      <button onClick={() => setConfirmDelete(r)} className="text-xs text-danger hover:underline">
                        Delete
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </Card>

            <Card
              title={selected ? selected.name : "Permissions"}
              icon="key"
              subtitle={
                selected
                  ? `${selected.permissions.length} granted permission${selected.permissions.length !== 1 ? "s" : ""}${selected.is_system ? " · system role" : ""}`
                  : undefined
              }
              actions={
                selected && !selected.is_system ? (
                  <Button size="sm" variant="secondary" icon="edit" onClick={() => openEdit(selected)}>
                    Edit Permissions
                  </Button>
                ) : null
              }
              className="lg:col-span-2"
            >
              {!selected ? (
                <EmptyState
                  icon="shield-check"
                  title="Select a role"
                  description="Choose a role on the left to inspect its permission grants."
                />
              ) : (
                <div className="space-y-4">
                  {Object.entries(permsByResource).map(([resource, perms]) => {
                    const hasAll = perms.every((p) =>
                      selected.permissions.some((sp) => sp.resource === p.resource && sp.action === p.action)
                    );
                    return (
                      <div key={resource}>
                        <div className="flex items-center gap-2 mb-2">
                          <span className="text-xs font-semibold uppercase tracking-wide text-ink-muted">{resource}</span>
                          {hasAll && <Badge tone="green">full access</Badge>}
                        </div>
                        <div className="flex flex-wrap gap-1.5">
                          {perms.map((p) => {
                            const has = selected.permissions.some(
                              (sp) => sp.resource === p.resource && sp.action === p.action
                            );
                            return (
                              <Badge key={p.id} tone={has ? "green" : "gray"}>
                                {has && <Icon name="check" className="h-3 w-3" />}
                                {p.action}
                              </Badge>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </Card>
          </div>
        )}

        <Modal
          open={showCreate || !!editingRole}
          onClose={() => { setShowCreate(false); setEditingRole(null); }}
          title={editingRole ? `Edit Role: ${editingRole.name}` : "Create Role"}
          icon="info"
          size="lg"
        >
          <form onSubmit={handleSave} className="flex flex-col gap-3">
            <div className="grid grid-cols-2 gap-3">
              <TextField label="Role name" required
                value={formName}
                onChange={(e) => setFormName(e.target.value)} />
              <TextField label="Description"
                value={formDesc}
                onChange={(e) => setFormDesc(e.target.value)} />
            </div>
            <div className="border-t border-line pt-3">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Permissions</span>
                <span className="text-[11px] text-ink-soft">{Array.from(formPerms).length} selected</span>
              </div>
              <div className="max-h-72 overflow-y-auto space-y-1.5">
                {Object.entries(permsByResource).map(([resource, perms]) => {
                  const allChecked = perms.every((p) => formPerms.has(p.id));
                  return (
                    <div key={resource} className="rounded-lg border border-line bg-base px-3 py-2">
                      <div className="flex items-center justify-between mb-1">
                        <label className="flex items-center gap-1.5 cursor-pointer text-xs font-medium text-ink">
                          <input
                            type="checkbox"
                            checked={allChecked}
                            onChange={() => {
                              if (allChecked) perms.forEach((p) => togglePerm(p.id));
                              else perms.forEach((p) => { if (!formPerms.has(p.id)) togglePerm(p.id); });
                            }}
                            className="accent-brand-500"
                          />
                          <span className="capitalize">{resource.replace(/_/g, " ")}</span>
                        </label>
                        <span className="text-[10px] text-ink-muted">
                          {perms.filter((p) => formPerms.has(p.id)).length}/{perms.length}
                        </span>
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {perms.map((p) => (
                          <label
                            key={p.id}
                            className={`text-[10px] px-1.5 py-0.5 rounded-full border cursor-pointer transition-colors ${
                              formPerms.has(p.id)
                                ? "bg-brand-tint border-brand-500/50 text-brand-400"
                                : "border-transparent text-ink-soft hover:border-line"
                            }`}
                          >
                            <input type="checkbox" checked={formPerms.has(p.id)} onChange={() => togglePerm(p.id)} className="hidden" />
                            {p.action.replace(/_/g, " ")}
                          </label>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-2">
              <Button variant="ghost" onClick={() => { setShowCreate(false); setEditingRole(null); }}>
                Cancel
              </Button>
              <Button type="submit" loading={saving}>{saving ? "Saving..." : "Save"}</Button>
            </div>
          </form>
        </Modal>

        <ConfirmDialog
          open={!!confirmDelete}
          title="Delete role"
          description={
            confirmDelete
              ? `Delete role "${confirmDelete.name}"? Users holding this role will lose its permissions. This action is audited.`
              : undefined
          }
          confirmLabel="Delete"
          cancelLabel="Cancel"
          tone="danger"
          loading={saving}
          onConfirm={() => confirmDelete && handleDelete(confirmDelete.id)}
          onCancel={() => setConfirmDelete(null)}
        />
      </div>
    </OwnerPermissionGuard>
  );
}
