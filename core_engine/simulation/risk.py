"""Risk calculator — position sizing from TradePlan.

Determines lot size / units based on:
    - Account balance
    - Risk percent
    - Stop distance
    - Instrument value
"""

from __future__ import annotations
from dataclasses import dataclass

from .planner import TradePlan


@dataclass(frozen=True)
class PositionSize:
    units: float             # number of units / contracts
    risk_amount: float       # account currency at risk
    risk_pct: float          # actual risk % of balance
    max_loss: float          # max loss if SL hit


def _resolve_risk_distance(plan: TradePlan) -> float:
    """Extract risk_distance from any TradePlan variant."""
    if hasattr(plan, 'risk_distance'):
        return plan.risk_distance
    entry = getattr(plan, 'entry', None) or getattr(plan, 'entry_price', 0)
    sl = getattr(plan, 'stop_loss', 0)
    return abs(entry - sl) if entry and sl else 0


def _resolve_risk_percent(plan: TradePlan) -> float:
    """Extract risk_percent from any TradePlan variant."""
    return getattr(plan, 'risk_percent', 0.5) or 0.5


def compute_position(plan: TradePlan, account_balance: float,
                     instrument_value: float = 1.0) -> PositionSize:
    """Compute position size from TradePlan.

    Works with both simulation.TradePlan and execution.trade_planner.TradePlan.

    Args:
        plan: TradePlan with entry, SL, risk_percent
        account_balance: current account balance
        instrument_value: pip/point value per unit (1.0 for crypto,
                         0.0001 for FX, etc.)

    Returns:
        PositionSize with calculated units and risk amounts.
    """
    risk_amount = account_balance * (_resolve_risk_percent(plan) / 100.0)
    risk_distance = _resolve_risk_distance(plan)

    if risk_distance == 0 or instrument_value == 0:
        return PositionSize(units=0, risk_amount=0, risk_pct=0, max_loss=0)

    units = risk_amount / (risk_distance * instrument_value)
    units = round(units, 2)

    max_loss = units * risk_distance * instrument_value
    actual_risk_pct = (max_loss / account_balance * 100) if account_balance else 0

    return PositionSize(
        units=units,
        risk_amount=round(risk_amount, 2),
        risk_pct=round(actual_risk_pct, 4),
        max_loss=round(max_loss, 2),
    )
