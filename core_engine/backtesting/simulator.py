from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import pandas as pd


@dataclass
class SimulatedTrade:
    symbol: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_amount: float
    lot_size: float
    setup_score: float
    confidence_score: float
    open_time: pd.Timestamp
    close_time: Optional[pd.Timestamp] = None
    close_price: Optional[float] = None
    status: str = "OPEN"
    close_reason: str = ""
    pnl: float = 0.0
    partial_pnl: float = 0.0
    total_pnl: float = 0.0
    be_moved: bool = False
    partial_closed: bool = False
    max_adverse: float = 0.0
    max_favorable: float = 0.0
    candles_held: int = 0


CONTRACT_SIZES = {"XAUUSD": 100, "USTEC": 100, "BTCUSD": 1}


def _pnl(lot: float, contract_size: float, price_diff: float) -> float:
    return lot * contract_size * price_diff


def simulate_trade(
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    direction: str,
    lot_size: float,
    symbol: str,
    setup_score: float,
    confidence_score: float,
    risk_amount: float,
    open_time: pd.Timestamp,
    future_candles: pd.DataFrame,
    max_candles: int = 200,
) -> SimulatedTrade:
    cs = CONTRACT_SIZES.get(symbol, 100)
    risk = abs(entry_price - stop_loss)
    if risk <= 0:
        risk = 0.01

    be_moved = False
    partial_done = False
    partial_pnl = 0.0
    current_sl = stop_loss
    max_adverse = 0.0
    max_favorable = 0.0
    candles_held = 0

    trade = SimulatedTrade(
        symbol=symbol, direction=direction,
        entry_price=entry_price, stop_loss=stop_loss,
        take_profit=take_profit,
        risk_amount=risk_amount,
        lot_size=lot_size,
        setup_score=setup_score,
        confidence_score=confidence_score,
        open_time=open_time,
    )

    for ts, candle in future_candles.head(max_candles).iterrows():
        high = float(candle["High"])
        low = float(candle["Low"])
        close = float(candle["Close"])
        candles_held += 1

        if direction == "BUY":
            r_multiple = (close - entry_price) / risk
            peak = max(high, close) - entry_price
            trough = entry_price - min(low, close)
            max_favorable = max(max_favorable, peak)
            max_adverse = max(max_adverse, trough)

            if not be_moved and r_multiple >= 1.0:
                be_moved = True
                current_sl = entry_price

            if not partial_done and r_multiple >= 0.75:
                partial_done = True
                partial_pnl = _pnl(lot_size * 0.5, cs, close - entry_price)

            if high >= take_profit:
                trade.close_time = ts
                trade.close_price = take_profit
                trade.status = "TP_HIT"
                trade.close_reason = "TP_HIT"
                trade.pnl = _pnl(lot_size, cs, take_profit - entry_price)
                trade.partial_pnl = partial_pnl
                trade.total_pnl = trade.pnl + trade.partial_pnl
                trade.be_moved = be_moved
                trade.partial_closed = partial_done
                trade.max_adverse = max_adverse
                trade.max_favorable = max_favorable
                trade.candles_held = candles_held
                return trade

            if low <= current_sl:
                trade.close_time = ts
                trade.close_price = current_sl
                trade.status = "SL_HIT"
                trade.close_reason = "SL_HIT"
                trade.pnl = _pnl(lot_size, cs, current_sl - entry_price)
                trade.partial_pnl = partial_pnl
                trade.total_pnl = trade.pnl + trade.partial_pnl
                trade.be_moved = be_moved
                trade.partial_closed = partial_done
                trade.max_adverse = max_adverse
                trade.max_favorable = max_favorable
                trade.candles_held = candles_held
                return trade

        else:
            r_multiple = (entry_price - close) / risk
            peak = entry_price - min(low, close)
            trough = max(high, close) - entry_price
            max_favorable = max(max_favorable, peak)
            max_adverse = max(max_adverse, trough)

            if not be_moved and r_multiple >= 1.0:
                be_moved = True
                current_sl = entry_price

            if not partial_done and r_multiple >= 0.75:
                partial_done = True
                partial_pnl = _pnl(lot_size * 0.5, cs, entry_price - close)

            if low <= take_profit:
                trade.close_time = ts
                trade.close_price = take_profit
                trade.status = "TP_HIT"
                trade.close_reason = "TP_HIT"
                trade.pnl = _pnl(lot_size, cs, entry_price - take_profit)
                trade.partial_pnl = partial_pnl
                trade.total_pnl = trade.pnl + trade.partial_pnl
                trade.be_moved = be_moved
                trade.partial_closed = partial_done
                trade.max_adverse = max_adverse
                trade.max_favorable = max_favorable
                trade.candles_held = candles_held
                return trade

            if high >= current_sl:
                trade.close_time = ts
                trade.close_price = current_sl
                trade.status = "SL_HIT"
                trade.close_reason = "SL_HIT"
                trade.pnl = _pnl(lot_size, cs, entry_price - current_sl)
                trade.partial_pnl = partial_pnl
                trade.total_pnl = trade.pnl + trade.partial_pnl
                trade.be_moved = be_moved
                trade.partial_closed = partial_done
                trade.max_adverse = max_adverse
                trade.max_favorable = max_favorable
                trade.candles_held = candles_held
                return trade

    trade.close_time = future_candles.index[-1] if len(future_candles) > 0 else None
    trade.status = "OPEN"
    trade.close_reason = "TIMEOUT"
    trade.total_pnl = trade.pnl + trade.partial_pnl
    trade.be_moved = be_moved
    trade.partial_closed = partial_done
    trade.max_adverse = max_adverse
    trade.max_favorable = max_favorable
    trade.candles_held = candles_held
    return trade
