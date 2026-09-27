"use client";

import { useEffect, useState, useCallback } from "react";
import StatusBadge from "@/components/StatusBadge";
import Modal from "@/components/Modal";
import PermissionGuard from "@/components/auth/permission_guard";
import { listNews, getEngineStatus, createNews, updateNews, deleteNews, broadcastNews, NewsItem, EngineStatus } from "@/lib/api";
import { Badge, Button, Card, PageHeader, Table, Td } from "@ds/components/ui";
import { ConfirmDialog } from "@ds/components/Modal";

export default function NewsPage() {
  const [items, setItems] = useState<NewsItem[]>([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState<NewsItem | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ title: "", body: "", category: "general", published: false });
  const [saving, setSaving] = useState(false);
  const [engine, setEngine] = useState<EngineStatus | null>(null);
  const [tab, setTab] = useState<"calendar" | "announcements">("calendar");
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [broadcastTarget, setBroadcastTarget] = useState<string | null>(null);
  const [broadcastBusy, setBroadcastBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [res, eng] = await Promise.all([
        listNews(),
        getEngineStatus(),
      ]);
      setItems(res.items);
      setTotal(res.total);
      setEngine(eng);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const openCreate = () => {
    setShowCreate(true);
    setForm({ title: "", body: "", category: "general", published: false });
  };

  const openEdit = (n: NewsItem) => {
    setEditing(n);
    setForm({ title: n.title, body: n.body, category: n.category, published: n.published });
  };

  const closeForm = () => { setEditing(null); setShowCreate(false); };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      if (editing) {
        await updateNews(editing.id, form);
      } else {
        await createNews(form);
      }
      closeForm();
      load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setDeleteBusy(true);
    try {
      await deleteNews(deleteTarget);
      setDeleteTarget(null);
      load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setDeleteBusy(false);
    }
  };

  const handleBroadcast = async (id: string) => {
    setBroadcastBusy(true);
    try {
      const res = await broadcastNews(id);
      setBroadcastTarget(null);
      load();
      setError(`Broadcast sent to ${res.broadcasted} users`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBroadcastBusy(false);
    }
  };

  return (
    <PermissionGuard permission="admin.overview">
      <div>
        <PageHeader
          title="News"
          subtitle={tab === "calendar" ? "Economic calendar and news filter" : "Client announcements and broadcasts"}
          actions={
            <>
              <Button
                size="sm"
                variant={tab === "calendar" ? "primary" : "ghost"}
                onClick={() => setTab("calendar")}
              >
                Economic Calendar
              </Button>
              <Button
                size="sm"
                variant={tab === "announcements" ? "primary" : "ghost"}
                onClick={() => setTab("announcements")}
              >
                Announcements
              </Button>
            </>
          }
        />

        {error && <div className="text-warn text-sm mb-3">{error}</div>}

        {tab === "calendar" && (
          <div className="space-y-4">
            {/* Engine Status Bar */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
              <div className="bg-raised border border-line rounded-lg p-3">
                <div className="text-[10px] text-ink-muted uppercase tracking-wider">Engine</div>
                <div className="flex items-center gap-1.5 mt-1">
                  <span className={`inline-block w-2 h-2 rounded-full ${engine?.running ? "bg-ok" : "bg-danger"}`} />
                  <span className="text-sm font-semibold text-ink">{engine?.running ? "Running" : "Stopped"}</span>
                </div>
                {engine?.cache_exists === false && (
                  <div className="text-[10px] text-warn mt-1">Waiting for first fetch...</div>
                )}
              </div>
              <div className="bg-raised border border-line rounded-lg p-3">
                <div className="text-[10px] text-ink-muted uppercase tracking-wider">Events Cached</div>
                <div className="text-xl font-bold text-ink mt-1 font-display">{engine?.total_events ?? "—"}</div>
              </div>
              <div className="bg-raised border border-line rounded-lg p-3">
                <div className="text-[10px] text-ink-muted uppercase tracking-wider">USD Events Today</div>
                <div className="text-xl font-bold text-ink mt-1 font-display">{engine?.usd_events_today ?? "—"}</div>
              </div>
              <div className="bg-raised border border-line rounded-lg p-3">
                <div className="text-[10px] text-ink-muted uppercase tracking-wider">Last Fetch</div>
                <div className="text-sm font-semibold text-ink mt-1">
                  {engine?.last_fetch_ago_sec != null
                    ? engine.last_fetch_ago_sec < 60
                      ? "Just now"
                      : engine.last_fetch_ago_sec < 3600
                        ? `${Math.floor(engine.last_fetch_ago_sec / 60)}m ago`
                        : `${Math.floor(engine.last_fetch_ago_sec / 3600)}h ago`
                    : "—"}
                </div>
                {engine?.running && (
                  <div className="text-[10px] text-ok/70 mt-0.5">Auto-fetch active</div>
                )}
              </div>
            </div>

            {/* Upcoming High-Impact Events */}
            <Card title="Upcoming High/Medium Impact Events" bodyClassName="p-0">
              <Table columns={["Time", "Currency", "Event", "Impact", "Forecast", "Previous"]}>
                {(!engine?.upcoming_high || engine.upcoming_high.length === 0) && (
                  <tr>
                    <td colSpan={6} className="text-center py-8 text-ink-muted text-xs">
                      {engine ? "No upcoming events. The engine will fetch new data from ForexFactory." : "Loading..."}
                    </td>
                  </tr>
                )}
                {engine?.upcoming_high.map((ev, i) => {
                  const isUSD = ev.currency === "USD";
                  return (
                    <tr key={i} className={isUSD ? "bg-warn/5" : ""}>
                      <Td mono className="text-[10px]">
                        {ev.time ? new Date(ev.time).toLocaleString() : "—"}
                      </Td>
                      <Td>
                        {isUSD ? (
                          <Badge tone="amber">USD</Badge>
                        ) : (
                          <span className="text-xs font-bold text-ink">{ev.currency}</span>
                        )}
                      </Td>
                      <Td className="text-xs">{ev.event}</Td>
                      <Td>
                        <Badge tone={ev.impact === "HIGH" ? "red" : "amber"}>{ev.impact}</Badge>
                      </Td>
                      <Td className="text-[10px] text-ink-muted">{ev.forecast || "—"}</Td>
                      <Td className="text-[10px] text-ink-muted">{ev.previous || "—"}</Td>
                    </tr>
                  );
                })}
              </Table>
            </Card>

            {/* News Filter Info */}
            <div className="bg-raised border border-line rounded-lg p-3">
              <div className="flex items-center gap-2">
                <span className={`inline-block w-2 h-2 rounded-full ${engine?.running ? "bg-ok" : "bg-danger"}`} />
                <div>
                  <div className="text-xs font-semibold text-ink">News Filter</div>
                  <div className="text-[10px] text-ink-muted">
                    {engine?.running
                      ? "Active — trading will be blocked 30min before high-impact USD events"
                      : "Inactive — start the API with news service enabled"}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {tab === "announcements" && (
          <div>
            <div className="flex items-center justify-between mb-3">
              <p className="text-xs text-ink-muted">{total} announcement{total !== 1 ? "s" : ""}</p>
              <Button icon="plus" onClick={openCreate}>New Post</Button>
            </div>

            <div className="space-y-2">
              {items.length === 0 && (
                <div className="text-center py-12 text-ink-muted text-sm">No announcements yet.</div>
              )}
              {items.map((n) => (
                <div key={n.id} className="bg-raised border border-line rounded-lg p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <h3 className="font-semibold text-sm text-ink truncate">{n.title}</h3>
                        <StatusBadge status={n.published ? "active" : "inactive"} />
                        {n.telegram_sent && <Badge tone="blue">Broadcast sent</Badge>}
                      </div>
                      {n.body && <p className="text-xs text-ink-muted line-clamp-2 mb-1">{n.body}</p>}
                      <div className="flex items-center gap-2 text-[10px] text-ink-muted">
                        <span className="px-1 py-0.5 rounded bg-input">{n.category}</span>
                        <span>{n.created_at ? new Date(n.created_at).toLocaleDateString() : "—"}</span>
                      </div>
                    </div>
                    <div className="flex gap-1 shrink-0">
                      <Button size="sm" variant="ghost" onClick={() => openEdit(n)}>Edit</Button>
                      <Button size="sm" variant="danger" onClick={() => setDeleteTarget(n.id)}>Delete</Button>
                      <Button size="sm" variant="success" onClick={() => setBroadcastTarget(n.id)}>Broadcast</Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            <Modal open={showCreate || editing !== null} onClose={closeForm} title={editing ? "Edit News" : "Create News"}>
              <form onSubmit={handleSave} className="flex flex-col gap-3">
                <div>
                  <label className="text-xs font-medium text-ink-soft mb-1.5 block">Title *</label>
                  <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required
                    className="w-full h-9 px-3 rounded-lg bg-input border border-line text-sm text-ink focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500 transition-colors" />
                </div>
                <div>
                  <label className="text-xs font-medium text-ink-soft mb-1.5 block">Body</label>
                  <textarea value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })}
                    className="w-full px-3 py-2 rounded-lg bg-input border border-line text-sm text-ink focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500 transition-colors min-h-[100px]" />
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-xs font-medium text-ink-soft mb-1.5 block">Category</label>
                    <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}
                      className="w-full h-9 px-3 rounded-lg bg-input border border-line text-sm text-ink focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500 transition-colors">
                      <option value="general">General</option>
                      <option value="update">Update</option>
                      <option value="maintenance">Maintenance</option>
                      <option value="alert">Alert</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-xs font-medium text-ink-soft mb-1.5 block">Status</label>
                    <label className="flex items-center gap-2 px-3 py-2 rounded-lg bg-input border border-line text-sm text-ink cursor-pointer">
                      <input type="checkbox" checked={form.published} onChange={(e) => setForm({ ...form, published: e.target.checked })} className="accent-brand-500" />
                      Published
                    </label>
                  </div>
                </div>
                <div className="flex justify-end gap-2 mt-2">
                  <Button size="sm" variant="ghost" type="button" onClick={closeForm}>Cancel</Button>
                  <Button size="sm" type="submit" loading={saving}>Save</Button>
                </div>
              </form>
            </Modal>

            <ConfirmDialog
              open={!!deleteTarget}
              title="Delete announcement"
              description="Delete this announcement? This cannot be undone."
              confirmLabel="Delete"
              tone="danger"
              loading={deleteBusy}
              onConfirm={handleDelete}
              onCancel={() => setDeleteTarget(null)}
            />

            <ConfirmDialog
              open={!!broadcastTarget}
              title="Broadcast announcement"
              description="Send this announcement to all subscribed clients via Telegram?"
              confirmLabel="Broadcast"
              tone="danger"
              loading={broadcastBusy}
              onConfirm={() => handleBroadcast(broadcastTarget!)}
              onCancel={() => setBroadcastTarget(null)}
            />
          </div>
        )}
      </div>
    </PermissionGuard>
  );
}
