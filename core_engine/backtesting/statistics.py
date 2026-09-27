from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from core_engine.backtesting.simulator import SimulatedTrade


@dataclass
class BacktestStats:
    mode: str
    symbol: str
    total_trades: int
    wins: int
    losses: int
    be_trades: int
    open_trades: int
    partial_closed: int
    win_rate: float
    loss_rate: float
    be_rate: float
    gross_profit: float
    gross_loss: float
    net_pnl: float
    profit_factor: float
    expectancy: float
    avg_rr: float
    avg_win_rr: float
    avg_loss_rr: float
    avg_win_pnl: float
    avg_loss_pnl: float
    avg_candles_held: float
    max_adverse_mean: float
    max_favorable_mean: float
    max_consecutive_losses: int
    max_consecutive_wins: int
    total_days: int
    trades_per_day: float


def compute_stats(trades: List[SimulatedTrade], mode: str, symbol: str) -> BacktestStats:
    total = len(trades)
    if total == 0:
        return BacktestStats(mode=mode, symbol=symbol, total_trades=0, wins=0, losses=0,
                             be_trades=0, open_trades=0, partial_closed=0, win_rate=0,
                             loss_rate=0, be_rate=0, gross_profit=0, gross_loss=0,
                             net_pnl=0, profit_factor=0, expectancy=0, avg_rr=0,
                             avg_win_rr=0, avg_loss_rr=0, avg_win_pnl=0, avg_loss_pnl=0,
                             avg_candles_held=0, max_adverse_mean=0, max_favorable_mean=0,
                             max_consecutive_losses=0, max_consecutive_wins=0,
                             total_days=0, trades_per_day=0)

    wins = [t for t in trades if t.status == "TP_HIT"]
    losses = [t for t in trades if t.status == "SL_HIT"]
    be_trades_list = [t for t in trades if t.status == "TP_HIT" and t.be_moved and t.pnl <= 0.5]
    open_list = [t for t in trades if t.status == "OPEN"]

    win_count = len(wins)
    loss_count = len(losses)
    be_count = len(be_trades_list)
    open_count = len(open_list)
    partial_count = sum(1 for t in trades if t.partial_closed)

    win_rate = (win_count / total) * 100 if total > 0 else 0
    loss_rate = (loss_count / total) * 100 if total > 0 else 0
    be_rate_actual = (be_count / total) * 100 if total > 0 else 0

    gross_profit = sum(t.total_pnl for t in wins)
    gross_loss_val = abs(sum(t.total_pnl for t in losses))
    net_pnl = sum(t.total_pnl for t in trades)

    profit_factor = gross_profit / gross_loss_val if gross_loss_val > 0 else (float("inf") if gross_profit > 0 else 0)
    expectancy = net_pnl / total if total > 0 else 0

    rr_values = [abs(t.take_profit - t.entry_price) / abs(t.entry_price - t.stop_loss)
                 for t in trades if abs(t.entry_price - t.stop_loss) > 0]
    avg_rr = float(np.mean(rr_values)) if rr_values else 0

    avg_win_rr = float(np.mean([abs(t.take_profit - t.entry_price) / abs(t.entry_price - t.stop_loss)
                                for t in wins if abs(t.entry_price - t.stop_loss) > 0])) if wins else 0
    avg_loss_rr = float(np.mean([abs(t.take_profit - t.entry_price) / abs(t.entry_price - t.stop_loss)
                                 for t in losses if abs(t.entry_price - t.stop_loss) > 0])) if losses else 0

    avg_win_pnl = float(np.mean([t.total_pnl for t in wins])) if wins else 0
    avg_loss_pnl = float(np.mean([t.total_pnl for t in losses])) if losses else 0

    avg_candles = float(np.mean([t.candles_held for t in trades])) if trades else 0
    avg_adverse = float(np.mean([t.max_adverse for t in trades])) if trades else 0
    avg_favorable = float(np.mean([t.max_favorable for t in trades])) if trades else 0

    max_consecutive_losses = 0
    max_consecutive_wins = 0
    current_losses = 0
    current_wins = 0
    for t in trades:
        if t.status == "TP_HIT":
            current_wins += 1
            current_losses = 0
            max_consecutive_wins = max(max_consecutive_wins, current_wins)
        elif t.status == "SL_HIT":
            current_losses += 1
            current_wins = 0
            max_consecutive_losses = max(max_consecutive_losses, current_losses)

    unique_days = len(set(t.open_time.date() for t in trades))
    tpd = total / unique_days if unique_days > 0 else 0

    return BacktestStats(
        mode=mode, symbol=symbol, total_trades=total,
        wins=win_count, losses=loss_count, be_trades=be_count,
        open_trades=open_count, partial_closed=partial_count,
        win_rate=round(win_rate, 2), loss_rate=round(loss_rate, 2),
        be_rate=round(be_rate_actual, 2),
        gross_profit=round(gross_profit, 2), gross_loss=round(gross_loss_val, 2),
        net_pnl=round(net_pnl, 2),
        profit_factor=round(profit_factor, 2) if profit_factor != float("inf") else 999.99,
        expectancy=round(expectancy, 2),
        avg_rr=round(avg_rr, 2), avg_win_rr=round(avg_win_rr, 2),
        avg_loss_rr=round(avg_loss_rr, 2),
        avg_win_pnl=round(avg_win_pnl, 2), avg_loss_pnl=round(avg_loss_pnl, 2),
        avg_candles_held=round(avg_candles, 1),
        max_adverse_mean=round(avg_adverse, 2),
        max_favorable_mean=round(avg_favorable, 2),
        max_consecutive_losses=max_consecutive_losses,
        max_consecutive_wins=max_consecutive_wins,
        total_days=unique_days,
        trades_per_day=round(tpd, 2),
    )
