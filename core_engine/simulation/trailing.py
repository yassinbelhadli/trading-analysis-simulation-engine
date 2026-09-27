"""Trailing stop — dynamically adjusts SL as price moves favourably."""

from __future__ import annotations
from dataclasses import dataclass

from .planner import TradePlan


@dataclass
class TrailingManager:
    """Manages trailing stop logic.

    Activates after a configurable TP level (default: after TP2).
    Trail distance can be fixed (R multiple) or ATR-based.
    """

    active: bool = False
    trail_distance_r: float = 0.5   # trail by 0.5R
    trail_highest: float = 0.0      # highest price seen (BUY)
    trail_lowest: float = float("inf")  # lowest price seen (SELL)
    current_stop: float = 0.0

    def update(self, plan: TradePlan, current_price: float,
               current_high: float, current_low: float):
        """Update trail levels from new candle.

        Must be called every candle while trailing is active.
        """
        if not self.active:
            return

        risk = plan.risk_distance

        if plan.side == "BUY":
            self.trail_highest = max(self.trail_highest, current_high)
            self.current_stop = self.trail_highest - risk * self.trail_distance_r
            # Never move below entry
            self.current_stop = max(self.current_stop, plan.entry)
        else:
            self.trail_lowest = min(self.trail_lowest, current_low)
            self.current_stop = self.trail_lowest + risk * self.trail_distance_r
            self.current_stop = min(self.current_stop, plan.entry)

    def activate(self, plan: TradePlan, current_price: float,
                 initial_stop: float) -> bool:
        """Activate trailing. Sets initial trail levels.

        Args:
            plan: TradePlan
            current_price: current market price
            initial_stop: the SL at time of activation (usually BE price)

        Returns:
            True if activation succeeded
        """
        if self.active:
            return False
        self.active = True
        if plan.side == "BUY":
            self.trail_highest = max(current_price, plan.entry)
            self.current_stop = max(initial_stop, plan.entry)
        else:
            self.trail_lowest = min(current_price, plan.entry)
            self.current_stop = min(initial_stop, plan.entry)
        return True
