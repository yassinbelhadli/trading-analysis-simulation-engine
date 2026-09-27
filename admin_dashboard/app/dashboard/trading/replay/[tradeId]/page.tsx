"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { getTradeSnapshot } from "@/lib/api";
import TradeReplay from "@/components/TradeReplay";
import PermissionGuard from "@/components/auth/permission_guard";

export default function ReplayPage() {
  const params = useParams();
  const tradeId = params?.tradeId as string;
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!tradeId) return;
    setLoading(true);
    getTradeSnapshot(tradeId)
      .then(setData)
      .catch((e) => setError(e.message || "Failed to load trade"))
      .finally(() => setLoading(false));
  }, [tradeId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-ink-muted">Loading trade replay...</div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="p-6">
        <div className="bg-danger/10 border border-danger/40 rounded-lg p-4 text-danger">
          {error || "Trade not found"}
        </div>
        <Link href="/dashboard/trading/history" className="text-sm text-brand-400 hover:underline mt-4 inline-block">
          Back to Trade History
        </Link>
      </div>
    );
  }

  return (
    <PermissionGuard permission="trades.view">
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center gap-4">
          <Link
            href="/dashboard/trading/history"
            className="text-sm text-ink-muted hover:text-brand-400"
          >
            Back to History
          </Link>
          <div>
            <h1 className="text-xl font-bold text-ink">
              Trade Replay — {data.trade.direction} {data.trade.symbol}
            </h1>
            <p className="text-xs text-ink-muted mt-1">
              ID: {tradeId} · {data.trade.status}
              {data.trade.closed_at && ` · Closed ${new Date(data.trade.closed_at).toLocaleString()}`}
            </p>
          </div>
        </div>

        <TradeReplay data={data} />
      </div>
    </PermissionGuard>
  );
}
