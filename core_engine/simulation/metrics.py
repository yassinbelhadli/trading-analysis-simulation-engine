"""Trade metrics — computes MFE, MAE, duration, drawdown from trade events + candle data."""

from __future__ import annotations
from typing import List, Optional

from .planner import TradePlan
from .result import TradeResult, TradeEvent, TradeMetrics, FillInfo, TradeOutcome


def compute_metrics(plan: TradePlan, result: TradeResult,
                    candles: List[Dict]) -> TradeMetrics:
    """Compute detailed trade metrics from result + candle data.

    Args:
        plan: original TradePlan
        result: TradeResult from simulation
        candles: full candle list

    Returns:
        TradeMetrics with MFE, MAE, duration, drawdown, etc.
    """
    entry_idx = _find_entry_candle(candles, result)
    exit_idx = _find_exit_candle(candles, result)

    if entry_idx is None or exit_idx is None or entry_idx >= exit_idx:
        return TradeMetrics(
            total_pnl=result.total_pnl,
            total_r=result.total_r,
        )

    entry_price = result.fill.price if result.fill else plan.entry

    # Compute MFE / MAE from candle extremes
    if plan.side == "BUY":
        max_price = max(c["high"] for c in candles[entry_idx:exit_idx + 1])
        min_price = min(c["low"] for c in candles[entry_idx:exit_idx + 1])
        mfe = (max_price - entry_price) / plan.risk_distance if plan.risk_distance else 0
        mae = (entry_price - min_price) / plan.risk_distance if plan.risk_distance else 0
        max_dd = (entry_price - min_price) / entry_price * 100 if entry_price else 0
    else:
        max_price = max(c["high"] for c in candles[entry_idx:exit_idx + 1])
        min_price = min(c["low"] for c in candles[entry_idx:exit_idx + 1])
        mfe = (entry_price - min_price) / plan.risk_distance if plan.risk_distance else 0
        mae = (max_price - entry_price) / plan.risk_distance if plan.risk_distance else 0
        max_dd = (max_price - entry_price) / entry_price * 100 if entry_price else 0

    duration = exit_idx - entry_idx

    return TradeMetrics(
        total_pnl=result.total_pnl,
        total_r=result.total_r,
        duration_candles=duration,
        max_adverse_excursion=round(mae, 2),
        max_favorable_excursion=round(mfe, 2),
        max_drawdown_pct=round(max_dd, 2),
    )


def _find_entry_candle(candles: List[Dict], result: TradeResult) -> Optional[int]:
    if result.fill is None or not result.events:
        return 0
    for i, c in enumerate(candles):
        if str(c.get("time", "")) == result.fill.time:
            return i
    # Fallback: first event time
    for i, c in enumerate(candles):
        if str(c.get("time", "")) == result.events[0].time:
            return i
    return 0


def _find_exit_candle(candles: List[Dict], result: TradeResult) -> Optional[int]:
    if not result.events:
        return len(candles) - 1
    last_ev = result.events[-1]
    for i, c in enumerate(candles):
        if str(c.get("time", "")) == last_ev.time:
            return i
    return len(candles) - 1
