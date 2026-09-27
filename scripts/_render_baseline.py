"""Render a realistic SELL setup snapshot with the current renderer (baseline)."""
import sys, os, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from renderer_v2 import render_snapshot
from renderer_v2.theme import LIGHT_THEME

random.seed(42)
np.random.seed(42)

# Synthetic OHLC: range-bound -> drop into discount -> sweep high -> pullback (ICT path)
n = 180
from datetime import datetime, timedelta
base = datetime(2026, 7, 31, 8, 0)
anchors = [(0, 3320.0), (60, 3320.0), (100, 3300.0), (150, 3325.0), (179, 3318.0)]
candles = []
prev_close = 3320.0
for i in range(n):
    # target price = linear interpolation along anchors
    t0, p0 = anchors[0], anchors[-1]
    for a, b in zip(anchors, anchors[1:]):
        if a[0] <= i <= b[0]:
            frac = (i - a[0]) / max(1, b[0] - a[0])
            target = a[1] + (b[1] - a[1]) * frac
            break
    o = prev_close
    c = round(target + random.uniform(-0.8, 0.6), 2)
    hi = round(max(o, c) + random.uniform(0.2, 1.0), 2)
    lo = round(min(o, c) - random.uniform(0.2, 1.0), 2)
    candles.append({"index": i, "open": round(o, 2), "high": hi,
                    "low": lo, "close": c,
                    "time": (base + timedelta(minutes=5 * i)).isoformat()})
    prev_close = c

last = candles[-1]["close"]
high5 = max(c["high"] for c in candles[-14:])

snap = {
    "metadata": {"symbol": "XAUUSD", "timeframe": "M5", "setup_id": "demo_sell", "theme": "light"},
    "chart": {"ohlc": candles},
    "structure": {
        "bos": {"price": last * 0.998, "start_index": 30, "end_index": n - 1, "direction": "BEARISH", "label": "BOS"},
        "mss": {"price": high5, "start_index": n - 12, "end_index": n - 1, "direction": "BEARISH", "label": "MSS"},
        "swings": [
            {"type": "HH", "price": high5, "index": n - 12},
            {"type": "LH", "price": high5 - 1.0, "index": n - 8},
            {"type": "LL", "price": last - 2.0, "index": n - 2},
        ],
    },
    "liquidity": {"pdh": high5 + 3.0, "pdl": last - 5.0, "sweep_price": high5 + 4.0, "sweep_type": "SELL_SIDE"},
    "session": {"pdh": high5 + 3.0, "pdl": last - 5.0},
    "order_blocks": [
        {"type": "BEARISH", "top": high5 + 0.5, "bottom": high5 - 2.5, "anchor_candle": n - 12, "fresh": True},
    ],
    "fvg": [
        {"type": "BEARISH", "top": last + 1.2, "bottom": last - 1.2, "candle": n - 8},
    ],
    "scoring": {"score": 92, "direction": "SELL", "rank": "A", "confidence_score": 88,
                 "confidence_label": "HIGH", "approved": True, "reasons": ["MSS", "BOS", "Liquidity Sweep", "Bearish FVG", "Fresh OB", "Premium Zone"]},
    "drawing": {
        "buy_sell": "SELL",
        "entry_price": last,
        "sl_price": high5 + 3.0,
        "tp": [last - 3.0, last - 7.0, last - 12.0],
    },
    "premium_discount": {"equilibrium": (max(c["high"] for c in candles) + min(c["low"] for c in candles)) / 2,
                         "premium_high": max(c["high"] for c in candles),
                         "discount_low": min(c["low"] for c in candles)},
}

os.makedirs("backtester/reports", exist_ok=True)
img = render_snapshot(snap, output_path="backtester/reports/rv2_baseline.png", theme=LIGHT_THEME, width=1200, height=600)
print(f"Rendered: {img.size}")
