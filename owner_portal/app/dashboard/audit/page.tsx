"use client";

import { Fragment, useEffect, useState, useCallback } from "react";
import OwnerPermissionGuard from "@/components/auth/owner_permission_guard";
import { listAuditLogs, getAuditSummary, AuditLogItem, AuditSummary } from "@/lib/api";
import { PageHeader, Card, Table, Td, Badge, Button, TextField, SelectField, Skeleton, EmptyState, type BadgeTone } from "@ds/components/ui";
import { Icon } from "@ds/components/Icon";

const SEVERITIES = ["info", "warning", "error", "critical"];

function severityTone(s: string): BadgeTone {
  if (s === "critical" || s === "error") return "red";
  if (s === "warning") return "amber";
  if (s === "info") return "blue";
  return "gray";
}

export default function AuditPage() {
  const [logs, setLogs] = useState<AuditLogItem[]>([]);
  const [summary, setSummary] = useState<AuditSummary | null>(null);
  const [error, setError] = useState("");
  const [severity, setSeverity] = useState("");
  const [search, setSearch] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [offset, setOffset] = useState(0);
  const [expandedLog, setExpandedLog] = useState<string | null>(null);

  const LIMIT = 30;

  const load = useCallback(async (sev: string, q: string, df: string, dt: string, off: number) => {
    const params = new URLSearchParams({ limit: String(LIMIT), offset: String(off) });
    if (sev) params.set("severity", sev);
    if (q) params.set("q", q);
    if (df) params.set("date_from", df);
    if (dt) params.set("date_to", dt);
    try {
      const [l, s] = await Promise.all([
        listAuditLogs(`?${params.toString()}`),
        off === 0 ? getAuditSummary() : Promise.resolve(null),
      ]);
      setLogs(l.items);
      if (s) setSummary(s);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => { load(severity, search, dateFrom, dateTo, offset); }, [load, severity, search, dateFrom, dateTo, offset]);

  const exportData = (format: "csv" | "json") => {
    const filename = `audit_logs_${new Date().toISOString().slice(0, 10)}`;
    if (format === "json") {
      const blob = new Blob([JSON.stringify({ logs, summary }, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a"); a.href = url; a.download = `${filename}.json`; a.click();
      URL.revokeObjectURL(url);
    } else {
      const headers = ["Time", "Action", "Severity", "Actor", "Target", "Result", "IP"];
      const rows = logs.map((l) => [
        l.timestamp || "", l.action, l.severity, l.actor || "", l.target || "", l.result || "", l.ip || "",
      ].map((v) => `"${v.replace(/"/g, '""')}"`).join(","));
      const csv = [headers.join(","), ...rows].join("\n");
      const blob = new Blob([csv], { type: "text/csv" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a"); a.href = url; a.download = `${filename}.csv`; a.click();
      URL.revokeObjectURL(url);
    }
  };

  const dateCls =
    "h-9 rounded-lg border border-line bg-input px-3 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500 transition-colors";

  return (
    <OwnerPermissionGuard permission="audit.read">
      <div className="flex flex-col gap-5 max-w-6xl">
        <PageHeader
          title="Audit Logs"
          subtitle="Global, filterable record of platform actions. Every mutation is audited server-side."
          actions={
            <>
              <Button size="sm" variant="secondary" icon="download" onClick={() => exportData("csv")}>
                CSV
              </Button>
              <Button size="sm" variant="secondary" icon="download" onClick={() => exportData("json")}>
                JSON
              </Button>
            </>
          }
        />

        {error && (
          <div className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
            {error}
          </div>
        )}

        {summary && (
          <div className="flex items-center gap-4 flex-wrap">
            <div className="text-xs text-ink-soft">
              Total: <span className="font-semibold text-ink">{summary.total}</span>
            </div>
            {Object.entries(summary.by_severity).map(([s, c]) => (
              <Badge key={s} tone={severityTone(s)}>
                {s}: {c}
              </Badge>
            ))}
          </div>
        )}

        <Card title="Filter" icon="filter" bodyClassName="flex flex-col sm:flex-row gap-3">
          <TextField
            icon="search"
            placeholder="Search actor, action, target..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setOffset(0); }}
            className="flex-1 min-w-[200px]"
          />
          <SelectField
            value={severity}
            onChange={(e) => { setSeverity(e.target.value); setOffset(0); }}
            className="w-44"
          >
            <option value="">All severities</option>
            {SEVERITIES.map((s) => (<option key={s} value={s}>{s}</option>))}
          </SelectField>
          <input type="date" value={dateFrom} onChange={(e) => { setDateFrom(e.target.value); setOffset(0); }} className={dateCls} />
          <input type="date" value={dateTo} onChange={(e) => { setDateTo(e.target.value); setOffset(0); }} className={dateCls} />
        </Card>

        <Card title="Log entries" icon="scroll" bodyClassName="p-0">
          {logs.length === 0 && !error ? (
            <EmptyState
              icon="scroll"
              title="No logs found"
              description={search || severity || dateFrom || dateTo ? "Try adjusting the filters." : "Audit entries will appear here as actions are performed."}
            />
          ) : (
            <Table columns={["Time", "Action", "Severity", "Actor", "Target", "Result", "IP"]}>
              {logs.map((log) => (
                <Fragment key={log.id}>
                  <tr
                    className="cursor-pointer hover:bg-hover transition-colors"
                    onClick={() => setExpandedLog(expandedLog === log.id ? null : log.id)}
                  >
                    <Td className="text-xs text-ink-muted whitespace-nowrap">
                      {log.timestamp ? new Date(log.timestamp).toLocaleString() : "—"}
                    </Td>
                    <Td mono className="text-xs">{log.action}</Td>
                    <Td>
                      <Badge tone={severityTone(log.severity)}>{log.severity}</Badge>
                    </Td>
                    <Td className="text-xs text-ink-soft">{log.actor || "—"}</Td>
                    <Td className="text-xs text-ink-soft truncate max-w-[150px]">{log.target || "—"}</Td>
                    <Td className="text-xs text-ink-soft">{log.result || "—"}</Td>
                    <Td className="text-xs text-ink-muted font-mono">{log.ip || "—"}</Td>
                  </tr>
                  {expandedLog === log.id && (
                    <tr className="bg-base">
                      <td colSpan={7} className="px-4 py-3">
                        <pre className="text-xs text-ink-muted font-mono whitespace-pre-wrap">
                          {JSON.stringify(log.details || {}, null, 2)}
                        </pre>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </Table>
          )}
        </Card>

        {logs.length > 0 && (
          <div className="flex items-center justify-between text-sm text-ink-soft">
            <span>Showing {offset + 1}–{offset + logs.length}</span>
            <div className="flex gap-2">
              <Button size="sm" variant="secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - LIMIT))}>
                Previous
              </Button>
              <Button size="sm" variant="secondary" disabled={logs.length < LIMIT} onClick={() => setOffset(offset + LIMIT)}>
                Next
              </Button>
            </div>
          </div>
        )}
      </div>
    </OwnerPermissionGuard>
  );
}
