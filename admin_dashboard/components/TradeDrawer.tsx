"use client";

import { useEffect } from "react";
import StatusBadge from "./StatusBadge";

interface TradeDetail {
  id: string;
  symbol: string;
  direction: string;
  entry_price: number | null;
  stop_loss: number | null;
  take_profit: number | null;
  risk_reward: number | null;
  lot_size: number | null;
  risk_percent: number | null;
  score: number | null;
  confidence: number | null;
  rank: string | null;
  status: string;
  reasons: string | null;
  session: string | null;
  market_regime: string | null;
  created_at: string | null;
  executed_at: string | null;
  exit_price: number | null;
  close_reason: string | null;
  closed_at: string | null;
  realized_r: number | null;
  trade_duration_sec: number | null;
  mfe: number | null;
  mae: number | null;
  breakeven_activated: boolean;
  partial_closed: boolean;
}

interface Props {
  trade: TradeDetail | null;
  onClose: () => void;
}

const ICT_REASONS = ["BOS", "CHoCH", "MSS", "Sweep", "FVG", "OB", "VI", "LV", "PD", "SR", "Candle"];

export default function TradeDrawer({ trade, onClose }: Props) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    if (trade) document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [trade, onClose]);

  if (!trade) return null;

  const reasons = (trade.reasons || "").split(",").map((r) => r.trim()).filter(Boolean);

  return (
    <div className="fixed inset-0 z-50 flex justify-end" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="w-full max-w-lg bg-raised border-l border-line h-full overflow-y-auto shadow-2xl">
        <div className="flex items-center justify-between px-4 py-3 border-b border-line">
          <h2 className="text-sm font-semibold text-ink">{trade.symbol || "Trade"} <span className={trade.direction === "BUY" ? "text-ok" : "text-danger"}>{trade.direction}</span></h2>
          <button onClick={onClose} className="text-ink-muted hover:text-ink text-lg">&times;</button>
        </div>

        <div className="p-4 space-y-4 text-sm">
          {/* Status */}
          <div className="flex items-center gap-2"><StatusBadge status={trade.status} /> {trade.status}</div>

          {/* Price Levels */}
          <div className="grid grid-cols-3 gap-3 bg-input rounded-lg p-3">
            <div className="text-center">
              <div className="text-[10px] text-ink-muted">Stop Loss</div>
              <div className="font-mono text-danger text-xs">{trade.stop_loss || "—"}</div>
            </div>
            <div className="text-center">
              <div className="text-[10px] text-ink-muted">Entry</div>
              <div className="font-mono font-semibold text-xs text-ink">{trade.entry_price || "—"}</div>
            </div>
            <div className="text-center">
              <div className="text-[10px] text-ink-muted">Take Profit</div>
              <div className="font-mono text-ok text-xs">{trade.take_profit || "—"}</div>
            </div>
          </div>

          {/* Trade Info */}
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div><span className="text-ink-muted">Lot:</span> {trade.lot_size || "—"}</div>
            <div><span className="text-ink-muted">Risk %:</span> {trade.risk_percent != null ? `${trade.risk_percent}%` : "—"}</div>
            <div><span className="text-ink-muted">RR:</span> {trade.risk_reward || "—"}</div>
            <div><span className="text-ink-muted">Score:</span> {trade.score || "—"}</div>
            <div><span className="text-ink-muted">Confidence:</span> {trade.confidence || "—"}</div>
            <div><span className="text-ink-muted">Rank:</span> {trade.rank || "—"}</div>
            <div><span className="text-ink-muted">Session:</span> {trade.session || "—"}</div>
            <div><span className="text-ink-muted">Regime:</span> {trade.market_regime || "—"}</div>
          </div>

          {/* P&L */}
          {trade.realized_r != null && (
            <div className="bg-input rounded-lg p-3">
              <div className="text-[10px] text-ink-muted">Realized P&L (R)</div>
              <div className={`text-lg font-bold font-mono ${trade.realized_r > 0 ? "text-ok" : "text-danger"}`}>
                {trade.realized_r > 0 ? "+" : ""}{trade.realized_r.toFixed(2)}R
              </div>
            </div>
          )}

          {/* ICT Score Breakdown */}
          <div>
            <div className="text-xs font-semibold text-ink-muted uppercase mb-2">ICT Checklist</div>
            <div className="flex flex-wrap gap-1.5">
              {ICT_REASONS.map((r) => {
                const checked = reasons.includes(r);
                return (
                  <span key={r} className={`text-[10px] px-2 py-0.5 rounded-full border flex items-center gap-1 ${
                    checked
                      ? "bg-ok/10 border-ok/30 text-ok"
                      : "bg-input border-line text-ink-muted"
                  }`}>
                    <span>{checked ? "✓" : "○"}</span> {r}
                  </span>
                );
              })}
            </div>
          </div>

          {/* MFE / MAE */}
          {trade.mfe != null && (
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="bg-input rounded p-2">
                <div className="text-ink-muted">MFE</div>
                  <div className="text-ok font-mono">{(trade.mfe ?? 0).toFixed(2)}</div>
              </div>
              <div className="bg-input rounded p-2">
                <div className="text-ink-muted">MAE</div>
                <div className="text-danger font-mono">{(trade.mae ?? 0).toFixed(2)}</div>
              </div>
            </div>
          )}

          {/* Close Info */}
          {trade.close_reason && (
            <div className="bg-input rounded-lg p-3 text-xs">
              <div className="flex justify-between">
                <span>Exit: <span className="font-mono">{trade.exit_price || "—"}</span></span>
                <span>Reason: <span className="font-semibold">{trade.close_reason}</span></span>
              </div>
              {trade.trade_duration_sec != null && (
                <div className="mt-1">Duration: {Math.floor(trade.trade_duration_sec / 60)}m {trade.trade_duration_sec % 60}s</div>
              )}
            </div>
          )}

          {/* Lifecycle */}
          <div className="flex gap-2 text-[10px]">
            {trade.breakeven_activated && <span className="bg-tech-tint border border-tech-500/30 text-tech-400 px-2 py-0.5 rounded">Breakeven</span>}
            {trade.partial_closed && <span className="bg-warn/10 border border-warn/30 text-warn px-2 py-0.5 rounded">Partial Close</span>}
          </div>

          {/* Times */}
          <div className="text-[10px] text-ink-muted">
            {trade.created_at && <div>Opened: {new Date(trade.created_at).toLocaleString()}</div>}
            {trade.executed_at && <div>Executed: {new Date(trade.executed_at).toLocaleString()}</div>}
            {trade.closed_at && <div>Closed: {new Date(trade.closed_at).toLocaleString()}</div>}
          </div>

          {/* Replay Link */}
          <div className="mt-3 pt-3 border-t border-line">
            <a
              href={`/dashboard/trading/replay/${trade.id}`}
              className="text-sm text-brand-400 hover:underline flex items-center gap-1"
              onClick={(e) => { e.stopPropagation(); }}
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              Open Replay
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
