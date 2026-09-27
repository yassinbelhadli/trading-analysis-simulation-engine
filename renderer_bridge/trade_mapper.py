"""TradeMapper — converts TradeResult + candle data to the canonical snapshot format.

For post-trade visualisation: shows entry, SL, TPs, BE, trailing, exit, and
trade outcome on the chart.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional

from renderer_v2.scene import Scene
from renderer_v2.builder import build_scene

from core_engine.simulation.result import TradeResult, TradeEvent, TradeState, TradeOutcome
from core_engine.simulation.planner import TradePlan


def trade_to_snapshot(
    result: TradeResult,
    candles: List[Dict],
    plan: Optional[TradePlan] = None,
    symbol: str = "",
    timeframe: str = "",
) -> Dict[str, Any]:
    """Convert a TradeResult into the canonical snapshot format.

    Args:
        result: simulation result with events
        candles: OHLC data (list of dicts with open/high/low/close/volume)
        plan: optional TradePlan (used for entry, SL, TPs if not in events)
        symbol: instrument name
        timeframe: timeframe label

    Returns:
        Canonical snapshot dict consumable by build_scene().
    """
    events = result.events
    fill_event = _first_event_of(events, TradeState.FILLED)
    exit_event = _last_event_of(events, (TradeState.STOPPED, TradeState.CLOSED))
    tp_events = [e for e in events if "TP" in e.state]
    be_event = _first_event_of(events, TradeState.BE_SET)
    trail_event = _first_event_of(events, TradeState.TRAILING)

    # Determine direction from fill or first event
    side = _detect_side(events, fill_event, plan)

    # Entry price
    entry = fill_event.price if fill_event and fill_event.price else (
        plan.entry if plan else 0)

    # Stop loss
    sl = plan.stop_loss if plan else 0

    # Take profits
    tps: List[float] = []
    if plan and plan.take_profits:
        tps = list(plan.take_profits)
    elif fill_event and fill_event.price and sl:
        dist = abs(entry - sl)
        tps = [entry + dist * 2 if side == "BUY" else entry - dist * 2]

    last_idx = max(0, len(candles) - 1)

    # Build drawing section
    drawing: Dict[str, Any] = {
        "buy_sell": side,
        "entry_price": entry,
        "sl_price": sl,
        "tp": tps,
    }

    # Mark hit TPs
    for tp_ev in tp_events:
        tp_idx = _which_tp(tp_ev, tps)
        if tp_idx >= 0:
            drawing[f"tp{tp_idx+1}_hit"] = True

    if be_event:
        drawing["be_price"] = be_event.price

    if trail_event:
        drawing["trailing_active"] = True

    if exit_event:
        drawing["exit_price"] = exit_event.price
        if result.total_r != 0:
            drawing["realized_r"] = result.total_r

    # Outcome label
    outcome_label = {
        TradeOutcome.WIN: "WIN",
        TradeOutcome.LOSS: "LOSS",
        TradeOutcome.BE: "BREAK_EVEN",
    }.get(result.outcome, result.outcome)

    return {
        "metadata": {
            "symbol": symbol,
            "timeframe": timeframe,
            "outcome": outcome_label,
        },
        "chart": {
            "ohlc": _normalise_candles(candles),
        },
        "drawing": drawing,
        "scoring": {
            "score": 0,
            "direction": side,
        },
    }


def trade_to_scene(
    result: TradeResult,
    candles: List[Dict],
    plan: Optional[TradePlan] = None,
    symbol: str = "",
    timeframe: str = "",
) -> Scene:
    """Convert a TradeResult directly to a Scene.

    Args:
        result: simulation result
        candles: OHLC data
        plan: trade plan (optional)
        symbol: symbol name
        timeframe: timeframe label

    Returns:
        Scene ready for layout + rendering.
    """
    snapshot = trade_to_snapshot(result, candles, plan, symbol, timeframe)
    return build_scene(snapshot)


# ── Helpers ──────────────────────────────────────────────────────

def _first_event_of(events: List[TradeEvent], state: str) -> Optional[TradeEvent]:
    for e in events:
        if e.state == state:
            return e
    return None


def _last_event_of(events: List[TradeEvent], states: tuple) -> Optional[TradeEvent]:
    for e in reversed(events):
        if e.state in states:
            return e
    return None


def _detect_side(events: List[TradeEvent], fill_event: Optional[TradeEvent],
                 plan: Optional[TradePlan]) -> str:
    if plan:
        return "BUY" if plan.side == "BUY" else "SELL"
    if fill_event and fill_event.description:
        desc = fill_event.description.upper()
        if "BUY" in desc or "LONG" in desc:
            return "BUY"
        if "SELL" in desc or "SHORT" in desc:
            return "SELL"
    return "BUY"


def _which_tp(event: TradeEvent, tps: List[float]) -> int:
    """Determine which TP number an event corresponds to."""
    for i, tp in enumerate(tps):
        if abs(event.price - tp) / max(abs(tp), 0.001) < 0.02:
            return i
    return -1


def _normalise_candles(candles: List[Dict]) -> List[Dict]:
    """Ensure candles have index and required fields."""
    result = []
    for i, c in enumerate(candles):
        entry = dict(c)
        entry["index"] = i
        for key in ("open", "high", "low", "close", "volume"):
            entry.setdefault(key, 0)
        entry.setdefault("time", "")
        result.append(entry)
    return result
