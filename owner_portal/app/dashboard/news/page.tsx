"use client";

import { useEffect, useState, useCallback } from "react";
import OwnerPermissionGuard from "@/components/auth/owner_permission_guard";
import { listNews, getEngineStatus, createNews, updateNews, deleteNews, broadcastNews, NewsItem, EngineStatus } from "@/lib/api";
import { PageHeader, Card, Table, Td, Badge, Button, TextField, SelectField, Skeleton, EmptyState } from "@ds/components/ui";
import { Modal, ConfirmDialog } from "@ds/components/Modal";
import { Icon } from "@ds/components/Icon";

export default function NewsPage() {
  const [items, setItems] = useState<NewsItem[]>([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState<NewsItem | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ title: "", body: "", category: "general", published: false });
  const [saving, setSaving] = useState(false);
  const [broadcasting, setBroadcasting] = useState<NewsItem | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<NewsItem | null>(null);
  const [engine, setEngine] = useState<EngineStatus | null>(null);
  const [tab, setTab] = useState<"calendar" | "announcements">("calendar");

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

  const handleDelete = async (id: string) => {
    try {
      await deleteNews(id);
      setConfirmDelete(null);
      load();
    } catch (e) {
      setError((e as Error).message);
      setConfirmDelete(null);
    }
  };

  const handleBroadcast = async (id: string) => {
    setBroadcasting(null);
    setError("");
    try {
      const res = await broadcastNews(id);
      load();
      setError(`Broadcast sent to ${res.broadcasted} users`);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const inputCls =
    "h-9 w-full rounded-lg border border-line bg-input px-3 text-sm text-ink placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500 transition-colors";

  return (
    <OwnerPermissionGuard permission="admin.overview">
      <div className="flex flex-col gap-5 max-w-6xl">
        <PageHeader
          title="News"
          subtitle="Economic calendar feed and platform announcements with broadcast."
          actions={
            <>
              <Button
                size="sm"
                variant={tab === "calendar" ? "primary" : "secondary"}
                icon="calendar"
                onClick={() => setTab("calendar")}
              >
                Economic Calendar
              </Button>
              <Button
                size="sm"
                variant={tab === "announcements" ? "primary" : "secondary"}
                icon="newspaper"
                onClick={() => setTab("announcements")}
              >
                Announcements
              </Button>
            </>
          }
        />

        {error && (
          <div className="rounded-lg border border-warn/30 bg-warn/10 px-3 py-2 text-sm text-warn">
            {error}
          </div>
        )}

        {tab === "calendar" && (
          <>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="bg-raised border border-line rounded-xl p-4">
                <div className="text-[10px] uppercase tracking-wider text-ink-muted">Engine</div>
                <div className="flex items-center gap-1.5 mt-2">
                  <span className={`inline-block h-2 w-2 rounded-full ${engine?.running ? "bg-ok" : "bg-danger"}`} />
                  <span className="text-sm font-semibold text-ink">{engine?.running ? "Running" : "Stopped"}</span>
                </div>
                {engine?.cache_exists === false && (
                  <div className="text-[10px] text-warn mt-1">Waiting for first fetch...</div>
                )}
              </div>
              <div className="bg-raised border border-line rounded-xl p-4">
                <div className="text-[10px] uppercase tracking-wider text-ink-muted">Events Cached</div>
                <div className="text-xl font-bold text-ink mt-2 font-display">{engine?.total_events ?? "—"}</div>
              </div>
              <div className="bg-raised border border-line rounded-xl p-4">
                <div className="text-[10px] uppercase tracking-wider text-ink-muted">USD Events Today</div>
                <div className="text-xl font-bold text-ink mt-2 font-display">{engine?.usd_events_today ?? "—"}</div>
              </div>
              <div className="bg-raised border border-line rounded-xl p-4">
                <div className="text-[10px] uppercase tracking-wider text-ink-muted">Last Fetch</div>
                <div className="text-sm font-semibold text-ink mt-2">
                  {engine?.last_fetch_ago_sec != null
                    ? engine.last_fetch_ago_sec < 60
                      ? "Just now"
                      : engine.last_fetch_ago_sec < 3600
                        ? `${Math.floor(engine.last_fetch_ago_sec / 60)}m ago`
                        : `${Math.floor(engine.last_fetch_ago_sec / 3600)}h ago`
                    : "—"}
                </div>
                {engine?.running && (
                  <div className="text-[10px] text-brand-400/70 mt-0.5">Auto-fetch active</div>
                )}
              </div>
            </div>

            <Card
              title="Upcoming High/Medium Impact Events"
              icon="calendar"
              bodyClassName="p-0"
            >
              {!engine ? (
                <div className="p-5 space-y-3">
                  {[0, 1, 2].map((i) => (
                    <Skeleton key={i} className="h-8 rounded-lg" />
                  ))}
                </div>
              ) : !engine.upcoming_high || engine.upcoming_high.length === 0 ? (
                <EmptyState
                  icon="calendar"
                  title="No upcoming events"
                  description="The engine will fetch new data from ForexFactory."
                />
              ) : (
                <Table columns={["Time", "Currency", "Event", "Impact", "Forecast", "Previous"]}>
                  {engine.upcoming_high.map((ev, i) => {
                    const isUSD = ev.currency === "USD";
                    return (
                      <tr key={i} className={isUSD ? "bg-warn/[0.04]" : ""}>
                        <Td className="text-[10px] font-mono text-ink-soft">
                          {ev.time ? new Date(ev.time).toLocaleString() : "—"}
                        </Td>
                        <Td>
                          <span className={`text-xs font-bold ${isUSD ? "text-warn" : "text-ink"}`}>
                            {ev.currency}
                            {isUSD && <span className="text-[9px] text-warn/70 ml-1">(USD)</span>}
                          </span>
                        </Td>
                        <Td className="text-xs text-ink">{ev.event}</Td>
                        <Td>
                          <Badge tone={ev.impact === "HIGH" ? "red" : "amber"}>{ev.impact}</Badge>
                        </Td>
                        <Td className="text-[10px] text-ink-muted">{ev.forecast || "—"}</Td>
                        <Td className="text-[10px] text-ink-muted">{ev.previous || "—"}</Td>
                      </tr>
                    );
                  })}
                </Table>
              )}
            </Card>

            <Card title="News Filter" icon="shield-check">
              <p className="text-xs text-ink-soft">
                {engine?.running
                  ? "Active — trading will be blocked 30min before high-impact USD events"
                  : "Inactive — start the API with news service enabled"}
              </p>
            </Card>
          </>
        )}

        {tab === "announcements" && (
          <>
            <div className="flex items-center justify-between">
              <p className="text-xs text-ink-soft">{total} announcement{total !== 1 ? "s" : ""}</p>
              <Button icon="plus" onClick={openCreate}>
                New Post
              </Button>
            </div>

            {items.length === 0 ? (
              <EmptyState
                icon="newspaper"
                title="No announcements yet"
                description="Create the first announcement to communicate with clients."
                action={
                  <Button icon="plus" onClick={openCreate}>
                    New Post
                  </Button>
                }
              />
            ) : (
              <div className="space-y-2">
                {items.map((n) => (
                  <div key={n.id} className="bg-raised border border-line rounded-xl p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <h3 className="font-semibold text-sm text-ink truncate">{n.title}</h3>
                          <Badge tone={n.published ? "green" : "gray"}>
                            {n.published ? "Published" : "Draft"}
                          </Badge>
                          {n.telegram_sent && (
                            <Badge tone="blue">
                              <Icon name="send" className="h-3 w-3" />
                              Sent
                            </Badge>
                          )}
                        </div>
                        {n.body && <p className="text-xs text-ink-muted line-clamp-2 mb-1">{n.body}</p>}
                        <div className="flex items-center gap-2 text-[10px] text-ink-muted">
                          <span className="px-1 py-0.5 rounded bg-base">{n.category}</span>
                          <span>{n.created_at ? new Date(n.created_at).toLocaleDateString() : "—"}</span>
                        </div>
                      </div>
                      <div className="flex gap-1.5 shrink-0">
                        <Button size="sm" variant="ghost" icon="edit" onClick={() => openEdit(n)}>
                          Edit
                        </Button>
                        <Button size="sm" variant="danger" icon="trash" onClick={() => setConfirmDelete(n)}>
                          Delete
                        </Button>
                        <Button
                          size="sm"
                          variant="secondary"
                          icon="send"
                          onClick={() => setBroadcasting(n)}
                        >
                          Broadcast
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}

        <Modal
          open={showCreate || editing !== null}
          onClose={closeForm}
          title={editing ? "Edit News" : "Create News"}
          icon="info"
        >
          <form onSubmit={handleSave} className="flex flex-col gap-3">
            <TextField label="Title" required
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })} />
            <div>
              <label className="block text-xs font-medium text-ink-soft mb-1.5">Body</label>
              <textarea
                value={form.body}
                onChange={(e) => setForm({ ...form, body: e.target.value })}
                className={`${inputCls} min-h-[100px] pt-2`}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <SelectField
                label="Category"
                value={form.category}
                onChange={(e) => setForm({ ...form, category: e.target.value })}
              >
                <option value="general">General</option>
                <option value="update">Update</option>
                <option value="maintenance">Maintenance</option>
                <option value="alert">Alert</option>
              </SelectField>
              <div>
                <span className="block text-xs font-medium text-ink-soft mb-1.5">Status</span>
                <label className="flex items-center gap-2 h-9 px-3 rounded-lg bg-input border border-line text-sm cursor-pointer">
                  <input
                    type="checkbox"
                    checked={form.published}
                    onChange={(e) => setForm({ ...form, published: e.target.checked })}
                    className="accent-brand-500"
                  />
                  Published
                </label>
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-2">
              <Button variant="ghost" onClick={closeForm}>Cancel</Button>
              <Button type="submit" loading={saving}>{saving ? "Saving..." : "Save"}</Button>
            </div>
          </form>
        </Modal>

        <ConfirmDialog
          open={!!confirmDelete}
          title="Delete news item"
          description={
            confirmDelete
              ? `Delete "${confirmDelete.title}"? This removes the announcement permanently.`
              : undefined
          }
          confirmLabel="Delete"
          cancelLabel="Cancel"
          tone="danger"
          onConfirm={() => confirmDelete && handleDelete(confirmDelete.id)}
          onCancel={() => setConfirmDelete(null)}
        />

        <ConfirmDialog
          open={!!broadcasting}
          title="Broadcast announcement"
          description={
            broadcasting
              ? `Broadcast "${broadcasting.title}" to all users? This sends a notification to the entire client base.`
              : undefined
          }
          confirmLabel="Broadcast"
          cancelLabel="Cancel"
          onConfirm={() => broadcasting && handleBroadcast(broadcasting.id)}
          onCancel={() => setBroadcasting(null)}
        />
      </div>
    </OwnerPermissionGuard>
  );
}
