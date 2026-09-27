"use client";

import { useEffect, useState, useCallback } from "react";
import StatusBadge from "@/components/StatusBadge";
import PermissionGuard from "@/components/auth/permission_guard";
import { listAuditLogs, getAuditSummary, AuditLogItem, AuditSummary } from "@/lib/api";
import { Button, Card, PageHeader, SelectField, Table, Td, TextField } from "@ds/components/ui";

const SEVERITIES = ["info", "warning", "error", "critical"];

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

  return (
    <PermissionGuard permission="audit.read">
      <div>
        <PageHeader
          title="Audit Logs"
          subtitle="Security and activity trail"
          actions={
            <>
              <Button variant="ghost" size="sm" onClick={() => exportData("csv")}>CSV</Button>
              <Button variant="ghost" size="sm" onClick={() => exportData("json")}>JSON</Button>
            </>
          }
        />

        {error && <div className="text-danger text-sm mb-3">{error}</div>}

        {summary && (
          <div className="flex gap-4 mb-4 flex-wrap text-ink-soft text-xs">
            <div>
              Total: <span className="text-ink font-semibold">{summary.total}</span>
            </div>
            {Object.entries(summary.by_severity).map(([s, c]) => (
              <div key={s}>
                {s}:{" "}
                <span className={`font-semibold ${s === "critical" || s === "error" ? "text-danger" : s === "warning" ? "text-warn" : "text-ink"}`}>{c}</span>
              </div>
            ))}
          </div>
        )}

        <div className="flex gap-3 mb-4 flex-wrap">
          <TextField
            icon="search"
            placeholder="Search actor, action, target..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setOffset(0); }}
            className="flex-1 min-w-[220px]"
          />
          <SelectField value={severity} onChange={(e) => { setSeverity(e.target.value); setOffset(0); }}>
            <option value="">All severities</option>
            {SEVERITIES.map((s) => (<option key={s} value={s}>{s}</option>))}
          </SelectField>
          <TextField type="date" value={dateFrom} onChange={(e) => { setDateFrom(e.target.value); setOffset(0); }} />
          <TextField type="date" value={dateTo} onChange={(e) => { setDateTo(e.target.value); setOffset(0); }} />
        </div>

        <Card bodyClassName="p-0">
          <Table columns={["Time", "Action", "Severity", "Actor", "Target", "Result", "IP"]}>
            {logs.length === 0 && (
              <tr>
                <td colSpan={7} className="text-center py-8 text-ink-muted px-4">No logs found</td>
              </tr>
            )}
            {logs.map((log) => (
              <tr key={log.id} className="cursor-pointer"
                onClick={() => setExpandedLog(expandedLog === log.id ? null : log.id)}>
                <Td className="text-ink-muted text-xs">
                  {log.timestamp ? new Date(log.timestamp).toLocaleString() : "—"}
                </Td>
                <Td mono>{log.action}</Td>
                <Td><StatusBadge status={log.severity} /></Td>
                <Td>{log.actor || "—"}</Td>
                <Td className="truncate max-w-[150px]">{log.target || "—"}</Td>
                <Td>{log.result || "—"}</Td>
                <Td mono className="text-ink-muted">{log.ip || "—"}</Td>
              </tr>
            ))}
            {expandedLog && logs.find(l => l.id === expandedLog) && (
              <tr className="bg-raise">
                <td colSpan={7} className="px-4 py-3">
                  <pre className="text-xs text-ink-muted font-mono whitespace-pre-wrap">
                    {JSON.stringify(logs.find(l => l.id === expandedLog)?.details || {}, null, 2)}
                  </pre>
                </td>
              </tr>
            )}
          </Table>
        </Card>

        {logs.length > 0 && (
          <div className="flex items-center justify-between mt-4 text-sm text-ink-muted">
            <span>Showing {offset + 1}–{offset + logs.length}</span>
            <div className="flex gap-2">
              <Button variant="secondary" size="sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - LIMIT))}>Previous</Button>
              <Button variant="secondary" size="sm" disabled={logs.length < LIMIT} onClick={() => setOffset(offset + LIMIT)}>Next</Button>
            </div>
          </div>
        )}
      </div>
    </PermissionGuard>
  );
}
