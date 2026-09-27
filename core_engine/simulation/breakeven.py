"""Breakeven — moves SL to entry after first TP is hit."""

from __future__ import annotations
from dataclasses import dataclass

from .planner import TradePlan


@dataclass
class BreakevenManager:
    """Manages breakeven stop logic.

    Moves SL to entry + buffer when the first TP is hit.
    """

    active: bool = False
    be_price: float = 0.0
    buffer: float = 0.0   # positive buffer above entry (BUY) or below (SELL)

    def check_and_activate(self, plan: TradePlan, current_price: float) -> bool:
        """Check if breakeven should activate.

        Activates when price reaches the first TP level.

        Returns:
            True if BE was just activated
        """
        if self.active:
            return False

        first_tp = plan.take_profits[0] if plan.take_profits else None
        if first_tp is None:
            return False

        if plan.side == "BUY" and current_price >= first_tp:
            self.active = True
            self.be_price = plan.entry + self.buffer
            return True
        elif plan.side == "SELL" and current_price <= first_tp:
            self.active = True
            self.be_price = plan.entry - self.buffer
            return True

        return False
