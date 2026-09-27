"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  PageHeader,
  SelectField,
  Skeleton,
  TextField,
} from "@ds/components/ui";
import { Icon } from "@ds/components/Icon";
import {
  ClientTicket,
  TICKET_CATEGORIES,
  createMyTicket,
  getMyTicket,
  listMyTickets,
  replyToMyTicket,
} from "@/lib/api";
import { useLocale } from "@/components/LocaleContext";

type View = { name: "list" } | { name: "detail"; ticketId: string } | { name: "new" };

const STATUS_TONE: Record<string, "green" | "blue" | "amber" | "red" | "gray"> = {
  open: "amber",
  in_progress: "blue",
  resolved: "green",
  closed: "gray",
};

const PRIORITY_TONE: Record<string, "green" | "blue" | "amber" | "red" | "gray"> = {
  low: "gray",
  medium: "blue",
  high: "amber",
  urgent: "red",
};

function fmt(dt: string | null): string {
  if (!dt) return "—";
  return new Date(dt).toLocaleString();
}

// Map raw status/priority/category values to i18n key suffixes.
const STATUS_KEY: Record<string, string> = {
  open: "Open",
  in_progress: "InProgress",
  resolved: "Resolved",
  closed: "Closed",
};
const PRIORITY_KEY: Record<string, string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
  urgent: "Urgent",
};
const CATEGORY_KEY: Record<string, string> = {
  connection: "Connection",
  license: "License",
  performance: "Performance",
  billing: "Billing",
  account: "Account",
  bug: "Bug",
  other: "Other",
};

export default function SupportPage() {
  const { t } = useLocale();
  const [view, setView] = useState<View>({ name: "list" });
  const [tickets, setTickets] = useState<ClientTicket[]>([]);
  const [total, setTotal] = useState(0);
  const [loadingList, setLoadingList] = useState(true);
  const [listError, setListError] = useState<string | null>(null);

  const loadList = useCallback(async () => {
    setLoadingList(true);
    setListError(null);
    try {
      const res = await listMyTickets();
      setTickets(res.tickets);
      setTotal(res.total);
    } catch (e) {
      setListError(e instanceof Error ? e.message : t("support.loadError"));
    } finally {
      setLoadingList(false);
    }
  }, [t]);

  useEffect(() => {
    loadList();
  }, [loadList]);

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title={t("support.title")}
        subtitle={t("support.subtitle")}
        actions={
          view.name !== "new" ? (
            <Button variant="primary" icon="plus" onClick={() => setView({ name: "new" })}>
              {t("support.newTicket")}
            </Button>
          ) : undefined
        }
      />

      {view.name === "new" && (
        <NewTicketForm
          onCreated={(ticket) => {
            loadList();
            setView({ name: "detail", ticketId: ticket.id });
          }}
          onCancel={() => setView({ name: "list" })}
        />
      )}

      {view.name === "detail" && (
        <TicketDetail
          ticketId={view.ticketId}
          onBack={() => setView({ name: "list" })}
          onReplied={() => loadList()}
        />
      )}

      {view.name === "list" && (
        <TicketList
          tickets={tickets}
          total={total}
          loading={loadingList}
          error={listError}
          onReload={loadList}
          onOpen={(ticket) => setView({ name: "detail", ticketId: ticket.id })}
          onNew={() => setView({ name: "new" })}
        />
      )}
    </div>
  );
}

/* ------------------------------- List ---------------------------------- */

function TicketList({
  tickets,
  total,
  loading,
  error,
  onReload,
  onOpen,
  onNew,
}: {
  tickets: ClientTicket[];
  total: number;
  loading: boolean;
  error: string | null;
  onReload: () => void;
  onOpen: (t: ClientTicket) => void;
  onNew: () => void;
}) {
  const { t } = useLocale();
  if (loading) {
    return (
      <Card>
        <div className="flex flex-col gap-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <EmptyState
          variant="gap"
          icon="alert-triangle"
          title={t("support.loadError")}
          description={error}
          action={<Button variant="secondary" icon="refresh" onClick={onReload}>{t("support.retry")}</Button>}
        />
      </Card>
    );
  }

  if (tickets.length === 0) {
    return (
      <Card>
        <EmptyState
          icon="lifebuoy"
          title={t("support.noTickets")}
          description={t("support.noTicketsDesc")}
          action={<Button variant="primary" icon="plus" onClick={onNew}>{t("support.createTicket")}</Button>}
        />
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-xs text-ink-muted">
        {total} {total === 1 ? t("support.statusOpen") : t("support.statusOpen")}
      </p>
      {tickets.map((ticket) => (
        <button
          key={ticket.id}
          onClick={() => onOpen(ticket)}
          className="text-left rounded-xl border border-line bg-surface hover:border-brand-500/40 transition-colors px-4 py-3.5 flex flex-col gap-2"
        >
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-semibold text-ink">{ticket.ticket_number}</span>
            <Badge tone={STATUS_TONE[ticket.status] || "gray"}>{t(`support.status${STATUS_KEY[ticket.status] || ticket.status}`)}</Badge>
            <Badge tone={PRIORITY_TONE[ticket.priority] || "gray"}>{t(`support.p${PRIORITY_KEY[ticket.priority] || ticket.priority}`)}</Badge>
            <Badge tone="gray">{t(`support.cat${CATEGORY_KEY[ticket.category] || ticket.category}`)}</Badge>
            {ticket.escalated && <Badge tone="red">{t("support.escalated")}</Badge>}
          </div>
          <div className="text-sm font-medium text-ink-soft truncate">{ticket.subject}</div>
          <div className="flex items-center justify-between gap-3">
            <span className="text-xs text-ink-muted">{fmt(ticket.created_at)}</span>
            <span className="inline-flex items-center gap-1 text-xs text-brand-400">
              {t("support.open")} <Icon name="arrow-right" className="h-3.5 w-3.5" />
            </span>
          </div>
        </button>
      ))}
    </div>
  );
}

/* ------------------------------- Detail -------------------------------- */

function TicketDetail({
  ticketId,
  onBack,
  onReplied,
}: {
  ticketId: string;
  onBack: () => void;
  onReplied: () => void;
}) {
  const { t } = useLocale();
  const [ticket, setTicket] = useState<ClientTicket | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reply, setReply] = useState("");
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getMyTicket(ticketId);
      setTicket(res.ticket);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("support.loadError"));
    } finally {
      setLoading(false);
    }
  }, [ticketId, t]);

  useEffect(() => {
    load();
  }, [load]);

  const sendReply = async () => {
    const text = reply.trim();
    if (!text) return;
    setSending(true);
    setSendError(null);
    try {
      const res = await replyToMyTicket(ticketId, text);
      setTicket(res.ticket);
      setReply("");
      onReplied();
    } catch (e) {
      setSendError(e instanceof Error ? e.message : t("support.sendFailed"));
    } finally {
      setSending(false);
    }
  };

  if (loading) {
    return (
      <Card>
        <Skeleton className="h-24 w-full mb-3" />
        <Skeleton className="h-40 w-full" />
      </Card>
    );
  }

  if (error || !ticket) {
    return (
      <Card>
        <EmptyState
          variant="gap"
          icon="alert-triangle"
          title={t("support.loadError")}
          description={error || t("support.loadError")}
          action={<Button variant="secondary" icon="arrow-left" onClick={onBack}>{t("support.backToTickets")}</Button>}
        />
      </Card>
    );
  }

  const closed = ticket.status === "closed";

  return (
    <div className="flex flex-col gap-5">
      <Button variant="ghost" icon="arrow-left" className="self-start" onClick={onBack}>
        {t("support.backToTickets")}
      </Button>

      <Card
        title={`${ticket.ticket_number} — ${ticket.subject}`}
        icon="lifebuoy"
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={STATUS_TONE[ticket.status] || "gray"}>{t(`support.status${STATUS_KEY[ticket.status] || ticket.status}`)}</Badge>
            <Badge tone={PRIORITY_TONE[ticket.priority] || "gray"}>{t(`support.p${PRIORITY_KEY[ticket.priority] || ticket.priority}`)}</Badge>
            <Badge tone="gray">{t(`support.cat${CATEGORY_KEY[ticket.category] || ticket.category}`)}</Badge>
            {ticket.escalated && <Badge tone="red">{t("support.escalated")}</Badge>}
          </div>
        }
      >
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
          <Meta label={t("support.colCreated")} value={fmt(ticket.created_at)} />
          <Meta label={t("support.colUpdated")} value={fmt(ticket.updated_at)} />
          <Meta label={t("support.colSource")} value={ticket.source} />
          <Meta label={t("support.colClosed")} value={fmt(ticket.closed_at)} />
        </div>
      </Card>

      <Card title={t("support.conversation")} icon="mail">
        <div className="flex flex-col gap-4">
          {ticket.messages.length === 0 && (
            <p className="text-sm text-ink-muted">{t("support.noMessages")}</p>
          )}
          {ticket.messages.map((m) => {
            const isStaff = m.author_role !== "client";
            return (
              <div
                key={m.id}
                className={`rounded-xl border px-4 py-3 ${
                  isStaff ? "border-tech-500/30 bg-tech-tint/40" : "border-line bg-surface"
                }`}
              >
                <div className="flex items-center justify-between gap-2 mb-1.5">
                  <span className="text-xs font-semibold text-ink-soft">
                    {m.author_name || (isStaff ? t("support.support") : t("support.you"))}
                  </span>
                  <span className="text-[11px] text-ink-muted">{fmt(m.created_at)}</span>
                </div>
                <p className="text-sm text-ink whitespace-pre-wrap">{m.body}</p>
              </div>
            );
          })}
        </div>

        {!closed && (
          <div className="mt-5 border-t border-line pt-4">
            <label htmlFor="reply" className="block text-xs font-medium text-ink-soft mb-1.5">
              {t("support.addReply")}
            </label>
            <textarea
              id="reply"
              value={reply}
              onChange={(e) => setReply(e.target.value)}
              rows={4}
              placeholder={t("support.replyPh")}
              className="w-full rounded-lg border border-line bg-surface px-3 py-2.5 text-sm text-ink placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-brand-500/40 resize-y"
            />
            {sendError && <p className="text-xs text-danger mt-2">{sendError}</p>}
            <div className="mt-3 flex justify-end">
              <Button
                variant="primary"
                icon="send"
                onClick={sendReply}
                disabled={!reply.trim() || sending}
              >
                {sending ? t("telegram.sending") : t("support.sendReply")}
              </Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-ink-muted mb-0.5">{label}</div>
      <div className="font-medium text-ink-soft">{value}</div>
    </div>
  );
}

/* ------------------------------ New Ticket ------------------------------ */

function NewTicketForm({
  onCreated,
  onCancel,
}: {
  onCreated: (t: ClientTicket) => void;
  onCancel: () => void;
}) {
  const { t } = useLocale();
  const [subject, setSubject] = useState("");
  const [category, setCategory] = useState<string>("connection");
  const [priority, setPriority] = useState<string>("medium");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const canSubmit = useMemo(
    () => subject.trim().length >= 3 && description.trim().length >= 10 && !submitting,
    [subject, description, submitting],
  );

  const submit = async () => {
    setError(null);
    setSubmitting(true);
    try {
      const res = await createMyTicket({
        subject: subject.trim(),
        description: description.trim(),
        category,
        priority,
      });
      onCreated(res.ticket);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("support.submitFailed"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card title={t("support.createTitle")} icon="plus">
      <div className="flex flex-col gap-4">
        <TextField
          label={t("support.subject")}
          placeholder={t("support.subjectPh")}
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
          maxLength={255}
          hint={`${subject.length}/255`}
        />
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <SelectField label={t("support.category")} value={category} onChange={(e) => setCategory(e.target.value)}>
            {TICKET_CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {t(`support.cat${CATEGORY_KEY[c] || c}`)}
              </option>
            ))}
          </SelectField>
          <SelectField label={t("support.priority")} value={priority} onChange={(e) => setPriority(e.target.value)}>
            <option value="low">{t("support.pLow")}</option>
            <option value="medium">{t("support.pMedium")}</option>
            <option value="high">{t("support.pHigh")}</option>
            <option value="urgent">{t("support.pUrgent")}</option>
          </SelectField>
        </div>
        <div>
          <label htmlFor="description" className="block text-xs font-medium text-ink-soft mb-1.5">
            {t("support.descLabel")}
          </label>
          <textarea
            id="description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={6}
            maxLength={5000}
            placeholder={t("support.descPh")}
            className="w-full rounded-lg border border-line bg-surface px-3 py-2.5 text-sm text-ink placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-brand-500/40 resize-y"
          />
          <p className="text-[11px] text-ink-muted mt-1">{t("support.descHint")} · {description.length}/5000</p>
        </div>
        {error && <p className="text-xs text-danger">{error}</p>}
        <div className="flex justify-end gap-2 border-t border-line pt-4">
          <Button variant="ghost" onClick={onCancel}>
            {t("support.cancel")}
          </Button>
          <Button variant="primary" icon="send" onClick={submit} disabled={!canSubmit}>
            {submitting ? t("telegram.sending") : t("support.submitTicket")}
          </Button>
        </div>
      </div>
    </Card>
  );
}
