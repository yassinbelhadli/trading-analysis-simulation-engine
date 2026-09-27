from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import pandas as pd
import numpy as np

from core_engine.backtesting.simulator import simulate_trade, SimulatedTrade
from core_engine.backtesting.statistics import compute_stats, BacktestStats


@dataclass
class ModeConfig:
    name: str
    label: str
    min_score: float
    max_trades_per_day: int
    min_rr: float
    sessions: List[str]


MODES = [
    ModeConfig("ULTRA_CONSERVATIVE", "Ultra Conservative", 85, 2, 2.0, ["LONDON", "NEW_YORK"]),
    ModeConfig("CONSERVATIVE",       "Conservative",       75, 3, 1.8, ["LONDON", "NEW_YORK"]),
    ModeConfig("BALANCED",           "Balanced",           65, 5, 1.5, ["LONDON", "NEW_YORK"]),
    ModeConfig("AGGRESSIVE",         "Aggressive",         50, 10, 1.5, ["LONDON", "NEW_YORK"]),
]


def extract_entry_sl_tp(row: pd.Series, min_rr: float) -> Optional[Tuple[str, float, float, float, float]]:
    """Extract direction, entry, SL, TP, and RR from a detection row.
    Follows logic similar to TradePlanner.
    """
    direction = None
    entry_price = None
    stop_loss = None

    trend = str(row.get("Market_Trend", "NEUTRAL"))
    mss_type = str(row.get("MSS_Type", ""))
    choch_type = str(row.get("CHoCH_Type", ""))
    bos_type = str(row.get("BOS_Type", ""))

    if "Bullish" in mss_type or "Bullish" in choch_type or "Bullish" in bos_type:
        direction = "BUY"
    elif "Bearish" in mss_type or "Bearish" in choch_type or "Bearish" in bos_type:
        direction = "SELL"
    elif "BULLISH" in trend:
        direction = "BUY"
    elif "BEARISH" in trend:
        direction = "SELL"
    else:
        return None

    bid = float(row.get("Close", row.get("Bid", 0)))
    ask = float(row.get("Close", row.get("Ask", 0)))

    bullish_ob = bool(row.get("Bullish_OB", False))
    bearish_ob = bool(row.get("Bearish_OB", False))
    bullish_fvg = bool(row.get("Bullish_FVG", False))
    bearish_fvg = bool(row.get("Bearish_FVG", False))
    ob_mitigated = bool(row.get("OB_Mitigated", False))
    fvg_mitigated = bool(row.get("FVG_Mitigated", False))

    if direction == "BUY":
        if bullish_ob and not ob_mitigated:
            ob_top = float(row["OB_Upper"]) if pd.notna(row.get("OB_Upper")) else None
            ob_bottom = float(row["OB_Lower"]) if pd.notna(row.get("OB_Lower")) else None
            if ob_bottom is not None and ob_top is not None:
                entry_price = (ob_top + ob_bottom) / 2
                stop_loss = ob_bottom
        if entry_price is None and bullish_fvg and not fvg_mitigated:
            fvg_top = float(row["FVG_Upper"]) if pd.notna(row.get("FVG_Upper")) else None
            fvg_bottom = float(row["FVG_Lower"]) if pd.notna(row.get("FVG_Lower")) else None
            if fvg_top is not None and fvg_bottom is not None:
                entry_price = (fvg_top + fvg_bottom) / 2
                stop_loss = fvg_bottom
        if entry_price is None:
            protected_low = float(row["Protected_Low_Level"]) if pd.notna(row.get("Protected_Low_Level")) else None
            if protected_low is not None:
                entry_price = ask if ask > 0 else bid
                stop_loss = protected_low
            else:
                entry_price = ask if ask > 0 else bid
                stop_loss = entry_price * 0.995

    else:
        if bearish_ob and not ob_mitigated:
            ob_top = float(row["OB_Upper"]) if pd.notna(row.get("OB_Upper")) else None
            ob_bottom = float(row["OB_Lower"]) if pd.notna(row.get("OB_Lower")) else None
            if ob_bottom is not None and ob_top is not None:
                entry_price = (ob_top + ob_bottom) / 2
                stop_loss = ob_top
        if entry_price is None and bearish_fvg and not fvg_mitigated:
            fvg_top = float(row["FVG_Upper"]) if pd.notna(row.get("FVG_Upper")) else None
            fvg_bottom = float(row["FVG_Lower"]) if pd.notna(row.get("FVG_Lower")) else None
            if fvg_top is not None and fvg_bottom is not None:
                entry_price = (fvg_top + fvg_bottom) / 2
                stop_loss = fvg_top
        if entry_price is None:
            protected_high = float(row["Protected_High_Level"]) if pd.notna(row.get("Protected_High_Level")) else None
            if protected_high is not None:
                entry_price = bid if bid > 0 else ask
                stop_loss = protected_high
            else:
                entry_price = bid if bid > 0 else ask
                stop_loss = entry_price * 1.005

    if entry_price is None or stop_loss is None or abs(entry_price - stop_loss) < 0.0001:
        return None

    risk = abs(entry_price - stop_loss)
    rr = min_rr
    if direction == "BUY":
        take_profit = entry_price + risk * rr
    else:
        take_profit = entry_price - risk * rr

    actual_rr = abs(take_profit - entry_price) / risk if risk > 0 else 0

    return (direction, entry_price, stop_loss, take_profit, actual_rr)


class Backtester:
    def __init__(self, account_balance: float = 10000.0, risk_per_trade: float = 0.005):
        self.account_balance = account_balance
        self.risk_per_trade = risk_per_trade

    def calculate_lot(self, risk_amount: float, stop_loss: float, entry_price: float, symbol: str) -> float:
        cs = {"XAUUSD": 100, "USTEC": 100, "BTCUSD": 1}.get(symbol, 100)
        sl_points = abs(entry_price - stop_loss)
        if sl_points <= 0:
            return 0.01
        money_per_lot = cs * sl_points
        if money_per_lot <= 0:
            return 0.01
        lot = risk_amount / money_per_lot
        return round(max(0.01, min(lot, 10.0)), 2)

    def run_mode(
        self,
        df: pd.DataFrame,
        mode: ModeConfig,
        symbol: str,
    ) -> List[SimulatedTrade]:
        trades: List[SimulatedTrade] = []
        daily_count: Dict[str, int] = {}
        risk_per_trade = self.account_balance * self.risk_per_trade

        session_ok = (
            (df["Session_Trade_Allowed"] == True)
            | (df["London_Trade_Allowed"] == True)
            | (df["NewYork_Trade_Allowed"] == True)
        )

        candidates = df[
            (df["Confidence_Approved"] == True)
            & session_ok
            & (df["Weekend_Trade_Allowed"] == True)
            & (df["Setup_Score"] >= mode.min_score)
        ].copy()

        candidates = candidates.sort_index()

        for idx, row in candidates.iterrows():
            day_key = str(idx.date())
            if daily_count.get(day_key, 0) >= mode.max_trades_per_day:
                continue

            result = extract_entry_sl_tp(row, mode.min_rr)
            if result is None:
                continue

            direction, entry_price, stop_loss, take_profit, actual_rr = result

            setup_score = float(row.get("Setup_Score", 0))
            confidence = float(row.get("Confidence_Score", 0))

            lot = self.calculate_lot(risk_per_trade, stop_loss, entry_price, symbol)

            future = df[df.index > idx]
            if len(future) < 5:
                continue

            trade = simulate_trade(
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                direction=direction,
                lot_size=lot,
                symbol=symbol,
                setup_score=setup_score,
                confidence_score=confidence,
                risk_amount=risk_per_trade,
                open_time=idx,
                future_candles=future,
            )

            daily_count[day_key] = daily_count.get(day_key, 0) + 1
            trades.append(trade)

        return trades

    @staticmethod
    def print_summary(all_stats: List[BacktestStats]):
        print(f"\n{'='*90}")
        print(f"{'Symbol':15} {'Mode':22} {'Trades':7} {'WR%':7} {'PF':7} {'Net PnL':10} {'Exp':9} {'AvgRR':7} {'MaxLoss':8}")
        print(f"{'='*90}")
        for s in all_stats:
            if s.total_trades == 0:
                continue
            print(f"{s.symbol:15} {s.mode:22} {s.total_trades:7} {s.win_rate:6}% {s.profit_factor:6} {s.net_pnl:9.2f} {s.expectancy:8.2f} {s.avg_rr:6} {s.max_consecutive_losses:7}")
        print(f"{'='*90}")
