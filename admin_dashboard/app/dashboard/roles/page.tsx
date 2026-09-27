"use client";

import { useEffect, useState, useCallback } from "react";
import Modal from "@/components/Modal";
import PermissionGuard from "@/components/auth/permission_guard";
import { listRoles, listPermissions, createRole, updateRole, deleteRole, RoleItem, PermissionItem } from "@/lib/api";
import { Button, PageHeader } from "@ds/components/ui";
import { ConfirmDialog } from "@ds/components/Modal";
import { parseApiError } from "@/lib/errors";
import { hasPermission } from "@/lib/auth";

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
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);

  const canCreate = hasPermission("roles.create");
  const canUpdate = hasPermission("roles.update");
  const canDelete = hasPermission("roles.delete");

  const load = useCallback(async () => {
    try {
      const [r, p] = await Promise.all([listRoles(), listPermissions()]);
      setRoles(r.items);
      setAllPerms(p.items);
    } catch (e) {
      setError(parseApiError(e));
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
      setError(parseApiError(err));
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    setDeleteBusy(true);
    try {
      await deleteRole(id);
      setConfirmDelete(null);
      if (selectedRole === id) setSelectedRole(null);
      load();
    } catch (e) {
      setError(parseApiError(e));
    } finally {
      setDeleteBusy(false);
    }
  };

  return (
    <PermissionGuard permission="roles.read">
      <div>
        <PageHeader
          title="Roles & Permissions"
          subtitle="Manage access roles and their permissions"
          actions={
            canCreate && (
            <Button icon="plus" onClick={openCreate}>
              Create Role
            </Button>
            )
          }
        />

        {error && <div className="text-danger text-sm mb-3">{error}</div>}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-1">
            <div className="bg-raised border border-line rounded-xl overflow-hidden">
              <div className="px-4 py-3 border-b border-line text-sm font-semibold text-ink">Roles</div>
              {roles.map((r) => (
                <div key={r.id}
                  className={`w-full text-left px-4 py-3 text-sm border-b border-line last:border-b-0 transition-colors ${
                    selectedRole === r.id ? "bg-brand-tint" : "hover:bg-hover"
                  }`}
                >
                  <button onClick={() => setSelectedRole(r.id)} className="w-full text-left">
                    <div className="font-medium text-ink">{r.name}</div>
                    {r.description && <div className="text-xs text-ink-muted mt-0.5">{r.description}</div>}
                    <div className="text-xs text-ink-muted mt-0.5">{r.permissions.length} permissions{r.is_system ? " · System" : ""}</div>
                  </button>
                  {!r.is_system && (
                    <div className="flex gap-1 mt-1.5">
                      {canUpdate && <button onClick={() => openEdit(r)} className="text-xs text-brand-400 hover:underline">Edit</button>}
                      {canDelete && <button onClick={() => setConfirmDelete(r.id)} className="text-xs text-danger hover:underline">Delete</button>}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          <div className="lg:col-span-2">
            {selected ? (
              <div className="bg-raised border border-line rounded-xl overflow-hidden">
                <div className="px-4 py-3 border-b border-line flex items-center justify-between">
                  <div>
                    <div className="text-sm font-semibold text-ink">{selected.name}</div>
                    {selected.description && <div className="text-xs text-ink-muted mt-0.5">{selected.description}</div>}
                  </div>
                  {!selected.is_system && canUpdate && (
                    <button onClick={() => openEdit(selected)} className="text-xs text-brand-400 hover:underline">Edit Permissions</button>
                  )}
                </div>

                <div className="p-4 space-y-4">
                  {Object.entries(permsByResource).map(([resource, perms]) => {
                    const hasAll = perms.every((p) =>
                      selected.permissions.some((sp) => sp.resource === p.resource && sp.action === p.action)
                    );
                    return (
                      <div key={resource}>
                        <div className="flex items-center gap-2 mb-2">
                          <span className="text-xs font-semibold uppercase text-ink-muted">{resource}</span>
                          {hasAll && <span className="text-[10px] text-ok">(full access)</span>}
                        </div>
                        <div className="flex flex-wrap gap-1.5">
                          {perms.map((p) => {
                            const has = selected.permissions.some(
                              (sp) => sp.resource === p.resource && sp.action === p.action
                            );
                            return (
                              <span key={p.id}
                                className={`text-xs px-2 py-0.5 rounded-full border ${
                                  has
                                    ? "bg-ok/10 border-ok/30 text-ok"
                                    : "bg-input border-line text-ink-muted"
                                }`}
                              >
                                {p.action}
                              </span>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : (
              <div className="bg-raised border border-line rounded-xl p-8 text-center text-ink-muted text-sm">
                Select a role to view its permissions
              </div>
            )}
          </div>
        </div>

        <Modal open={showCreate || !!editingRole} onClose={() => { setShowCreate(false); setEditingRole(null); }}
          title={editingRole ? `Edit Role: ${editingRole.name}` : "Create Role"}>
          <form onSubmit={handleSave} className="flex flex-col gap-3">
            <input placeholder="Role name *" value={formName} onChange={(e) => setFormName(e.target.value)} required
              className="w-full h-9 px-3 rounded-lg bg-input border border-line text-sm text-ink placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500 transition-colors" />
            <input placeholder="Description" value={formDesc} onChange={(e) => setFormDesc(e.target.value)}
              className="w-full h-9 px-3 rounded-lg bg-input border border-line text-sm text-ink placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500 transition-colors" />
            <div className="border-t border-line pt-3">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold uppercase text-ink-muted">Permissions</span>
                <span className="text-[10px] text-ink-muted">{Array.from(formPerms).length} selected</span>
              </div>
              <div className="max-h-72 overflow-y-auto space-y-1.5">
                {Object.entries(permsByResource).map(([resource, perms]) => {
                  const allChecked = perms.every((p) => formPerms.has(p.id));
                  const someChecked = perms.some((p) => formPerms.has(p.id));
                  return (
                    <div key={resource} className="bg-input rounded-lg px-3 py-2 border border-line">
                      <div className="flex items-center justify-between mb-1">
                        <label className="flex items-center gap-1.5 cursor-pointer text-xs font-medium text-ink">
                          <input type="checkbox" checked={allChecked}
                            onChange={() => {
                              if (allChecked) perms.forEach((p) => togglePerm(p.id));
                              else perms.forEach((p) => { if (!formPerms.has(p.id)) togglePerm(p.id); });
                            }}
                            className="accent-brand-500" />
                          <span className="capitalize">{resource.replace(/_/g, " ")}</span>
                        </label>
                        <span className="text-[9px] text-ink-muted">{perms.filter((p) => formPerms.has(p.id)).length}/{perms.length}</span>
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {perms.map((p) => (
                          <label key={p.id}
                            className={`text-[10px] px-1.5 py-0.5 rounded-full border cursor-pointer transition-colors ${
                              formPerms.has(p.id)
                                ? "bg-brand-tint border-brand-500/30 text-brand-400"
                                : "border-line text-ink-muted hover:border-line-strong"
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
              <Button size="sm" variant="ghost" type="button" onClick={() => { setShowCreate(false); setEditingRole(null); }}>
                Cancel
              </Button>
              <Button size="sm" type="submit" loading={saving}>Save</Button>
            </div>
          </form>
        </Modal>

        <ConfirmDialog
          open={!!confirmDelete}
          title="Delete role"
          description="Delete this role? Users assigned to it will lose its permissions. This cannot be undone."
          confirmLabel="Delete"
          tone="danger"
          loading={deleteBusy}
          onConfirm={() => handleDelete(confirmDelete!)}
          onCancel={() => setConfirmDelete(null)}
        />
      </div>
    </PermissionGuard>
  );
}
