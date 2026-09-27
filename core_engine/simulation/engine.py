"""Simulation Engine — runs a single trade simulation against historical candle data.

Pipeline:
    Snapshot → TradePlan → Fill → Lifecycle → TradeResult + Metrics

No random numbers. Deterministic for a given snapshot + candle history.
"""

from __future__ import annotations
from typing import Dict, List, Optional, Tuple

from .planner import build_plan, TradePlan
from .fill_model import FillModel
from .lifecycle import TradeLifecycle
from .result import TradeResult, TradeEvent, FillInfo, TradeOutcome, TradeMetrics
from .metrics import compute_metrics
from .risk import compute_position, PositionSize


def simulate(
    snapshot: Dict,
    candles: List[Dict],
    fill_model: Optional[FillModel] = None,
    account_balance: float = 10000.0,
    max_lookahead: int = 100,
    entry_idx: int = None,
) -> TradeResult:
    """Run trade simulation from a single snapshot.

    Args:
        snapshot: detection snapshot dict
        candles: full OHLC list (used for price action after entry)
        fill_model: custom fill model (default: ideal with 0.05% slippage)
        account_balance: account balance for position sizing
        max_lookahead: max candles to simulate after entry
        entry_idx: explicit candle index for entry attempt.
                   If None, scans the last two candles.

    Returns:
        TradeResult — deterministic, structured, event-logged
    """
    # 1. Build TradePlan
    plan = build_plan(snapshot)
    if plan.entry == 0 or plan.stop_loss == 0:
        return _empty_result("Invalid plan: missing entry or SL")

    # 2. Find entry candle
    fill = fill_model or FillModel()
    lc = TradeLifecycle(plan, fill)
    if entry_idx is not None:
        entry_idx = entry_idx
    else:
        entry_idx = _find_entry_candle(plan, candles)

    if entry_idx is None:
        return _empty_result("Entry candle not found")

    # 3. Attempt fill
    start_result = lc.start(candles, entry_idx)
    if lc.state == "PENDING":
        return _empty_result(f"Entry not filled (plan={plan.entry})")

    # 4. Run lifecycle
    end_idx = min(len(candles) - 1, entry_idx + max_lookahead)
    for i in range(entry_idx + 1, end_idx + 1):
        step_result = lc.step(candles, i)
        if step_result.done:
            break

    # 5. Build result
    outcome = _determine_outcome(lc.state, lc.total_r)
    events = _clean_events(lc.events)

    fill_info = FillInfo(
        price=lc.fill_info.price if lc.fill_info else plan.entry,
        time=events[0].time if events else "",
        fill_type=lc.fill_info.fill_type if lc.fill_info else "MARKET",
        slippage=lc.fill_info.slippage if lc.fill_info else 0,
    ) if lc.fill_info else None

    result = TradeResult(
        outcome=outcome,
        total_r=round(lc.total_r, 2),
        total_pnl=round(lc.total_pnl, 2),
        events=events,
        fill=fill_info,
    )

    # 6. Compute metrics
    metrics = compute_metrics(plan, result, candles)
    object.__setattr__(result, "metrics", metrics)

    return result


def simulate_from_plan(
    plan: TradePlan,
    candles: List[Dict],
    fill_model: Optional[FillModel] = None,
    max_lookahead: int = 100,
) -> TradeResult:
    """Simulate from an existing TradePlan (bypasses planner)."""
    fill = fill_model or FillModel()
    lc = TradeLifecycle(plan, fill)
    entry_idx = _find_entry_candle(plan, candles)

    if entry_idx is None:
        return _empty_result("Entry candle not found")

    start_result = lc.start(candles, entry_idx)
    if lc.state == "PENDING":
        return _empty_result(f"Entry not filled (plan={plan.entry})")

    end_idx = min(len(candles) - 1, entry_idx + max_lookahead)
    for i in range(entry_idx + 1, end_idx + 1):
        step_result = lc.step(candles, i)
        if step_result.done:
            break

    outcome = _determine_outcome(lc.state, lc.total_r)
    events = _clean_events(lc.events)

    fill_info = FillInfo(
        price=lc.fill_info.price if lc.fill_info else plan.entry,
        time=events[0].time if events else "",
        fill_type=lc.fill_info.fill_type if lc.fill_info else "MARKET",
    ) if lc.fill_info else None

    result = TradeResult(
        outcome=outcome,
        total_r=round(lc.total_r, 2),
        total_pnl=round(lc.total_pnl, 2),
        events=events,
        fill=fill_info,
    )

    metrics = compute_metrics(plan, result, candles)
    object.__setattr__(result, "metrics", metrics)
    return result


# ── Batch simulation ────────────────────────────────────────────

def simulate_batch(
    snapshots: List[Dict],
    candles_list: List[List[Dict]],
    account_balance: float = 10000.0,
) -> List[TradeResult]:
    """Run multiple simulations in sequence.

    Args:
        snapshots: list of snapshot dicts (one per trade)
        candles_list: matching candle lists for each trade
        account_balance: starting balance

    Returns:
        List of TradeResult
    """
    results = []
    balance = account_balance
    for snap, candles in zip(snapshots, candles_list):
        result = simulate(snap, candles, account_balance=balance)
        results.append(result)
        balance += result.total_pnl
    return results


# ── Helpers ──────────────────────────────────────────────────────

def _find_entry_candle(plan: TradePlan, candles: List[Dict]) -> Optional[int]:
    """Find the earliest candle where entry price can be filled.

    Scans forward to find the first candle where price reaches the
    entry level.  The caller may override by passing entry_idx directly.
    """
    if not candles:
        return None
    # Scan forward: find the first candle where entry is reachable
    for i in range(len(candles) - 2, len(candles)):
        c = candles[i]
        if plan.side == "BUY" and c["high"] >= plan.entry:
            return i
        if plan.side == "SELL" and c["low"] <= plan.entry:
            return i
    # Fallback: use the candle before last (detection point)
    return max(0, len(candles) - 2)


def _determine_outcome(state: str, total_r: float = 0.0) -> str:
    if state == "STOPPED":
        return TradeOutcome.WIN if total_r > 0 else TradeOutcome.LOSS
    if state == "CLOSED":
        return TradeOutcome.WIN if total_r >= 0 else TradeOutcome.LOSS
    if state in ("TP1_HIT", "TP2_HIT", "TP3_HIT", "BE_SET", "TRAILING"):
        return TradeOutcome.WIN if total_r >= 0 else TradeOutcome.LOSS
    if state == "PENDING":
        return TradeOutcome.PENDING
    return TradeOutcome.ERROR


def _clean_events(events: List[TradeEvent]) -> List[TradeEvent]:
    """Deduplicate consecutive events with same state."""
    cleaned = []
    for ev in events:
        if cleaned and cleaned[-1].state == ev.state:
            continue
        cleaned.append(ev)
    return cleaned


def _empty_result(reason: str) -> TradeResult:
    return TradeResult(
        outcome=TradeOutcome.ERROR,
        total_r=0.0,
        total_pnl=0.0,
        events=[],
        error=reason,
    )
