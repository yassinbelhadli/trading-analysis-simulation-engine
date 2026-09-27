"""Renderer QA harness.

Generates a wide matrix of snapshots (BUY/SELL x symbols x timeframes x
structure types x features x volatility x TP counts x win/loss), renders each
and runs programmatic geometry + pixel checks:

  1. Every trade level (Entry/SL/TP) fully inside the chart area.
  2. Every structure/liquidity/OB/FVG/swing element inside the chart area.
  3. Trade-level ordering sanity (SELL: sl > entry > tp; BUY: sl < entry < tp).
  4. Time-axis labels do not overlap.
  5. Price-axis labels do not overlap.
  6. Info card stays inside the chart.
  7. Pixel presence of Entry/SL/TP line colors.

Usage:  python scripts/_qa_render.py [output_dir]
"""
import sys, os, random, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime, timedelta
from PIL import Image
import numpy as np

from renderer_v2 import render_snapshot
from renderer_v2.backends.pil import PILBackend
from renderer_v2.theme import LIGHT_THEME
from renderer_v2.enums import ElementType

OUT = sys.argv[1] if len(sys.argv) > 1 else "backtester/reports/qa"
HEADER_H, LEFT_MARGIN, TIME_AXIS_H, PRICE_AXIS_W = 34, 6, 26, 78

random.seed(1234)
np.random.seed(1234)

# ── synthetic candle generation ──────────────────────────────────────
SYMBOLS = {
    "XAUUSD":  {"px": 3320.0, "vol": 2.0,  "dec": 2},
    "BTCUSD":  {"px": 68000.0, "vol": 400.0, "dec": 1},
    "US100":   {"px": 22000.0, "vol": 120.0, "dec": 1},
    "EURUSD":  {"px": 1.0850, "vol": 0.0012, "dec": 5},
}
TFS = {"M5": 180, "M15": 96, "H1": 120}


def gen_candles(symbol, tf, vol_scale=1.0, direction="SELL"):
    base = SYMBOLS[symbol]["px"]
    vol = SYMBOLS[symbol]["vol"] * vol_scale
    n = TFS[tf]
    candles = []
    p = base
    start = datetime(2026, 7, 31, 8, 0)
    for i in range(n):
        o = p
        drift = -vol * 0.06 if direction == "SELL" else vol * 0.06
        c = o + drift + random.uniform(-vol, vol)
        hi = max(o, c) + random.uniform(vol * 0.1, vol * 0.6)
        lo = min(o, c) - random.uniform(vol * 0.1, vol * 0.6)
        dec = SYMBOLS[symbol]["dec"]
        candles.append({"index": i, "open": round(o, dec), "high": round(hi, dec),
                        "low": round(lo, dec), "close": round(c, dec),
                        "time": (start + timedelta(minutes={  # noqa: E251
                            "M5": 5, "M15": 15, "H1": 60}[tf] * i)).isoformat()})
        p = c
    return candles


def nearest(values, price):
    return min(values, key=lambda v: abs(v - price))


# ── scenario matrix ──────────────────────────────────────────────────
SCENARIOS = []


def add(name, **kw):
    SCENARIOS.append({"name": name, **kw})


struct_types = ["bos", "choch", "mss"]
for symbol in SYMBOLS:
    for tf in TFS:
        for direction in ("SELL", "BUY"):
            base = SYMBOLS[symbol]["px"]
            add(f"{symbol}_{tf}_{direction}_plain", symbol=symbol, tf=tf,
                direction=direction, struct="bos")
            add(f"{symbol}_{tf}_{direction}_full", symbol=symbol, tf=tf,
                direction=direction, struct="bos", ob=True, fvg=True, sweep=True)
            if symbol == "XAUUSD" and tf == "M5":
                for st in struct_types:
                    add(f"XAUUSD_M5_{direction}_{st}", symbol=symbol, tf=tf,
                        direction=direction, struct=st, ob=True, fvg=True)

# Feature stress: every structure type on XAU/M15
for st in struct_types:
    for direction in ("SELL", "BUY"):
        add(f"XAUUSD_M15_{direction}_{st}_nosweep", symbol="XAUUSD", tf="M15",
            direction=direction, struct=st)

# TP count stress
for tpc in (1, 2, 3):
    add(f"XAUUSD_M5_SELL_tp{tpc}", symbol="XAUUSD", tf="M5", direction="SELL",
        struct="bos", tp_count=tpc, ob=True, fvg=True)
    add(f"BTCUSD_M15_BUY_tp{tpc}", symbol="BTCUSD", tf="M15", direction="BUY",
        struct="mss", tp_count=tpc, ob=True)

# Volatility stress
add("XAUUSD_M5_SELL_highvol", symbol="XAUUSD", tf="M5", direction="SELL",
    struct="bos", vol_scale=6.0, ob=True, fvg=True)
add("EURUSD_H1_BUY_lowvol", symbol="EURUSD", tf="H1", direction="BUY",
    struct="bos", vol_scale=0.2)
add("US100_M15_SELL_highvol", symbol="US100", tf="M15", direction="SELL",
    struct="choch", vol_scale=5.0, sweep=True)

# Win / loss (exit realised below/above entry)
add("XAUUSD_M5_SELL_win", symbol="XAUUSD", tf="M5", direction="SELL",
    struct="bos", win=True, ob=True, fvg=True, sweep=True)
add("BTCUSD_M5_BUY_win", symbol="BTCUSD", tf="M5", direction="BUY",
    struct="mss", win=True, ob=True)
add("EURUSD_H1_SELL_loss", symbol="EURUSD", tf="H1", direction="SELL",
    struct="bos", loss=True)
add("US100_H1_BUY_loss", symbol="US100", tf="H1", direction="BUY",
    struct="choch", loss=True, sweep=True)

# Far levels (auto-scale stress): SL and TPs way outside candle range
add("XAUUSD_M5_SELL_farSL", symbol="XAUUSD", tf="M5", direction="SELL",
    struct="bos", far_sl=True, ob=True, fvg=True, sweep=True)
add("BTCUSD_H1_BUY_farTP", symbol="BTCUSD", tf="H1", direction="BUY",
    struct="mss", far_tp=True, ob=True)
add("US100_M5_SELL_farboth", symbol="US100", tf="M5", direction="SELL",
    struct="bos", far_sl=True, far_tp=True, sweep=True)

# Edge: few candles
add("XAUUSD_M5_SELL_20bars", symbol="XAUUSD", tf="M5", direction="SELL",
    struct="bos", bars=20, ob=True, fvg=True)
add("EURUSD_M5_BUY_10bars", symbol="EURUSD", tf="M5", direction="BUY",
    struct="bos", bars=10)

# Multiple simultaneous structure levels (stress label de-collision)
add("XAUUSD_M5_SELL_allstruct", symbol="XAUUSD", tf="M5", direction="SELL",
    structs=["bos", "choch", "mss"], ob=True, fvg=True, sweep=True)
add("BTCUSD_M15_BUY_allstruct", symbol="BTCUSD", tf="M15", direction="BUY",
    structs=["bos", "choch", "mss"], ob=True, fvg=True, sweep=True)
add("US100_H1_SELL_bos_choch", symbol="US100", tf="H1", direction="SELL",
    structs=["bos", "choch"], sweep=True, ob=True)
add("EURUSD_H1_BUY_choch_mss", symbol="EURUSD", tf="H1", direction="BUY",
    structs=["choch", "mss"], ob=True, fvg=True)

# BUY-side sweep + win/loss on both sides
add("BTCUSD_M5_SELL_sweep_buy", symbol="BTCUSD", tf="M5", direction="BUY",
    struct="bos", sweep=True, ob=True, fvg=True, win=True)
add("US100_H1_BUY_loss_sweep", symbol="US100", tf="H1", direction="BUY",
    struct="mss", sweep=True, loss=True)
add("XAUUSD_M15_BUY_farSL", symbol="XAUUSD", tf="M15", direction="BUY",
    struct="choch", far_sl=True, ob=True)
add("BTCUSD_H1_SELL_farboth", symbol="BTCUSD", tf="H1", direction="SELL",
    struct="mss", far_sl=True, far_tp=True, sweep=True)

# Flagship: EVERY ICT element on one chart, all symbols x timeframes.
# BOS + CHoCH + MSS + Order Block + FVG + Liquidity Sweep + PDH/PDL +
# Premium/Discount + Entry/SL/TP1/TP2/TP3 + Current Price + Info Card
# + checklist + score/confidence.
for symbol in SYMBOLS:
    for tf in TFS:
        for direction in ("SELL", "BUY"):
            add(f"{symbol}_{tf}_{direction}_flagship", symbol=symbol, tf=tf,
                direction=direction, structs=["bos", "choch", "mss"],
                ob=True, fvg=True, sweep=True, tp_count=3, win=True)
# Flagship losing-trade variants (exit on the wrong side)
add("XAUUSD_M5_SELL_flagship_loss", symbol="XAUUSD", tf="M5", direction="SELL",
    structs=["bos", "choch", "mss"], ob=True, fvg=True, sweep=True, loss=True)
add("EURUSD_H1_BUY_flagship_loss", symbol="EURUSD", tf="H1", direction="BUY",
    structs=["bos", "choch", "mss"], ob=True, fvg=True, sweep=True, loss=True)


# ── snapshot builder ─────────────────────────────────────────────────
def build_snapshot(sc):
    symbol = sc["symbol"]
    tf = sc["tf"]
    direction = sc["direction"]
    vol_scale = sc.get("vol_scale", 1.0)
    n_bars = sc.get("bars") or TFS[tf]

    candles = gen_candles(symbol, tf, vol_scale, direction)
    if n_bars < len(candles):
        candles = candles[-n_bars:]

    closes = [c["close"] for c in candles]
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]
    last = closes[-1]
    recent = candles[-14:]
    h5 = max(c["high"] for c in recent)
    l5 = min(c["low"] for c in recent)
    base = SYMBOLS[symbol]["px"]

    struct_map = {
        "bos": {"price": last - base * 0.0009, "label": "BOS"},
        "choch": {"price": h5 - base * 0.0004, "label": "CHoCH"},
        "mss": {"price": h5, "label": "MSS"},
    }
    struct_names = sc.get("structs") or [sc["struct"]]
    structure = {}
    for sn in struct_names:
        st = struct_map[sn]
        structure[sn] = {"price": st["price"], "direction": direction,
                         "start_index": len(candles) // 3,
                         "end_index": len(candles) - 1, "label": st["label"]}

    # levels sized to symbol
    atr = (max(highs) - min(lows)) / 6
    if sc.get("far_sl"):
        sl_dist = atr * 8
    else:
        sl_dist = atr * 0.8
    if sc.get("far_tp"):
        tp_span = atr * 9
    else:
        tp_span = atr * 0.5

    entry = last
    if direction == "SELL":
        sl = h5 + sl_dist * 0.4
        tp_count = sc.get("tp_count", 3)
        tps = [last - tp_span * (i + 1) / (tp_count + 1) for i in range(tp_count)]
        rr = abs(entry - sl) and abs(tps[0] - entry) / max(1e-12, abs(entry - sl))
    else:
        sl = l5 - sl_dist * 0.4
        tp_count = sc.get("tp_count", 3)
        tps = [last + tp_span * (i + 1) / (tp_count + 1) for i in range(tp_count)]
        rr = abs(entry - sl) and abs(tps[0] - entry) / max(1e-12, abs(entry - sl))

    drawing = {"buy_sell": direction, "entry_price": entry,
               "sl_price": sl, "tp": [round(t, SYMBOLS[symbol]["dec"]) for t in tps]}
    if sc.get("win"):
        drawing["exit_price"] = entry + tp_span * 0.8 if direction == "BUY" \
            else entry - tp_span * 0.8
    if sc.get("loss"):
        drawing["exit_price"] = entry + sl_dist * 0.3 if direction == "SELL" \
            else entry - sl_dist * 0.3

    liquid = {}
    if sc.get("sweep"):
        liquid = {"pdh": h5 + atr * 0.3, "pdl": l5 - atr * 0.3,
                  "sweep_price": h5 + atr * 0.4, "sweep_type": "SELL_SIDE" if direction == "SELL" else "BUY_SIDE"}

    obs = []
    if sc.get("ob"):
        obs = [{"type": "BEARISH" if direction == "SELL" else "BULLISH",
                "top": h5 - atr * 0.1, "bottom": h5 - atr * 0.5,
                "anchor_candle": len(candles) - 12, "fresh": True}]
    fvgs = []
    if sc.get("fvg"):
        fvgs = [{"type": "BEARISH" if direction == "SELL" else "BULLISH",
                 "top": last + atr * 0.2, "bottom": last - atr * 0.2,
                 "candle": len(candles) - 8}]

    reasons = [struct_map[sn]["label"] for sn in struct_names]
    reasons += ["BOS" if "bos" not in struct_names else "Break of Structure",
                "Liquidity Sweep" if sc.get("sweep") else "Break of Structure",
                "FVG" if sc.get("fvg") else "Order Block",
                "Premium" if direction == "SELL" else "Discount",
                "Session High"]
    return {
        "metadata": {"symbol": symbol, "timeframe": tf, "theme": "light"},
        "chart": {"ohlc": candles},
        "structure": structure,
        "liquidity": liquid,
        "session": liquid,
        "order_blocks": obs,
        "fvg": fvgs,
        "scoring": {"score": 80 + (len(SCENARIOS) % 15), "direction": direction,
                    "confidence_score": 70 + (len(SCENARIOS) % 25),
                    "confidence_label": "HIGH", "approved": True, "reasons": reasons},
        "drawing": drawing,
        "premium_discount": {"equilibrium": last,
                             "premium_high": max(highs), "discount_low": min(lows)},
    }


# ── checks ───────────────────────────────────────────────────────────
HARD_FAILS = []


def check(cond, label, ctx):
    if not cond:
        HARD_FAILS.append(f"{ctx['name']}: {label}")


def run_checks(name, snapshot, layout, resolved):
    mapper = layout.mapper
    W, H = mapper.bounds.width, mapper.bounds.height  # 1200 x 600 (mapper coords)
    tol = 1.0
    ctx = {"name": name}

    for el in resolved.elements:
        et = el.element.element_type
        if el.element.layer.name in ("CANDLES",):
            continue
        if not el.visible:
            continue
        in_x = -tol <= el.px_left <= W + tol and -tol <= el.px_right <= W + tol
        in_y = -tol <= el.px_top <= H + tol and -tol <= el.px_bottom <= H + tol
        check(in_x, f"element {et.name} x out of chart [{el.px_left:.0f},{el.px_right:.0f}]", ctx)
        check(in_y, f"element {et.name} y out of chart [{el.px_top:.0f},{el.px_bottom:.0f}]", ctx)

    # Trade ordering sanity
    drawing = snapshot.get("drawing", {})
    direction = drawing.get("buy_sell", "")
    entry = drawing.get("entry_price")
    sl = drawing.get("sl_price")
    tps = drawing.get("tp", [])
    if direction == "SELL":
        if entry is not None and sl is not None:
            check(sl > entry, "SELL sl must be above entry", ctx)
        for tp in tps:
            check(tp < entry, "SELL tp must be below entry", ctx)
    elif direction == "BUY":
        if entry is not None and sl is not None:
            check(sl < entry, "BUY sl must be below entry", ctx)
        for tp in tps:
            check(tp > entry, "BUY tp must be above entry", ctx)

    # Time labels overlap (replicate renderer layout)
    ohlc = snapshot.get("chart", {}).get("ohlc", [])
    if ohlc:
        n = len(ohlc)
        label_count = min(6, n)
        step = max(1, n // label_count)
        xs = []
        for i in range(0, n, step):
            x_pos = mapper.x_of(i)
            xs.append(x_pos)
        prev = None
        for x in xs:
            if prev is not None:
                # each label ~34px wide at font 13
                check(x - prev >= 34, f"time labels too close at x={x:.0f}", ctx)
            prev = x


def run_label_checks(name, backend, canvas_w, canvas_h):
    """Verify every right-edge label box is on-canvas and non-overlapping."""
    ctx = {"name": name}
    boxes = backend.drawn_labels
    for (top, bot, right, left) in boxes:
        check(0 <= top and bot <= canvas_h, f"label y out of image [{top:.0f},{bot:.0f}]", ctx)
        check(0 <= left and right <= canvas_w, f"label x out of image [{left:.0f},{right:.0f}]", ctx)
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i], boxes[j]
            ov_y = not (a[1] <= b[0] + 0.5 or b[1] <= a[0] + 0.5)
            ov_x = not (a[2] <= b[3] + 0.5 or b[2] <= a[3] + 0.5)
            if ov_y and ov_x:
                check(False, f"label overlap: #{i} vs #{j} "
                             f"[{a[0]:.0f}-{a[1]:.0f}] vs [{b[0]:.0f}-{b[1]:.0f}]", ctx)
    # flagship/allstruct stress must actually produce the expected label count
    if "flagship" in name or "allstruct" in name:
        check(len(boxes) >= 8, f"flagship should draw >=8 right labels, got {len(boxes)}", ctx)


def run_pixel_checks(name, img_path, snapshot):
    drawing = snapshot.get("drawing", {})
    direction = drawing.get("buy_sell", "")
    tps = [t for t in drawing.get("tp", []) if t]
    arr = np.array(Image.open(img_path).convert("RGB"))
    # Entry blue + SL red + TP green lines present
    for color, key, need in [
        ((41, 98, 255), "entry", True),
        ((239, 83, 80), "sl", True),
        ((8, 153, 129), "tp", bool(tps)),
    ]:
        if not need:
            continue
        n = int(np.sum(np.all(arr == color, axis=2)))
        check(n > 50, f"pixel check: {key} line color missing ({n} px)", {"name": name})


# ── main loop ────────────────────────────────────────────────────────
def main():
    os.makedirs(OUT, exist_ok=True)
    total = len(SCENARIOS)
    rendered = 0
    for i, sc in enumerate(SCENARIOS):
        name = sc["name"]
        snap = build_snapshot(sc)
        path = os.path.join(OUT, f"{name}.png")
        backend = PILBackend(LIGHT_THEME)
        try:
            img = render_snapshot(snap, output_path=path, theme=LIGHT_THEME,
                                  width=1200, height=600, backend=backend)
        except Exception as e:  # noqa: BLE001
            HARD_FAILS.append(f"{name}: EXCEPTION {e!r}")
            continue
        rendered += 1
        # re-run through layout to get resolved geometry
        from renderer_v2.builder import build_scene
        from renderer_v2.layout import layout_scene, PixelBounds
        from renderer_v2.collision import CollisionResolver
        scene = build_scene(snap)
        px = PixelBounds(top=0, bottom=600, left=0, right=1200, width=1200, height=600)
        layout = layout_scene(scene, px, None)
        resolved = CollisionResolver().resolve(layout)
        run_checks(name, snap, layout, resolved)
        run_label_checks(name, backend, 1284, 660)
        run_pixel_checks(name, path, snap)
        if (i + 1) % 10 == 0:
            print(f"  {i+1}/{total} rendered...")

    print(f"\nRendered {rendered}/{total} images to {OUT}")
    if HARD_FAILS:
        print(f"\n⚠  {len(HARD_FAILS)} FAILURES:")
        for f in HARD_FAILS:
            print(f"  - {f}")
        sys.exit(1)
    print("✅ All QA checks passed.")


if __name__ == "__main__":
    main()
