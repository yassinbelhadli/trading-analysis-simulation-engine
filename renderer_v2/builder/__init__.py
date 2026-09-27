"""Builder pipeline — snapshot dict → Scene.

Each builder handles one domain. The pipeline:
    Snapshot → CandleBuilder → StructureBuilder → LiquidityBuilder →
    OBBuilder → FVGBuilder → TradeBuilder → AnnotationBuilder → Merge → Scene
"""

from typing import Dict, List

from ..scene import (
    Scene, Layer, LayerType, Viewport, Element, BoundingBox,
    Direction, CollisionPolicy,
)

from .candles import CandleBuilder
from .structure import StructureBuilder
from .liquidity import LiquidityBuilder
from .order_blocks import OBBuilder
from .fvg import FVGBuilder
from .trades import TradeBuilder
from .annotations import AnnotationBuilder


def build_scene(snapshot: dict, theme=None, minimal: bool = False) -> Scene:
    """Run the full builder pipeline on a snapshot.

    Args:
        snapshot: canonical snapshot dict
        theme: optional theme (unused by builders)
        minimal: if True, build only candles + Entry/SL/TP levels and drop
                 every other overlay (structure, liquidity, FVG, OB, zones).
                 Used for clean Telegram signal charts.
    """
    candle_b = CandleBuilder()
    trade_b = TradeBuilder()
    structure_b = StructureBuilder()
    liquidity_b = LiquidityBuilder()
    ob_b = OBBuilder()
    fvg_b = FVGBuilder()
    annot_b = AnnotationBuilder()

    meta = snapshot.get("metadata", {})
    candles = snapshot.get("chart", {}).get("ohlc", [])

    elements = []
    elements.extend(candle_b.build(snapshot))
    if minimal:
        elements.extend(trade_b.build(snapshot))
    else:
        elements.extend(structure_b.build(snapshot))
        elements.extend(liquidity_b.build(snapshot))
        elements.extend(ob_b.build(snapshot))
        elements.extend(fvg_b.build(snapshot))
        elements.extend(trade_b.build(snapshot))
        elements.extend(annot_b.build(snapshot))

    # Compute viewport from candle data, auto-scaling to keep all essential
    # levels (Entry/SL/TP, BOS/CHoCH/MSS, PDH/PDL/Sweep, zones) fully visible.
    if candles:
        lo = min(c["low"] for c in candles)
        hi = max(c["high"] for c in candles)
        levels = _collect_price_levels(snapshot, minimal=minimal)
        if levels:
            lo = min(lo, min(levels))
            hi = max(hi, max(levels))
        pad = max((hi - lo) * 0.05, hi * 1e-6)
        vp = Viewport(
            candle_first=0,
            candle_last=max(0, len(candles) - 1),
            price_min=lo - pad,
            price_max=hi + pad,
        )
    else:
        vp = Viewport()

    # Organise into layers
    layer_map = {lt: [] for lt in LayerType}
    for el in elements:
        if el.layer in layer_map:
            layer_map[el.layer].append(el)

    layers = [
        Layer(type=lt, elements=layer_map[lt])
        for lt in LayerType
        if layer_map[lt]
    ]

    chart = snapshot.get("chart", {})
    ohlc = chart.get("ohlc", [])
    current_price = None
    if ohlc:
        current_price = ohlc[-1].get("close") or ohlc[-1].get("Close")
        if current_price is not None:
            current_price = float(current_price)
    return Scene(
        metadata={
            "scene_version": 2,
            "theme": meta.get("theme", "dark"),
            "symbol": meta.get("symbol", ""),
            "timeframe": meta.get("timeframe", ""),
            "snapshot_id": meta.get("setup_id", ""),
            "original": meta,
            "premium_discount": snapshot.get("premium_discount", {}),
            "chart": chart,
            "drawing": snapshot.get("drawing", {}),
            "trade": snapshot.get("trade", {}),
            "scoring": snapshot.get("scoring", {}),
            "structure": snapshot.get("structure", {}),
            "liquidity": snapshot.get("liquidity", {}),
            "order_blocks": snapshot.get("order_blocks", []),
            "fvg": snapshot.get("fvg", []) or snapshot.get("fvgs", []),
            "session": snapshot.get("session", {}),
            "current_price": current_price,
            "_minimal": minimal,
        },
        viewport=vp,
        layers=layers,
    )


def _collect_price_levels(snapshot: dict, minimal: bool = False) -> List[float]:
    """Collect every important price level so the viewport auto-scales to include
    trade lines, structure and liquidity levels even if they sit beyond the
    candle range (e.g. a far stop-loss)."""
    levels: List[float] = []

    def add(value):
        if value is None:
            return
        try:
            f = float(value)
        except (ValueError, TypeError):
            return
        if f == f and f != 0.0 and abs(f) < 1e15:  # skip NaN / junk
            levels.append(f)

    drawing = snapshot.get("drawing", {}) or {}
    trade = snapshot.get("trade", {}) or {}
    for src in (drawing, trade):
        for key in ("entry_price", "sl_price", "exit_price", "partial_price", "be_price"):
            add(src.get(key))
        tp = src.get("tp") or src.get("tp_prices") or []
        if isinstance(tp, list):
            for t in tp:
                add(t)
        else:
            add(tp)

    if minimal:
        return levels

    struct = snapshot.get("structure", {}) or {}
    for key in ("bos", "choch", "mss"):
        entry = struct.get(key)
        if isinstance(entry, dict):
            add(entry.get("price") or entry.get("level"))

    liquid = snapshot.get("liquidity", {}) or {}
    for key in ("pdh", "pdl", "sweep_price"):
        add(liquid.get(key))
    session = snapshot.get("session", {}) or {}
    for key in ("pdh", "pdl"):
        add(session.get(key))

    pd = snapshot.get("premium_discount", {}) or {}
    for key in ("premium_high", "discount_low", "equilibrium"):
        add(pd.get(key))

    ohlc = snapshot.get("chart", {}).get("ohlc", [])
    if ohlc:
        add(ohlc[-1].get("close"))

    return levels
