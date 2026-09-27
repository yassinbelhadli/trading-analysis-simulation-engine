"use client";

import { useCallback, useEffect, useState, Fragment } from "react";
import OwnerPermissionGuard from "@/components/auth/owner_permission_guard";
import { listAuditLogs, type AuditLogItem } from "@/lib/api";
import {
  PageHeader,
  Card,
  Table,
  Td,
  Badge,
  Button,
  SelectField,
  Skeleton,
  EmptyState,
  type BadgeTone,
} from "@ds/components/ui";
import { Icon } from "@ds/components/Icon";

/**
 * Owner Alerts — real platform alert events sourced from the audit log
 * (risk stops, security events, license/trading anomalies). No separate
 * alert-rule engine is invented; the audit trail IS the event stream.
 */
const CATEGORIES: { value: string; label: string; pattern: string }[] = [
  { value: "security", label: "Security", pattern: "auth.|||access.denied|||license." },
  { value: "risk", label: "Risk", pattern: "risk." },
  { value: "trading", label: "Trading", pattern: "trade.|||paper_trade|||break_even|||partial_close|||SL_" },
  { value: "system", label: "System & Channels", pattern: "engine.|||system.|||telegram.|||email.|||subscription." },
];

const ALERT_PATTERNS: Record<string, string> = Object.fromEntries(
  CATEGORIES.map((c) => [c.value, c.pattern]),
);

function toneFor(sev: string): BadgeTone {
  const s = (sev || "").toUpperCase();
  if (s === "ERROR" || s === "CRITICAL") return "red";
  if (s === "WARNING" || s === "WARN") return "amber";
  return "blue";
}

export default function AlertsPage() {
  const [logs, setLogs] = useState<AuditLogItem[] | null>(null);
  const [error, setError] = useState("");
  const [category, setCategory] = useState("security");
  const [offset, setOffset] = useState(0);
  const [expanded, setExpanded] = useState<string | null>(null);

  const LIMIT = 30;

  const load = useCallback(async (cat: string, off: number) => {
    setError("");
    try {
      const pattern = ALERT_PATTERNS[cat] ?? "auth.";
      // Server `action` filter is a single ILIKE; for OR patterns fetch the
      // union by querying with each fragment sequentially is too chatty, so
      // request the primary fragment and filter the rest client-side.
      const primary = pattern.split("|||")[0];
      const res = await listAuditLogs(
        `?limit=${LIMIT}&offset=${off}&action=${encodeURIComponent(primary)}`,
      );
      const fragments = pattern.split("|||");
      const all = fragments.length > 1
        ? res.items.filter((l) => fragments.some((f) => l.action.toUpperCase().includes(f.toUpperCase())))
        : res.items;
      setLogs(all);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load alerts");
      setLogs([]);
    }
  }, []);

  useEffect(() => {
    setOffset(0);
    load(category, 0);
  }, [category, load]);

  const changeCategory = (v: string) => {
    setCategory(v);
    setOffset(0);
  };

  return (
    <OwnerPermissionGuard permission="audit.read">
      <div className="flex flex-col gap-5 max-w-6xl">
        <PageHeader
          title="Alerts"
          subtitle="Platform alert events: security anomalies, risk stops, trading and system channel events. Sourced from the server audit trail."
        />

        {error && (
          <div className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
            {error}
          </div>
        )}

        <div className="flex flex-wrap items-end gap-3">
          <SelectField label="Category" value={category} onChange={(e) => changeCategory(e.target.value)}>
            {CATEGORIES.map((c) => (
              <option key={c.value} value={c.value}>{c.label}</option>
            ))}
          </SelectField>
          <Button size="sm" variant="secondary" icon="refresh" onClick={() => load(category, offset)}>
            Refresh
          </Button>
        </div>

        <Card title={`${CATEGORIES.find((c) => c.value === category)?.label} events`} icon="bell" bodyClassName="p-0">
          {logs === null ? (
            <div className="p-4 flex flex-col gap-2">
              <Skeleton className="h-9 w-full" />
              <Skeleton className="h-9 w-full" />
              <Skeleton className="h-9 w-full" />
            </div>
          ) : logs.length === 0 ? (
            <div className="p-4">
              <EmptyState
                icon="bell"
                title="No matching events"
                description="Alert events in this category will appear here as they are audited."
              />
            </div>
          ) : (
            <Table columns={["Time", "Event", "Severity", "Actor", "Details"]}>
              {logs.map((l) => (
                <Fragment key={l.id}>
                  <tr
                    className="cursor-pointer hover:bg-hover transition-colors"
                    onClick={() => setExpanded(expanded === l.id ? null : l.id)}
                  >
                    <Td className="text-xs text-ink-muted whitespace-nowrap">
                      {l.timestamp ? new Date(l.timestamp).toLocaleString() : "—"}
                    </Td>
                    <Td mono className="text-xs">{l.action}</Td>
                    <Td>
                      <Badge tone={toneFor(l.severity)}>{l.severity}</Badge>
                    </Td>
                    <Td className="text-xs text-ink-soft">{l.actor || "—"}</Td>
                    <Td className="text-xs text-ink-soft truncate max-w-[220px]">
                      {l.details ? JSON.stringify(l.details).slice(0, 120) : "—"}
                    </Td>
                  </tr>
                  {expanded === l.id && (
                    <tr className="bg-base">
                      <td colSpan={5} className="px-4 py-3">
                        <pre className="text-xs text-ink-muted font-mono whitespace-pre-wrap">
                          {JSON.stringify(l.details || {}, null, 2)}
                        </pre>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </Table>
          )}
        </Card>

        {logs && logs.length > 0 && (
          <div className="flex items-center justify-between text-sm text-ink-soft">
            <span>Page {Math.floor(offset / LIMIT) + 1}</span>
            <div className="flex gap-2">
              <Button size="sm" variant="secondary" disabled={offset === 0} onClick={() => { setOffset(Math.max(0, offset - LIMIT)); load(category, Math.max(0, offset - LIMIT)); }}>
                Previous
              </Button>
              <Button size="sm" variant="secondary" disabled={logs.length < LIMIT} onClick={() => { setOffset(offset + LIMIT); load(category, offset + LIMIT); }}>
                Next
              </Button>
            </div>
          </div>
        )}

        <div className="rounded-xl border border-line bg-raised px-5 py-4 text-xs text-ink-muted">
          <div className="flex items-start gap-2">
            <Icon name="info" className="h-4 w-4 mt-0.5 shrink-0" />
            <p>
              High-impact economic events automatically pause trading 30 minutes before release
              (see Economic Calendar). Alert rules with custom channels are a future module; this
              page reflects the audited platform event stream today.
            </p>
          </div>
        </div>
      </div>
    </OwnerPermissionGuard>
  );
}
