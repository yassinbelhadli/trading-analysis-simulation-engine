"""Simulation Engine — deterministically simulates a trade against historical data.

Usage:
    from core_engine.simulation import simulate
    from core_engine.simulation import build_plan, TradePlan
    from core_engine.simulation import FillModel, TradeResult

    result = simulate(snapshot, candles)
    print(f"{result.outcome}: {result.total_r}R")
    for ev in result.events:
        print(f"  [{ev.state}] {ev.price} — {ev.description}")
"""

from .engine import simulate, simulate_from_plan, simulate_batch
from .planner import build_plan, TradePlan
from .fill_model import FillModel
from .result import TradeResult, TradeEvent, FillInfo, TradeMetrics, TradeOutcome
from .lifecycle import TradeLifecycle
from .risk import compute_position, PositionSize
from .partials import PartialTracker
from .breakeven import BreakevenManager
from .trailing import TrailingManager
from .metrics import compute_metrics

__all__ = [
    "simulate",
    "simulate_from_plan",
    "simulate_batch",
    "build_plan",
    "TradePlan",
    "FillModel",
    "TradeResult",
    "TradeEvent",
    "FillInfo",
    "TradeMetrics",
    "TradeOutcome",
    "TradeLifecycle",
    "compute_position",
    "PositionSize",
    "PartialTracker",
    "BreakevenManager",
    "TrailingManager",
    "compute_metrics",
]
