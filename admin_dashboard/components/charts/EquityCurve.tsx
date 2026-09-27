"use client";

import { useEffect, useRef } from "react";
import { createChart, ColorType, LineSeries, IChartApi } from "lightweight-charts";

interface DataPoint {
  time: string;
  value: number;
}

interface Props {
  data: DataPoint[];
  color?: string;
  label?: string;
  height?: number;
}

export default function EquityCurve({ data, color = "#22c55e", label, height = 200 }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      height,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#6b7280",
        fontSize: 10,
      },
      grid: {
        vertLines: { color: "#1f2937" },
        horzLines: { color: "#1f2937" },
      },
      timeScale: {
        borderColor: "#374151",
        timeVisible: false,
      },
      rightPriceScale: {
        borderColor: "#374151",
      },
      crosshair: {
        vertLine: { color: "#6b7280", style: 2, width: 1 },
        horzLine: { color: "#6b7280", style: 2, width: 1 },
      },
      handleScroll: false,
      handleScale: false,
    });

    const line = chart.addSeries(LineSeries, {
      color,
      lineWidth: 2,
      crosshairMarkerVisible: true,
      crosshairMarkerRadius: 3,
      priceFormat: { type: "price", minMove: 0.01 },
      lastValueVisible: true,
      priceLineVisible: false,
    });

    const formatted = data.map((d) => ({
      time: d.time as any,
      value: d.value,
    }));
    line.setData(formatted);
    chart.timeScale().fitContent();
    chartRef.current = chart;

    return () => chart.remove();
  }, [data, color, height]);

  return (
    <div className="bg-raised border border-line rounded-lg p-3">
      {label && <div className="text-xs font-semibold text-ink-muted uppercase mb-2">{label}</div>}
      <div ref={containerRef} />
    </div>
  );
}
