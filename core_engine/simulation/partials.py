"""Partial TP manager — tracks which TP levels have been hit and position fractions."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List

from .planner import TradePlan


@dataclass
class PartialTracker:
    """Tracks partial take-profit hits and remaining position."""

    plan: TradePlan
    remaining_ratio: float = 1.0
    tps_hit: List[float] = field(default_factory=list)
    tps_pending: List[float] = field(default_factory=list)

    def __post_init__(self):
        if not self.tps_pending:
            self.tps_pending = list(self.plan.take_profits)

    def hit(self, tp_price: float) -> float:
        """Mark a TP as hit. Returns the fraction of position closed.

        Args:
            tp_price: the TP price that was hit

        Returns:
            fraction of position closed (e.g. 0.50 for 50%)
        """
        if tp_price in self.tps_hit:
            return 0.0
        if tp_price not in self.tps_pending:
            return 0.0

        self.tps_hit.append(tp_price)
        idx = self.plan.take_profits.index(tp_price)
        fraction = self.plan.partials[idx] if idx < len(self.plan.partials) else 0.0

        self.remaining_ratio = max(0.0, self.remaining_ratio - fraction)
        if tp_price in self.tps_pending:
            self.tps_pending.remove(tp_price)

        return fraction

    @property
    def all_tps_hit(self) -> bool:
        return len(self.tps_hit) >= len(self.plan.take_profits)

    @property
    def remaining_pct(self) -> float:
        return self.remaining_ratio * 100.0
