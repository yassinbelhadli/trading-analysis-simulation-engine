"use client";

import { useEffect, useState } from "react";
import { getClientTrades, type ClientTrade } from "@/lib/api";
import { PageHeader, Card, Badge, EmptyState, Table, Td, SelectField, Skeleton } from "@ds/components/ui";
import { Icon } from "@ds/components/Icon";
import { useLocale } from "@/components/LocaleContext";

const FILTERS = ["all", "open", "closed"] as const;

export default function ActivityPage() {
  const { t } = useLocale();
  const [trades, setTrades] = useState<ClientTrade[]>([]);
  const [total, setTotal] = useState(0);
  const [filter, setFilter] = useState<string>("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    setLoading(true);
    getClientTrades(`?status=${filter}&limit=100`)
      .then((r) => { setTrades(r.items); setTotal(r.total); })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [filter]);

  if (loading && trades.length === 0) {
    return (
      <div className="flex flex-col gap-5">
        <div className="h-8 w-56 rounded bg-hover animate-pulse" />
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }
  if (error) {
    return <EmptyState icon="alert-triangle" title={t("activity.loadError")} description={error} />;
  }

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title={t("activity.title")}
        subtitle={t("activity.subtitle", { total, s: total === 1 ? "" : "s" })}
        actions={
          <div className="w-40">
            <SelectField
              aria-label={t("activity.filterLabel")}
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            >
              <option value="all">{t("activity.all")}</option>
              <option value="open">{t("activity.open")}</option>
              <option value="closed">{t("activity.closed")}</option>
            </SelectField>
          </div>
        }
      />

      <Card>
        {trades.length === 0 ? (
          <EmptyState
            icon="activity"
            title={filter === "all" ? t("activity.noTradesAll") : t("activity.noTradesFilter", { filter })}
            description={t("activity.noTradesDesc")}
          />
        ) : (
          <Table
            columns={[t("activity.colSymbol"), t("activity.colDirection"), t("activity.colStatus"), t("activity.colEntry"), t("activity.colSl"), t("activity.colTp"), t("activity.colPnl"), t("activity.colR"), t("activity.colDate")]}
          >
            {trades.map((t) => (
              <tr key={t.id}>
                <Td mono className="font-medium">{t.symbol}</Td>
                <Td>
                  <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium ${
                    t.direction === "BUY"
                      ? "bg-brand-tint text-brand-400"
                      : "bg-danger/10 text-danger"
                  }`}>
                    <Icon name={t.direction === "BUY" ? "trending-up" : "trending-down"} className="h-3 w-3" />
                    {t.direction}
                  </span>
                </Td>
                <Td>
                  <Badge tone={t.status === "CLOSED" ? "green" : t.status === "FILLED" ? "amber" : "gray"}>
                    {t.status}
                  </Badge>
                </Td>
                <Td mono className="text-right text-ink-soft">{t.entry_price?.toFixed(2) ?? "—"}</Td>
                <Td mono className="text-right text-ink-soft">{t.stop_loss?.toFixed(2) ?? "—"}</Td>
                <Td mono className="text-right text-ink-soft">{t.take_profit?.toFixed(2) ?? "—"}</Td>
                <Td mono className={`text-right font-medium ${(t.realized_pnl ?? 0) >= 0 ? "text-ok" : "text-danger"}`}>
                  {t.realized_pnl != null ? `${t.realized_pnl >= 0 ? "+" : ""}$${t.realized_pnl.toFixed(2)}` : "—"}
                </Td>
                <Td mono className={`text-right ${(t.realized_r ?? 0) >= 0 ? "text-ok" : "text-danger"}`}>
                  {t.realized_r != null ? `${t.realized_r >= 0 ? "+" : ""}${t.realized_r.toFixed(2)}R` : "—"}
                </Td>
                <Td className="text-right text-ink-muted">
                  {t.closed_at ? new Date(t.closed_at).toLocaleDateString() : (t.created_at ? new Date(t.created_at).toLocaleDateString() : "—")}
                </Td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
    </div>
  );
}
