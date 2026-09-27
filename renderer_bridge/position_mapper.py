"""PositionMapper — converts active broker position + lifecycle to the
canonical snapshot format.

For live position monitoring: shows current price, entry, SL, TPs,
BE status, trailing status on the chart.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional

from renderer_v2.scene import Scene
from renderer_v2.builder import build_scene

from core_engine.execution.broker import PositionInfo, OrderSide
from core_engine.simulation.lifecycle import TradeLifecycle


def position_to_snapshot(
    position: PositionInfo,
    lifecycle: Optional[TradeLifecycle] = None,
    candles: Optional[List[Dict]] = None,
    current_price: Optional[float] = None,
    symbol: str = "",
    timeframe: str = "",
    total_r: float = 0.0,
) -> Dict[str, Any]:
    """Convert an active position + lifecycle state into a snapshot.

    Args:
        position: current broker position
        lifecycle: optional TradeLifecycle for BE/trailing state
        candles: optional OHLC data
        current_price: current market price
        symbol: instrument name
        timeframe: timeframe label
        total_r: current R multiple

    Returns:
        Canonical snapshot dict consumable by build_scene().
    """
    side = "BUY" if position.side == OrderSide.BUY else "SELL"
    entry = position.open_price
    sl = position.stop_loss
    tp = position.take_profit
    price = current_price or position.open_price

    ohlc = _normalise_candles(candles) if candles else _dummy_candles(entry, price)
    last_idx = max(0, len(ohlc) - 1)

    drawing: Dict[str, Any] = {
        "buy_sell": side,
        "entry_price": entry,
        "sl_price": sl,
        "tp": [tp] if tp else [],
    }

    # Lifecycle state
    if lifecycle:
        state = lifecycle.state
        if state in ("BE_SET", "TRAILING"):
            drawing["be_price"] = lifecycle.current_sl
        if state == "TRAILING":
            drawing["trailing_active"] = True
        if lifecycle.partials and lifecycle.partials.tps_hit:
            for i, tp_hit in enumerate(lifecycle.partials.tps_hit):
                drawing[f"tp{i+1}_hit"] = True

    drawing["realized_r"] = round(total_r, 2)

    status_label = lifecycle.state if lifecycle else "ACTIVE"
    status_icon = "🟢" if "WIN" in str(total_r) else (
        "🔴" if total_r < 0 else "⚪")

    return {
        "metadata": {
            "symbol": symbol or position.symbol,
            "timeframe": timeframe,
            "status": status_label,
        },
        "chart": {
            "ohlc": ohlc,
        },
        "drawing": drawing,
        "scoring": {
            "score": 0,
            "direction": side,
        },
    }


def position_to_scene(
    position: PositionInfo,
    lifecycle: Optional[TradeLifecycle] = None,
    candles: Optional[List[Dict]] = None,
    current_price: Optional[float] = None,
    symbol: str = "",
    timeframe: str = "",
    total_r: float = 0.0,
) -> Scene:
    """Convert an active position directly to a Scene."""
    snapshot = position_to_snapshot(
        position, lifecycle, candles, current_price, symbol, timeframe, total_r)
    return build_scene(snapshot)


# ── Helpers ──────────────────────────────────────────────────────

def _normalise_candles(candles: List[Dict]) -> List[Dict]:
    result = []
    for i, c in enumerate(candles):
        entry = dict(c)
        entry["index"] = i
        for key in ("open", "high", "low", "close", "volume"):
            entry.setdefault(key, 0)
        entry.setdefault("time", "")
        result.append(entry)
    return result


def _dummy_candles(entry: float, current: float, count: int = 10) -> List[Dict]:
    """Generate minimal candle data around entry/current price range."""
    low = min(entry, current) * 0.998
    high = max(entry, current) * 1.002
    mid = (entry + current) / 2
    return [
        {"index": i, "open": mid, "high": high, "low": low,
         "close": current if i == count - 1 else mid,
         "volume": 0, "time": ""}
        for i in range(count)
    ]
