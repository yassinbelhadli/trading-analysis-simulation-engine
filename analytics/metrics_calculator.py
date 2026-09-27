"""
Trade metrics calculator.

Key conventions:
  - "win by PnL"   = realized_pnl > 0  (financial outcome)
  - "win by reason"  = close_reason == "TP_HIT"  (outcome by exit type)
  These are SEPARATE. A trade closed by SL_HIT can still be a PnL-win
  if partial profit exceeded the runner loss.
"""
from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Tuple

from database.models import PaperTrade

logger = logging.getLogger(__name__)

NATURAL_REASONS = {"TP_HIT", "SL_HIT"}


@dataclass
class TradeMetrics:
    total_trades: int = 0
    filled_trades: int = 0
    closed_trades: int = 0
    planned_trades: int = 0

    # --- Outcome by close reason (exit type) ---
    tp_count: int = 0
    sl_count: int = 0
    tp_rate: float = 0.0
    sl_rate: float = 0.0

    # --- Outcome by PnL (financial result) ---
    win_count: int = 0
    loss_count: int = 0
    win_rate: float = 0.0

    # --- PnL ---
    net_pnl: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    profit_factor: float = 0.0
    expectancy: float = 0.0
    average_win: float = 0.0
    average_loss: float = 0.0

    # --- Risk-normalized (R-multiple) ---
    avg_realized_r: float = 0.0
    avg_planned_rr: float = 0.0
    total_r: float = 0.0
    r_sample_size: int = 0
    r_excluded_be: int = 0
    r_excluded_legacy: int = 0

    # --- Timing ---
    average_trade_duration: float = 0.0
    average_fill_latency: float = 0.0

    # --- Execution quality ---
    average_mfe: float = 0.0
    average_mae: float = 0.0

    # --- Lifecycle rates ---
    partial_trigger_rate: float = 0.0
    breakeven_activation_rate: float = 0.0

    # --- Partial & runner breakdown ---
    partial_count: int = 0
    total_partial_pnl: float = 0.0
    average_partial_pnl: float = 0.0
    total_runner_pnl: float = 0.0
    average_runner_pnl: float = 0.0
    runner_win_rate: float = 0.0
    average_runner_efficiency: float = 0.0
    runner_efficiency_sample_size: int = 0
    partial_then_be_rate: float = 0.0
    partial_then_tp_rate: float = 0.0

    # --- Classification counts ---
    stale_count: int = 0
    strategic_count: int = 0


def close_category(trade: PaperTrade) -> str:
    if trade.status in ("PLANNED", "FILLED"):
        return "ACTIVE"
    if trade.status == "CLOSED":
        r = trade.close_reason
        if r in ("TP_HIT",):
            return "NATURAL_TP"
        if r in ("SL_HIT",):
            return "NATURAL_SL"
        if r == "STALE_CLEANUP" or r is None:
            return "STALE_CLEANUP"
    return "UNKNOWN"


def is_strategic(trade: PaperTrade) -> bool:
    return trade.status == "CLOSED" and trade.close_reason in NATURAL_REASONS


def _score_bucket(score: float) -> str:
    if score >= 90:
        return "90-100"
    if score >= 80:
        return "80-89"
    if score >= 70:
        return "70-79"
    if score >= 60:
        return "60-69"
    return "0-59"


def _is_win(trade: PaperTrade) -> bool:
    return trade.realized_pnl is not None and trade.realized_pnl > 0


def _is_loss(trade: PaperTrade) -> bool:
    return trade.realized_pnl is not None and trade.realized_pnl < 0


def _compute_core(closed: List[PaperTrade]) -> TradeMetrics:
    m = TradeMetrics()
    m.total_trades = len(closed)
    m.closed_trades = len(closed)

    if not closed:
        return m

    # --- Outcome by close reason ---
    tps = [t for t in closed if t.close_reason == "TP_HIT"]
    sls = [t for t in closed if t.close_reason == "SL_HIT"]
    m.tp_count = len(tps)
    m.sl_count = len(sls)
    m.tp_rate = round(len(tps) / len(closed) * 100, 2)
    m.sl_rate = round(len(sls) / len(closed) * 100, 2)

    # --- Outcome by PnL ---
    wins = [t for t in closed if _is_win(t)]
    losses = [t for t in closed if _is_loss(t)]
    m.win_count = len(wins)
    m.loss_count = len(losses)
    m.win_rate = round(len(wins) / len(closed) * 100, 2)

    # --- PnL ---
    gross_profit = sum(t.realized_pnl for t in wins)
    gross_loss = abs(sum(t.realized_pnl for t in losses))
    m.gross_profit = round(gross_profit, 2)
    m.gross_loss = round(gross_loss, 2)
    m.net_pnl = round(gross_profit - gross_loss, 2)
    m.profit_factor = round(gross_profit / gross_loss, 4) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0.0)
    m.expectancy = round(m.net_pnl / len(closed), 2)
    m.average_win = round(gross_profit / len(wins), 2) if wins else 0.0
    m.average_loss = round(gross_loss / len(losses), 2) if losses else 0.0

    # --- R-multiple ---
    r_vals = [t.realized_r for t in closed if t.realized_r is not None]
    rr_vals = [t.risk_reward for t in closed if t.risk_reward and t.risk_reward > 0]
    m.avg_realized_r = round(sum(r_vals) / len(r_vals), 2) if r_vals else 0.0
    m.avg_planned_rr = round(sum(rr_vals) / len(rr_vals), 2) if rr_vals else 0.0
    m.total_r = round(sum(r_vals), 2) if r_vals else 0.0
    m.r_sample_size = len(r_vals)
    # Excluded: trades without initial_risk_usd (entered before fix)
    m.r_excluded_be = len([t for t in closed if t.breakeven_activated and t.initial_risk_usd is None])
    m.r_excluded_legacy = len([t for t in closed if not t.breakeven_activated and t.initial_risk_usd is None])

    # --- Timing ---
    durations = [t.trade_duration_sec for t in closed if t.trade_duration_sec is not None]
    m.average_trade_duration = round(sum(durations) / len(durations), 1) if durations else 0.0

    latencies = [t.fill_latency_sec for t in closed if t.fill_latency_sec is not None]
    m.average_fill_latency = round(sum(latencies) / len(latencies), 1) if latencies else 0.0

    # --- Execution quality ---
    mfes = [t.mfe for t in closed if t.mfe is not None]
    maes = [t.mae for t in closed if t.mae is not None]
    m.average_mfe = round(sum(mfes) / len(mfes), 2) if mfes else 0.0
    m.average_mae = round(sum(maes) / len(maes), 2) if maes else 0.0

    # --- Lifecycle rates ---
    partials = [t for t in closed if t.partial_closed]
    bes = [t for t in closed if t.breakeven_activated]
    stale = [t for t in closed if close_category(t) == "STALE_CLEANUP"]
    strategic = [t for t in closed if is_strategic(t)]

    m.partial_count = len(partials)
    m.partial_trigger_rate = round(len(partials) / len(closed) * 100, 2)
    m.breakeven_activation_rate = round(len(bes) / len(closed) * 100, 2)
    m.stale_count = len(stale)
    m.strategic_count = len(strategic)

    # --- Partial & runner breakdown ---
    if partials:
        partial_pnls = [t.partial_pnl for t in partials if t.partial_pnl is not None]
        m.total_partial_pnl = round(sum(partial_pnls), 2)
        m.average_partial_pnl = round(m.total_partial_pnl / len(partials), 2)

        runner_pnls = []
        runner_wins = 0
        efficiencies = []
        for t in partials:
            if t.partial_pnl is not None and t.realized_pnl is not None:
                runner = t.realized_pnl - t.partial_pnl
                runner_pnls.append(runner)
                if runner > 0:
                    runner_wins += 1
            if t.runner_efficiency is not None:
                efficiencies.append(t.runner_efficiency)

        m.total_runner_pnl = round(sum(runner_pnls), 2) if runner_pnls else 0.0
        m.average_runner_pnl = round(sum(runner_pnls) / len(runner_pnls), 2) if runner_pnls else 0.0
        m.runner_win_rate = round(runner_wins / len(partials) * 100, 2) if partials else 0.0
        m.average_runner_efficiency = round(sum(efficiencies) / len(efficiencies), 4) if efficiencies else 0.0
        m.runner_efficiency_sample_size = len(efficiencies)

        partial_be = [t for t in partials if t.breakeven_activated]
        partial_tp = [t for t in partials if t.close_reason == "TP_HIT"]
        m.partial_then_be_rate = round(len(partial_be) / len(partials) * 100, 2)
        m.partial_then_tp_rate = round(len(partial_tp) / len(partials) * 100, 2)

    return m


def compute_metrics(trades: List[PaperTrade]) -> TradeMetrics:
    m = TradeMetrics()
    m.total_trades = len(trades)

    filled = [t for t in trades if t.status in ("FILLED", "CLOSED")]
    closed = [t for t in trades if t.status == "CLOSED"]
    planned = [t for t in trades if t.status == "PLANNED"]

    m.filled_trades = len(filled)
    m.closed_trades = len(closed)
    m.planned_trades = len(planned)

    core = _compute_core(closed)
    for k, v in asdict(core).items():
        setattr(m, k, v)
    return m


def compute_strategic_metrics(all_trades: List[PaperTrade]) -> TradeMetrics:
    strategic = [t for t in all_trades if is_strategic(t)]
    return _compute_core(strategic)


def compute_grouped(
    trades: List[PaperTrade],
    key_fn: Callable[[PaperTrade], str],
) -> Dict[str, TradeMetrics]:
    groups: Dict[str, List[PaperTrade]] = {}
    for t in trades:
        k = key_fn(t) or "UNKNOWN"
        groups.setdefault(k, []).append(t)
    return {k: compute_metrics(v) for k, v in sorted(groups.items())}


def compute_grouped_strategic(
    trades: List[PaperTrade],
    key_fn: Callable[[PaperTrade], str],
) -> Dict[str, TradeMetrics]:
    strategic = [t for t in trades if is_strategic(t)]
    return compute_grouped(strategic, key_fn)


def compute_by_category(trades: List[PaperTrade]) -> Dict[str, TradeMetrics]:
    return compute_grouped(trades, close_category)


def compute_by_symbol(trades: List[PaperTrade]) -> Dict[str, TradeMetrics]:
    return compute_grouped(trades, lambda t: t.symbol)


def compute_by_session(trades: List[PaperTrade]) -> Dict[str, TradeMetrics]:
    return compute_grouped(trades, lambda t: t.session or "UNKNOWN")


def compute_by_regime(trades: List[PaperTrade]) -> Dict[str, TradeMetrics]:
    return compute_grouped(trades, lambda t: t.market_regime or "UNKNOWN")


def compute_by_direction(trades: List[PaperTrade]) -> Dict[str, TradeMetrics]:
    return compute_grouped(trades, lambda t: t.direction)


def compute_by_score_bucket(trades: List[PaperTrade]) -> Dict[str, TradeMetrics]:
    return compute_grouped(trades, lambda t: _score_bucket(t.score))


def metrics_to_dict(m: TradeMetrics) -> dict:
    return asdict(m)


def compute_histogram(values: List[float], bins: List[float]) -> List[dict]:
    counts = [0] * (len(bins) - 1)
    for v in values:
        for i in range(len(bins) - 1):
            if bins[i] <= v < bins[i + 1]:
                counts[i] += 1
                break
    return [
        {"range": f"{bins[i]:.1f}-{bins[i+1]:.1f}", "count": counts[i]}
        for i in range(len(bins) - 1)
    ]


def compute_distributions(trades: List[PaperTrade]) -> dict:
    closed = [t for t in trades if t.status == "CLOSED"]

    mfe_vals = [t.mfe for t in closed if t.mfe is not None]
    mae_vals = [t.mae for t in closed if t.mae is not None]
    dur_vals = [t.trade_duration_sec for t in closed if t.trade_duration_sec is not None]
    lat_vals = [t.fill_latency_sec for t in closed if t.fill_latency_sec is not None]

    mfe_bins = [0, 1, 2, 5, 10, 20, 50, 100, 500]
    mae_bins = [0, 1, 2, 5, 10, 20, 50, 100, 500]
    dur_bins = [0, 5, 10, 30, 60, 300, 600, 3600, 86400]
    lat_bins = [0, 1, 5, 10, 30, 60, 300, 3600, 86400]

    return {
        "mfe_distribution": compute_histogram(mfe_vals, mfe_bins),
        "mae_distribution": compute_histogram(mae_vals, mae_bins),
        "trade_duration_distribution": compute_histogram(dur_vals, dur_bins),
        "fill_latency_distribution": compute_histogram(lat_vals, lat_bins),
    }


def compute_timeline(trades: List[PaperTrade]) -> dict:
    closed_by_hour: Dict[str, List[PaperTrade]] = {}
    for t in trades:
        if t.status != "CLOSED" or t.closed_at is None:
            continue
        key = t.closed_at.strftime("%Y-%m-%d %H:00")
        closed_by_hour.setdefault(key, []).append(t)

    hourly = []
    for key in sorted(closed_by_hour.keys()):
        group = closed_by_hour[key]
        wins = sum(1 for t in group if _is_win(t))
        losses = sum(1 for t in group if _is_loss(t))
        pnl = sum(t.realized_pnl for t in group if t.realized_pnl is not None)
        hourly.append({
            "hour": key,
            "trades": len(group),
            "wins": wins,
            "losses": losses,
            "net_pnl": round(pnl, 2),
        })

    return {"hourly": hourly}
