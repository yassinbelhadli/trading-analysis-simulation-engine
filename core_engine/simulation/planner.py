"""TradePlanner — converts Snapshot + optional Explanation into a TradePlan.

TradePlan is the single contract between analysis and execution/simulation.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass(frozen=True)
class TradePlan:
    """Plan for a single trade — consumed by Simulation, Execution, MT5, Dashboard.

    All fields are resolved to concrete values (no placeholders).
    """
    side: str                  # BUY / SELL
    entry: float
    stop_loss: float
    take_profits: List[float]
    risk_percent: float        # % of account to risk
    partials: List[float]      # fraction of position per TP (sums to 1.0)
    slippage_tolerance: float = 0.0005
    max_spread: float = 0.0002
    label: str = ""
    plan_id: str = ""

    @property
    def risk_distance(self) -> float:
        return abs(self.entry - self.stop_loss)

    @property
    def tp_count(self) -> int:
        return len(self.take_profits)

    def rr_of(self, tp_index: int = 0) -> float:
        if tp_index >= len(self.take_profits) or self.risk_distance == 0:
            return 0.0
        return abs(self.take_profits[tp_index] - self.entry) / self.risk_distance


def build_plan(snapshot: Dict[str, Any]) -> TradePlan:
    """Build a TradePlan from a detection snapshot."""
    drawing = snapshot.get("drawing", {}) or {}
    trade = snapshot.get("trade", {}) or {}
    scoring = snapshot.get("scoring", {}) or {}

    side = _detect_side(drawing, trade, scoring)
    entry = float(drawing.get("entry_price") or trade.get("entry_price") or 0)
    sl = float(drawing.get("sl_price") or trade.get("sl_price") or 0)
    tp_raw = drawing.get("tp", []) or trade.get("tp_prices", []) or []

    take_profits = [float(t) for t in (tp_raw if isinstance(tp_raw, list) else [tp_raw]) if t]
    if not take_profits:
        # Fallback: 2:1 default RR
        dist = abs(entry - sl) if entry and sl else 0
        if dist and entry:
            tp_default = entry + dist * 2 if side == "BUY" else entry - dist * 2
            take_profits = [round(tp_default, 2)]

    # Default: 50% at TP1, 30% at TP2, 20% at TP3
    if len(take_profits) <= 1:
        partials = [1.0]
    elif len(take_profits) == 2:
        partials = [0.50, 0.50]
    else:
        partials = [0.50, 0.30, 0.20]

    # Sum partials to 1.0
    total = sum(partials)
    if total > 0:
        partials = [p / total for p in partials]

    risk_pct = float(drawing.get("risk_percent", trade.get("risk_percent", 0.5)))

    return TradePlan(
        side=side,
        entry=entry,
        stop_loss=sl,
        take_profits=take_profits,
        risk_percent=risk_pct,
        partials=partials[:len(take_profits)],
        label=f"{side} @ {entry}",
    )


def _detect_side(drawing: dict, trade: dict, scoring: dict) -> str:
    raw = (drawing.get("buy_sell") or trade.get("direction")
           or scoring.get("direction") or "").upper()
    if raw in ("BUY", "BULLISH"):
        return "BUY"
    if raw in ("SELL", "BEARISH"):
        return "SELL"
    return "BUY"
