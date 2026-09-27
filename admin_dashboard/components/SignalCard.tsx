"use client";

import StatusBadge from "./StatusBadge";

interface SignalProps {
  signal: any;
  onSelect?: (id: string) => void;
  selected?: boolean;
}

const ICT_ITEMS = ["BOS", "CHoCH", "MSS", "Sweep", "FVG", "OB", "VI", "LV", "PD", "SR", "Candle"];

function ScoreGauge({ score }: { score: number | null }) {
  const val = Math.min(Math.max(score || 0, 0), 100);
  const color = val >= 80 ? "#22c55e" : val >= 60 ? "#eab308" : val >= 40 ? "#f97316" : "#ef4444";
  return (
    <div className="flex items-center gap-2">
      <div className="w-full bg-input rounded-full h-2">
        <div className="h-2 rounded-full transition-all" style={{ width: `${val}%`, backgroundColor: color }} />
      </div>
      <span className="text-xs font-mono font-bold" style={{ color }}>{val}</span>
    </div>
  );
}

export default function SignalCard({ signal, onSelect, selected }: SignalProps) {
  if (!signal) return null;
  const reasons = (signal.reasons || "").split(",").map((r: string) => r.trim()).filter(Boolean);

  return (
    <div
      className={`bg-raised border rounded-lg p-3 cursor-pointer transition-all ${
        selected ? "border-brand-500 ring-1 ring-brand-500/40" : "border-line hover:border-brand-500"
      }`}
      onClick={() => onSelect?.(signal.id)}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div>
          <span className="font-mono font-bold text-sm text-ink">{signal.symbol || "—"}</span>
          <span className={`ml-2 text-xs font-semibold ${signal.direction === "BUY" ? "text-ok" : "text-danger"}`}>
            {signal.direction}
          </span>
        </div>
        <StatusBadge status={signal.status} />
      </div>

      {/* Score Gauge */}
      <div className="mb-2">
        <div className="text-[10px] text-ink-muted mb-0.5">Setup Score</div>
        <ScoreGauge score={signal.score} />
      </div>

      {/* Price Levels */}
      <div className="grid grid-cols-3 gap-1 text-[10px] font-mono mb-2">
        <div className="text-center bg-input rounded p-1">
          <div className="text-danger">SL</div>
          <div>{signal.stop_loss || "—"}</div>
        </div>
        <div className="text-center bg-input rounded p-1">
          <div className="text-ink-muted">Entry</div>
          <div>{signal.entry_price || "—"}</div>
        </div>
        <div className="text-center bg-input rounded p-1">
          <div className="text-ok">TP</div>
          <div>{signal.take_profit || "—"}</div>
        </div>
      </div>

      {/* Key Info */}
      <div className="flex flex-wrap gap-x-3 gap-y-1 text-[10px] text-ink-muted mb-2">
        <span>Lot: {signal.lot_size || "—"}</span>
        <span>Risk: {signal.risk_percent != null ? `${signal.risk_percent}%` : "—"}</span>
        <span>RR: {signal.risk_reward || "—"}</span>
        <span>Conf: {signal.confidence || "—"}</span>
        <span>Rank: {signal.rank || "—"}</span>
        <span>Session: {signal.session || "—"}</span>
      </div>

      {/* ICT Checklist */}
      <div className="flex flex-wrap gap-1">
        {ICT_ITEMS.map((item) => {
          const checked = reasons.includes(item);
          return (
            <span key={item} className={`text-[9px] px-1.5 py-0.5 rounded-full border ${
              checked
                ? "bg-ok/10 border-ok/30 text-ok"
                : "bg-input border-line text-ink-muted"
            }`}>
              {checked ? "✓" : "○"} {item}
            </span>
          );
        })}
      </div>
    </div>
  );
}
