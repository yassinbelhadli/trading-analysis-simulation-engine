"""Fill Model — simulates order execution.

Handles MARKET, LIMIT, and STOP orders with configurable slippage and spread.

The fill model is the only component that needs to be swapped when going live:
    - Simulation: ideal fills with configurable slippage
    - MT5: actual broker fills
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Optional

from .planner import TradePlan
from .result import FillInfo, TradeEvent, TradeState


class FillType:
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"


@dataclass
class FillResult:
    filled: bool
    price: float = 0.0
    fill_type: str = FillType.MARKET
    slippage: float = 0.0
    reason: str = ""


class FillModel:
    """Simulate order fills against candle data.

    Configurable:
        slippage_pct: max slippage as % of price (default 0.05%)
        spread_pct:   assumed spread (default 0.02%)
    """

    def __init__(self, slippage_pct: float = 0.0005, spread_pct: float = 0.0002):
        self.slippage_pct = slippage_pct
        self.spread_pct = spread_pct

    def fill_entry(self, plan: TradePlan, candles: List[Dict],
                   current_idx: int) -> FillResult:
        """Simulate entry fill at current candle.

        Returns:
            FillResult with filled price and fill type.
        """
        if current_idx >= len(candles):
            return FillResult(filled=False, reason="No candle data")

        candle = candles[current_idx]
        o, hi, lo, close = candle["open"], candle["high"], candle["low"], candle["close"]

        # Determine fill type from entry relative to current price
        if plan.side == "BUY":
            if plan.entry <= hi:
                # Price reached entry → MARKET or LIMIT fill
                fill_price = min(hi, plan.entry + plan.entry * self.slippage_pct)
                fill_type = FillType.MARKET if plan.entry >= lo else FillType.LIMIT
                return FillResult(
                    filled=True,
                    price=round(fill_price, 2),
                    fill_type=fill_type,
                    slippage=round(fill_price - plan.entry, 2) if fill_price > plan.entry else 0,
                )
            if plan.entry > hi:
                # Price hasn't reached entry yet → STOP entry
                return FillResult(filled=False, fill_type=FillType.STOP,
                                  reason="Entry not yet reached")

        else:  # SELL
            if plan.entry >= lo:
                fill_price = max(lo, plan.entry - plan.entry * self.slippage_pct)
                fill_type = FillType.MARKET if plan.entry <= hi else FillType.LIMIT
                return FillResult(
                    filled=True,
                    price=round(fill_price, 2),
                    fill_type=fill_type,
                    slippage=round(plan.entry - fill_price, 2) if fill_price < plan.entry else 0,
                )
            if plan.entry < lo:
                return FillResult(filled=False, fill_type=FillType.STOP,
                                  reason="Entry not yet reached")

        return FillResult(filled=False, reason="Unknown")

    def check_tp_hit(self, plan: TradePlan, candles: List[Dict],
                     idx: int, prev_idx: int) -> List[float]:
        """Check which TP levels are hit between prev_idx and idx.

        Returns:
            List of TP prices hit in order (may be empty).
        """
        if idx >= len(candles) or prev_idx >= len(candles):
            return []
        hit = []
        for i in range(prev_idx + 1, idx + 1):
            c = candles[i]
            if plan.side == "BUY":
                for tp in plan.take_profits:
                    if c["high"] >= tp and tp not in hit:
                        hit.append(tp)
            else:
                for tp in plan.take_profits:
                    if c["low"] <= tp and tp not in hit:
                        hit.append(tp)
        return hit

    def check_sl_hit(self, plan: TradePlan, candles: List[Dict],
                     idx: int, prev_idx: int) -> bool:
        """Check if stop loss is hit between prev_idx and idx."""
        if idx >= len(candles) or prev_idx >= len(candles):
            return False
        for i in range(prev_idx + 1, idx + 1):
            c = candles[i]
            if plan.side == "BUY" and c["low"] <= plan.stop_loss:
                return True
            if plan.side == "SELL" and c["high"] >= plan.stop_loss:
                return True
        return False

    def check_be_hit(self, plan: TradePlan, be_price: float,
                     candles: List[Dict], idx: int, prev_idx: int) -> bool:
        """Check if breakeven stop is hit."""
        if idx >= len(candles) or prev_idx >= len(candles):
            return False
        for i in range(prev_idx + 1, idx + 1):
            c = candles[i]
            if plan.side == "BUY" and c["low"] <= be_price:
                return True
            if plan.side == "SELL" and c["high"] >= be_price:
                return True
        return False

    def check_trailing_breach(self, plan: TradePlan, trail_stop: float,
                              candles: List[Dict], idx: int,
                              prev_idx: int) -> bool:
        """Check if trailing stop is breached."""
        return self.check_be_hit(plan, trail_stop, candles, idx, prev_idx)
