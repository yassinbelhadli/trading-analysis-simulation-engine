"use client";

import { useEffect, useRef, useState } from "react";
import {
  createChart,
  ColorType,
  CandlestickSeries,
  LineSeries,
  IChartApi,
  ISeriesApi,
} from "lightweight-charts";

interface SnapshotData {
  trade: any;
  snapshot: any;
  screenshots: Record<string, string>;
}

interface Props {
  data: SnapshotData;
}

function val(v: any): number | undefined {
  if (v === null || v === undefined) return undefined;
  const n = Number(v);
  return isNaN(n) ? undefined : n;
}

export default function TradeReplay({ data }: Props) {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartApiRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const [activeTab, setActiveTab] = useState<"chart" | "entry" | "exit">("entry");

  const { trade, snapshot, screenshots } = data;
  const ohlc = snapshot?.chart?.ohlc ?? [];
  const drawing = snapshot?.drawing ?? {};
  const scoring = snapshot?.scoring ?? {};
  const struct = snapshot?.structure ?? {};
  const liq = snapshot?.liquidity ?? {};
  const obs = snapshot?.order_blocks ?? [];
  const fvgs = snapshot?.fvg ?? [];
  const sess = snapshot?.session ?? {};

  useEffect(() => {
    if (!chartRef.current || ohlc.length === 0) return;

    const chart = createChart(chartRef.current, {
      height: 520,
      layout: {
        background: { type: ColorType.Solid, color: "#1a1a2e" },
        textColor: "#9ca3af",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "#2d2d44" },
        horzLines: { color: "#2d2d44" },
      },
      timeScale: {
        borderColor: "#374151",
        timeVisible: true,
        secondsVisible: false,
      },
      rightPriceScale: {
        borderColor: "#374151",
      },
      crosshair: {
        vertLine: { color: "#6b7280", style: 2, width: 1 },
        horzLine: { color: "#6b7280", style: 2, width: 1 },
      },
    });

    // Candlestick series
    const candles = chart.addSeries(CandlestickSeries, {
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderDownColor: "#ef4444",
      borderUpColor: "#22c55e",
      wickDownColor: "#ef4444",
      wickUpColor: "#22c55e",
    });

    const candleData = ohlc.map((c: any) => ({
      time: c.time as any,
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    }));
    candles.setData(candleData);
    candleSeriesRef.current = candles;

    // Entry line
    const entryPrice = val(drawing?.entry?.price);
    if (entryPrice !== undefined) {
      const entryLine = chart.addSeries(LineSeries, {
        color: "#3b82f6",
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: true,
        title: "Entry",
      });
      entryLine.setData(
        ohlc.map((c: any) => ({ time: c.time as any, value: entryPrice! }))
      );
    }

    // SL line
    const slPrice = val(drawing?.sl);
    if (slPrice !== undefined) {
      const slLine = chart.addSeries(LineSeries, {
        color: "#ef4444",
        lineWidth: 2,
        lineStyle: 2,
        priceLineVisible: false,
        lastValueVisible: true,
        title: "SL",
      });
      slLine.setData(
        ohlc.map((c: any) => ({ time: c.time as any, value: slPrice! }))
      );
    }

    // TP lines
    const tpPrices: number[] = (drawing?.tp ?? []).map(val).filter((v: any) => v !== undefined);
    tpPrices.forEach((tp, i) => {
      const tpLine = chart.addSeries(LineSeries, {
        color: "#22c55e",
        lineWidth: 2,
        lineStyle: 2,
        priceLineVisible: false,
        lastValueVisible: true,
        title: `TP${i + 1}`,
      });
      tpLine.setData(
        ohlc.map((c: any) => ({ time: c.time as any, value: tp }))
      );
    });

    // Exit line
    const exitPrice = val(drawing?.exit_price);
    if (exitPrice !== undefined) {
      const exitLine = chart.addSeries(LineSeries, {
        color: "#f59e0b",
        lineWidth: 2,
        lineStyle: 2,
        priceLineVisible: false,
        lastValueVisible: true,
        title: "Exit",
      });
      exitLine.setData(
        ohlc.map((c: any) => ({ time: c.time as any, value: exitPrice }))
      );
    }

    chart.timeScale().fitContent();
    chartApiRef.current = chart;

    return () => chart.remove();
  }, [ohlc, drawing]);

  const indicatorColors: Record<string, string> = {
    atr: "#f59e0b",
    ema20: "#3b82f6",
    ema50: "#8b5cf6",
  };

  return (
    <div className="space-y-4">
      {/* Tabs */}
      <div className="flex gap-2 border-b border-line pb-2">
        <button
          onClick={() => setActiveTab("entry")}
          className={`px-4 py-1.5 text-sm rounded-t ${
            activeTab === "entry" ? "bg-raised text-brand-400 font-semibold" : "text-ink-muted"
          }`}
        >
          Entry
        </button>
        <button
          onClick={() => setActiveTab("exit")}
          className={`px-4 py-1.5 text-sm rounded-t ${
            activeTab === "exit" ? "bg-raised text-brand-400 font-semibold" : "text-ink-muted"
          }`}
        >
          Exit
        </button>
        <button
          onClick={() => setActiveTab("chart")}
          className={`px-4 py-1.5 text-sm rounded-t ${
            activeTab === "chart" ? "bg-raised text-brand-400 font-semibold" : "text-ink-muted"
          }`}
        >
          Interactive Chart
        </button>
      </div>

      {/* Entry / Exit Screenshot */}
      {activeTab !== "chart" && (
        <div className="bg-raised border border-line rounded-lg overflow-hidden">
          {screenshots[activeTab] ? (
            <img
              src={screenshots[activeTab]}
              alt={`${activeTab} chart`}
              className="w-full h-auto"
            />
          ) : (
            <div className="p-8 text-center text-ink-muted">
              No {activeTab} screenshot available
            </div>
          )}
        </div>
      )}

      {/* Interactive Chart */}
      {activeTab === "chart" && (
        <div className="bg-raised border border-line rounded-lg p-3">
          {ohlc.length > 0 ? (
            <div ref={chartRef} />
          ) : (
            <div className="p-8 text-center text-ink-muted">
              No OHLC data in snapshot
            </div>
          )}
        </div>
      )}

      {/* Trade Info Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Trade Details */}
        <div className="bg-raised border border-line rounded-lg p-4">
          <h3 className="text-xs font-semibold text-ink-muted uppercase mb-3">Trade Details</h3>
          <div className="space-y-2 text-sm">
            <Row label="Symbol" value={`${trade.direction} ${trade.symbol}`} />
            <Row label="Status" value={trade.status} />
            <Row label="Score" value={`${trade.score ?? "—"}%`} />
            <Row label="Confidence" value={`${trade.confidence ?? "—"}%`} />
            <Row label="Entry" value={trade.entry_price?.toFixed(2)} />
            <Row label="SL" value={trade.stop_loss?.toFixed(2)} />
            <Row label="TP" value={trade.take_profit?.toFixed(2)} />
            <Row label="Session" value={trade.session ?? "—"} />
            <Row label="RR" value={trade.risk_reward?.toFixed(1)} />
          </div>
        </div>

        {/* ICT Confluence */}
        <div className="bg-raised border border-line rounded-lg p-4">
          <h3 className="text-xs font-semibold text-ink-muted uppercase mb-3">ICT Confluence</h3>
          <div className="space-y-2 text-sm">
            <Row label="BOS" value={struct.bos_detected ? "✓" : "—"} ok={struct.bos_detected} />
            <Row label="CHoCH" value={struct.choch_detected ? "✓" : "—"} ok={struct.choch_detected} />
            <Row label="MSS" value={struct.mss_detected ? "✓" : "—"} ok={struct.mss_detected} />
            <Row label="Sweep" value={liq.sweep_detected ? liq.sweep_type || "✓" : "—"} ok={liq.sweep_detected} />
            <Row label="EQH" value={liq.equal_highs ? "✓" : "—"} ok={liq.equal_highs} />
            <Row label="EQL" value={liq.equal_lows ? "✓" : "—"} ok={liq.equal_lows} />
            <Row label="PDH Swept" value={liq.pdh_swept ? "✓" : "—"} ok={liq.pdh_swept} />
            <Row label="PDL Swept" value={liq.pdl_swept ? "✓" : "—"} ok={liq.pdl_swept} />
            <Row label="OB" value={obs.length > 0 ? obs[0]?.type || "✓" : "—"} ok={obs.length > 0} />
            <Row label="FVG" value={fvgs.length > 0 ? fvgs[0]?.type || "✓" : "—"} ok={fvgs.length > 0} />
          </div>
        </div>

        {/* Session / Market */}
        <div className="bg-raised border border-line rounded-lg p-4">
          <h3 className="text-xs font-semibold text-ink-muted uppercase mb-3">Market Context</h3>
          <div className="space-y-2 text-sm">
            <Row label="Session" value={sess.label || "—"} />
            <Row label="Killzone" value={sess.is_kill_zone ? sess.kill_zones_active?.join(", ") || "✓" : "—"} ok={sess.is_kill_zone} />
            <Row label="Trend" value={struct.trend || "—"} />
            <Row label="PD Zone" value={snapshot?.premium_discount?.zone || "—"} />
            <Row label="PDH" value={sess.pdh?.toFixed(2)} />
            <Row label="PDL" value={sess.pdl?.toFixed(2)} />
            <Row label="Asian High" value={sess.asian_high?.toFixed(2)} />
            <Row label="Asian Low" value={sess.asian_low?.toFixed(2)} />
          </div>
        </div>
      </div>

      {/* Reasons */}
      {scoring.reasons?.length > 0 && (
        <div className="bg-raised border border-line rounded-lg p-4">
          <h3 className="text-xs font-semibold text-ink-muted uppercase mb-3">Setup Reasons</h3>
          <div className="flex flex-wrap gap-2">
            {scoring.reasons.map((r: string, i: number) => (
              <span key={i} className="px-2 py-1 text-xs rounded bg-brand-tint text-brand-400 border border-brand-500/30">
                {r}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Score Breakdown */}
      {snapshot?.scoring?.breakdown && Object.keys(snapshot.scoring.breakdown).length > 0 && (
        <div className="bg-raised border border-line rounded-lg p-4">
          <h3 className="text-xs font-semibold text-ink-muted uppercase mb-3">Score Breakdown</h3>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
            {Object.entries(snapshot.scoring.breakdown).map(([k, v]) => (
              <div key={k} className="flex justify-between px-3 py-1.5 text-sm rounded bg-input">
                <span className="text-ink-muted">{k.replace(/_/g, " ")}</span>
                <span className="font-mono font-semibold text-ink">{String(v)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Indicators */}
      {snapshot?.chart?.indicators && Object.keys(snapshot.chart.indicators).length > 0 && (
        <div className="bg-raised border border-line rounded-lg p-4">
          <h3 className="text-xs font-semibold text-ink-muted uppercase mb-3">Indicators at Entry</h3>
          <div className="space-y-2 text-sm">
            {Object.entries(snapshot.chart.indicators).map(([name, values]: [string, any]) => {
              const last = Array.isArray(values) ? values[values.length - 1] : null;
              if (!last) return null;
              return (
                <Row
                  key={name}
                  label={name.toUpperCase()}
                  value={last.value?.toFixed(2)}
                />
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

function Row({ label, value, ok }: { label: string; value: string | number | undefined | null; ok?: boolean }) {
  const color = ok === undefined ? "" : ok ? "text-ok" : "text-ink-muted";
  return (
    <div className="flex justify-between">
      <span className="text-ink-muted">{label}</span>
      <span className={`font-mono font-semibold text-ink ${color}`}>{value ?? "—"}</span>
    </div>
  );
}
