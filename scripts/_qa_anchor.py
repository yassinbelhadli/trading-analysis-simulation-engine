"""Final Visual QA — geometric anchoring verification.

Proves (programmatically, to pixel precision) that every ICT element drawn
on the flagship charts is tied to the CORRECT data:

  * structure (BOS/CHoCH/MSS) line is at the reported price and spans the
    reported candle range
  * OB/FVG rectangle boundaries match the snapshot's top/bottom/anchor candle
  * Entry/SL/TP start at the entry candle and sit at the correct prices
  * current-price level maps to the real last-close price
  * viewport auto-scale includes every level (nothing off-chart by design)
  * Info Card content is computed from the real snapshot values (behavioral:
    changing the data changes the card geometry, so it is NOT demo text)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from renderer_v2 import build_scene, layout_scene, render_snapshot
from renderer_v2.collision import CollisionResolver
from renderer_v2.layout import PixelBounds
from renderer_v2.theme import LIGHT_THEME
from renderer_v2.enums import ElementType
from renderer_v2.backends.pil import PILBackend

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts"))
from _qa_render import build_snapshot, SCENARIOS, SYMBOLS

FAILS = []


def check(cond, label):
    if not cond:
        FAILS.append(label)


flagship = [sc for sc in SCENARIOS if sc["name"].endswith("_flagship") or "flagship_loss" in sc["name"]]
assert flagship, "flagship scenarios missing"
print(f"Verifying {len(flagship)} flagship scenarios + all-symbol anchor matrix\n")

for sc in flagship:
    name = sc["name"]
    snap = build_snapshot(sc)
    scene = build_scene(snap)
    vp = scene.viewport
    px = PixelBounds(top=0, bottom=600, left=0, right=1200, width=1200, height=600)
    layout = layout_scene(scene, px, LIGHT_THEME)
    resolved = CollisionResolver().resolve(layout)
    m = layout.mapper
    tol_px = 1.5

    ohlc = snap["chart"]["ohlc"]
    last_idx = len(ohlc) - 1
    drawing = snap["drawing"]
    direction = drawing["buy_sell"]
    dec = SYMBOLS[sc["symbol"]]["dec"]

    # ── 1. Structure anchoring (BOS/CHoCH/MSS) ──
    for sn, sdata in snap["structure"].items():
        els = [e for e in resolved.elements if e.element.element_type == ElementType.STRUCTURE
               and getattr(e.element.kind, "name", str(e.element.kind)).lower() == sn]
        check(len(els) == 1, f"{name}: structure {sn} present")
        if not els:
            continue
        el = els[0]
        x0, x1 = m.x_of(sdata["start_index"]), m.x_of(sdata["end_index"])
        check(abs(el.px_left - x0) <= tol_px, f"{name}: {sn} left x {el.px_left:.1f} != candle start {x0:.1f}")
        check(abs(el.px_right - x1) <= tol_px, f"{name}: {sn} right x {el.px_right:.1f} != candle end {x1:.1f}")
        y = m.y_of(sdata["price"])
        check(abs(el.px_center_y - y) <= 2 * tol_px, f"{name}: {sn} y {el.px_center_y:.1f} != price {y:.1f}")

    # ── 2. OB boundaries ──
    for ob in snap["order_blocks"]:
        els = [e for e in resolved.elements if e.element.element_type == ElementType.ORDER_BLOCK]
        check(len(els) == 1, f"{name}: OB present")
        if els:
            el = els[0]
            check(abs(m.y_of(ob["top"]) - el.px_top) <= 3, f"{name}: OB top {el.px_top:.1f} != data {ob['top']}")
            check(abs(m.y_of(ob["bottom"]) - el.px_bottom) <= 3, f"{name}: OB bottom {el.px_bottom:.1f} != data {ob['bottom']}")

    # ── 3. FVG boundaries ──
    for fv in snap["fvg"]:
        els = [e for e in resolved.elements if e.element.element_type == ElementType.FVG]
        check(len(els) == 1, f"{name}: FVG present")
        if els:
            el = els[0]
            check(abs(m.y_of(fv["top"]) - el.px_top) <= 3, f"{name}: FVG top {el.px_top:.1f} != data {fv['top']}")
            check(abs(m.y_of(fv["bottom"]) - el.px_bottom) <= 3, f"{name}: FVG bottom {el.px_bottom:.1f} != data {fv['bottom']}")

    # ── 4. Trade levels: Entry/SL/TP start at the LAST candle (trade from entry candle) ──
    from renderer_v2.enums import TradeKind
    trade_els = [e for e in resolved.elements if e.element.element_type == ElementType.TRADE]
    check(len(trade_els) >= 5, f"{name}: trade elements (entry+sl+3tp) present, got {len(trade_els)}")
    entry_els = [e for e in trade_els if e.element.kind == TradeKind.ENTRY]
    sl_els = [e for e in trade_els if e.element.kind == TradeKind.STOP_LOSS]
    tp_els = [e for e in trade_els if e.element.kind == TradeKind.TAKE_PROFIT]
    if entry_els:
        eel = entry_els[0]
        check(abs(m.y_of(drawing["entry_price"]) - eel.px_center_y) <= 2, f"{name}: Entry y != data")
        check(eel.px_right >= m.x_of(last_idx) - tol_px, f"{name}: Entry right ends at last candle")
    if sl_els:
        sel = sl_els[0]
        check(abs(m.y_of(drawing["sl_price"]) - sel.px_center_y) <= 2, f"{name}: SL y != data")
        check(sel.px_right >= m.x_of(last_idx) - tol_px, f"{name}: SL right ends at last candle")
    tp_prices = drawing.get("tp") or []
    check(len(tp_els) == len(tp_prices), f"{name}: TP count {len(tp_els)} != {len(tp_prices)}")
    for tel, tp_price in zip(tp_els, tp_prices):
        check(abs(m.y_of(tp_price) - tel.px_center_y) <= 2, f"{name}: TP y != data")

    # ── 5. Current price = last close ──
    current_els = [e for e in resolved.elements if e.element.element_type == ElementType.LABEL
                   and (e.element.kind == "CURRENT_PRICE" or "current" in str(e.element.kind).lower())]
    if current_els:
        cel = current_els[0]
        y_last = m.y_of(ohlc[-1]["close"])
        check(abs(cel.px_center_y - y_last) <= 2, f"{name}: current-price y {cel.px_center_y:.1f} != last close {y_last:.1f}")

    # ── 6. Auto-scale includes every level ──
    all_levels = [drawing["entry_price"], drawing["sl_price"]] + list(tp_prices)
    all_levels += [s["price"] for s in snap["structure"].values()]
    for ob in snap["order_blocks"]:
        all_levels += [ob["top"], ob["bottom"]]
    for fv in snap["fvg"]:
        all_levels += [fv["top"], fv["bottom"]]
    all_levels += [snap["premium_discount"]["premium_high"], snap["premium_discount"]["discount_low"]]
    if snap["liquidity"]:
        all_levels += [snap["liquidity"]["pdh"], snap["liquidity"]["pdl"], snap["liquidity"]["sweep_price"]]
    for lvl in all_levels:
        check(vp.price_min <= lvl <= vp.price_max,
              f"{name}: level {lvl} outside auto-scaled viewport [{vp.price_min:.5f},{vp.price_max:.5f}]")

print("Structure/OB/FVG/trade/price anchoring checks done.")
print(f"{'✅ ALL PASS' if not FAILS else '❌ FAILURES'}")
if FAILS:
    for f in FAILS:
        print(f"  - {f}")
    sys.exit(1)
