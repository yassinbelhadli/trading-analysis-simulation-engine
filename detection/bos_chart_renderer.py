"""BOS validation chart renderer — full visual annotations on OHLC."""
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np

logger = logging.getLogger(__name__)


def _to_idx(candle_time):
    return mdates.date2num(datetime.utcfromtimestamp(candle_time))


def render_bos_chart(bos_event: Dict, candles: List[Dict],
                     output_path: str, window: int = 80):
    """Render an OHLC chart with full BOS annotations.

    Displays:
      - Candlestick chart (window before/after the break candle)
      - Horizontal dashed line at the broken swing price
      - Swing candle marker with HH/HL/LH/LL label
      - Break candle with "BOS" arrow marker
      - Connecting line from swing → break
      - Info header with score, classification, displacement
      - Color: External=green tone, Internal=blue tone
    """
    b_idx = bos_event["candle_index"]
    s_idx = bos_event.get("swing_index", 0)
    swing_type = bos_event.get("swing_type", "?")
    direction = bos_event["direction"]
    score = bos_event.get("score", 0)
    cls = bos_event.get("classification", "?")
    bos_type = bos_event.get("bos_type", "?")
    disp_pct = bos_event.get("displacement_pct", 0)
    breakdown = bos_event.get("breakdown", {})
    swing_price = bos_event["price"]

    # Data window
    start = max(0, b_idx - window)
    end = min(len(candles), b_idx + 15)
    segment = candles[start:end]
    if not segment:
        return

    # Determine price range
    highs = [c["high"] for c in segment]
    lows = [c["low"] for c in segment]
    price_range = max(highs) - min(lows)
    y_pad = price_range * 0.08

    # Timestamps for x-axis
    times = [_to_idx(c["time"]) for c in segment]

    # Create figure
    fig, ax = plt.subplots(figsize=(16, 9), facecolor="#1a1a2e")
    fig.subplots_adjust(left=0.05, right=0.95, top=0.88, bottom=0.05)

    # ── Draw candlesticks ──
    for i, c in enumerate(segment):
        t = times[i]
        open_p, high, low, close = c["open"], c["high"], c["low"], c["close"]
        is_green = close >= open_p

        if is_green:
            color = "#26a69a"
            body_color = "#26a69a"
        else:
            color = "#ef5350"
            body_color = "#ef5350"

        # Wick
        ax.plot([t, t], [low, high], color=color, linewidth=0.8, zorder=1)

        # Body
        body_bottom = min(open_p, close)
        body_top = max(open_p, close)
        body_h = max(body_top - body_bottom, 0.5)
        ax.bar(t, body_h, bottom=body_bottom, width=0.6,
               color=body_color, edgecolor=color, linewidth=0.5, zorder=2)

    # ── Swing level line ──
    swing_line_color = "#ff7043" if direction == "bullish" else "#42a5f5"
    ax.axhline(y=swing_price, xmin=0, xmax=1,
               color=swing_line_color, linestyle="--", linewidth=1.5,
               alpha=0.8, zorder=3)
    ax.text(times[0], swing_price, f"  ${swing_price:,.2f}",
            color=swing_line_color, fontsize=9, va="bottom",
            fontweight="bold", alpha=0.8)

    # ── Swing candle marker ──
    rel_s = s_idx - start
    if 0 <= rel_s < len(segment):
        s_time = times[rel_s]
        s_high = segment[rel_s]["high"]
        s_low = segment[rel_s]["low"]
        marker_color = "#66bb6a" if swing_type in ("HH", "HL") else "#ef5350"
        ax.scatter(s_time, s_high + y_pad * 0.3, marker="v", s=80,
                   color=marker_color, zorder=5)
        ax.text(s_time, s_high + y_pad * 0.5, swing_type,
                color=marker_color, fontsize=10, ha="center",
                fontweight="bold", zorder=5)

    # ── Break candle marker ──
    rel_b = b_idx - start
    if 0 <= rel_b < len(segment):
        b_time = times[rel_b]
        b_low = segment[rel_b]["low"]
        b_high = segment[rel_b]["high"]
        # Arrow pointing to the break candle
        if direction == "bullish":
            arrow_y = b_low - y_pad * 0.3
            ax.scatter(b_time, b_low - y_pad * 0.1, marker="^", s=120,
                       color="#ffeb3b", zorder=5)
            ax.text(b_time, arrow_y - y_pad * 0.2, "BOS ↑",
                    color="#ffeb3b", fontsize=11, ha="center",
                    fontweight="bold", zorder=5)
        else:
            arrow_y = b_high + y_pad * 0.3
            ax.scatter(b_time, b_high + y_pad * 0.1, marker="v", s=120,
                       color="#ffeb3b", zorder=5)
            ax.text(b_time, arrow_y + y_pad * 0.2, "BOS ↓",
                    color="#ffeb3b", fontsize=11, ha="center",
                    fontweight="bold", zorder=5)

    # ── Connecting line: swing → break ──
    if 0 <= rel_s < len(segment) and 0 <= rel_b < len(segment):
        s_time = times[rel_s]
        b_time = times[rel_b]
        mid_y = swing_price
        conn_color = "#ffeb3b"  # yellow
        ax.plot([s_time, b_time], [mid_y, mid_y], color=conn_color,
                linewidth=1, linestyle=":", alpha=0.6, zorder=2)

    # ── Directional shading ──
    if direction == "bullish":
        # Light green shade above swing level
        ax.axhspan(swing_price, max(highs) + y_pad, alpha=0.04,
                   color="#66bb6a", zorder=0)
    else:
        # Light red shade below swing level
        ax.axhspan(min(lows) - y_pad, swing_price, alpha=0.04,
                   color="#ef5350", zorder=0)

    # ── Info header ──
    header_color = "#66bb6a" if bos_type == "External" else "#42a5f5"
    title_str = (
        f"BOS #{bos_event.get('_idx', '?')} | "
        f"{'Bullish ' if direction == 'bullish' else 'Bearish '} | "
        f"Score={score} | {cls} | {bos_type}"
    )
    ax.set_title(title_str, color=header_color, fontsize=16,
                 fontweight="bold", pad=15)

    # Metadata below title
    swing_candle = segment[rel_s] if 0 <= rel_s < len(segment) else None
    swing_time = datetime.utcfromtimestamp(segment[rel_s]["time"]).strftime("%Y-%m-%d %H:%M") if swing_candle else "?"
    break_time = datetime.utcfromtimestamp(segment[rel_b]["time"]).strftime("%Y-%m-%d %H:%M") if 0 <= rel_b < len(segment) else "?"

    meta = (
        f"Swing: {swing_type} @{s_idx}  ${swing_price:,.2f} ({swing_time})  |  "
        f"Break @{b_idx}  (${candles[b_idx]['close']:,.2f}) ({break_time})  |  "
        f"Displacement: {disp_pct:.3f}%  |  "
        f"C1={breakdown.get('close_beyond',0)} C2={breakdown.get('body_beyond',0)} "
        f"C3={breakdown.get('strong_candle',0)} C4={breakdown.get('displacement',0)} "
        f"C5={breakdown.get('structure',0)} C6={breakdown.get('atr_expansion',0)} "
        f"C7={breakdown.get('bos_distance',0)} C8={breakdown.get('volume',0)}"
    )
    fig.text(0.5, 0.92, meta, ha="center", fontsize=8,
             color="#aaaaaa", fontfamily="monospace")

    # ── Axis styling ──
    # Show every 10th candle label
    step = max(1, len(segment) // 10)
    visible_indices = list(range(0, len(segment), step))
    ax.set_xticks([times[i] for i in visible_indices])
    ax.set_xticklabels([segment[i]["index"] for i in visible_indices],
                        fontsize=7, color="#888888")

    ax.set_ylabel("Price (USD)", color="#aaaaaa", fontsize=10)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"${x:,.0f}"))
    ax.tick_params(axis="y", colors="#888888", labelsize=9)

    ax.set_facecolor("#16213e")
    ax.grid(True, alpha=0.1, color="#ffffff", linewidth=0.5)
    for spine in ax.spines.values():
        spine.set_color("#333333")

    # ── Color coding border ──
    border_color = "#66bb6a" if bos_type == "External" else "#42a5f5"
    for spine in ax.spines.values():
        spine.set_color(border_color)
        spine.set_linewidth(2)

    # ── Legend ──
    from matplotlib.lines import Line2D
    legend_lines = [
        Line2D([0], [0], color=swing_line_color, linestyle="--", linewidth=1.5,
               label=f"Swing Level ${swing_price:,.2f}"),
        Line2D([0], [0], color="#ffeb3b", linestyle=":", linewidth=1,
               label=f"Swing → Break ({b_idx - s_idx} candles)"),
        Line2D([0], [0], marker="v", color="w", markerfacecolor="#ffeb3b",
               markersize=8, label="BOS Break Candle"),
    ]
    ax.legend(handles=legend_lines, loc="lower right", fontsize=8,
              facecolor="#1a1a2e", edgecolor="#333333", labelcolor="#cccccc")

    fig.savefig(output_path, dpi=150, bbox_inches="tight",
                facecolor="#1a1a2e", edgecolor="none")
    plt.close(fig)
    logger.info("Saved BOS chart: %s", output_path)
