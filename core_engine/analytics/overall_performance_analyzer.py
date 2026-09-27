# overall_performance_analyzer.py
from dataclasses import dataclass, asdict
from typing import Dict, Any
import pandas as pd
import numpy as np


@dataclass
class OverallPerformanceSummary:
    total_days: int
    total_trades: int
    tp_wins: int
    be_trades: int
    real_losses: int
    partial_closed: int
    be_moved: int
    closed_pnl: float
    partial_pnl: float
    net_pnl: float
    avg_net_pnl_per_trade: float
    avg_net_pnl_per_day: float
    real_winrate: float
    be_rate: float
    loss_rate: float
    profit_factor: float
    expectancy: float
    performance_state: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class OverallPerformanceAnalyzer:
    def analyze(self, daily_df: pd.DataFrame) -> Dict[str, Any]:
        if daily_df is None or len(daily_df) == 0:
            return {}

        df = daily_df.copy()

        required_cols = [
            "trades_count",
            "tp_wins",
            "be_trades",
            "real_losses",
            "partial_closed",
            "be_moved",
            "closed_pnl",
            "partial_pnl",
            "net_pnl",
        ]

        for col in required_cols:
            if col not in df.columns:
                df[col] = 0

        total_days = len(df)
        total_trades = int(df["trades_count"].sum())

        tp_wins = int(df["tp_wins"].sum())
        be_trades = int(df["be_trades"].sum())
        real_losses = int(df["real_losses"].sum())
        partial_closed = int(df["partial_closed"].sum())
        be_moved = int(df["be_moved"].sum())

        closed_pnl = float(df["closed_pnl"].sum())
        partial_pnl = float(df["partial_pnl"].sum())
        net_pnl = float(df["net_pnl"].sum())

        avg_net_pnl_per_trade = net_pnl / total_trades if total_trades > 0 else 0.0
        avg_net_pnl_per_day = net_pnl / total_days if total_days > 0 else 0.0

        real_winrate = (tp_wins / total_trades) * 100 if total_trades > 0 else 0.0
        be_rate = (be_trades / total_trades) * 100 if total_trades > 0 else 0.0
        loss_rate = (real_losses / total_trades) * 100 if total_trades > 0 else 0.0

        gross_profit = float(df[df["net_pnl"] > 0]["net_pnl"].sum())
        gross_loss = abs(float(df[df["net_pnl"] < 0]["net_pnl"].sum()))

        if gross_loss > 0:
            profit_factor = gross_profit / gross_loss
        else:
            profit_factor = np.inf if gross_profit > 0 else 0.0

        expectancy = avg_net_pnl_per_trade

        state = self._performance_state(
            total_trades=total_trades,
            real_winrate=real_winrate,
            loss_rate=loss_rate,
            net_pnl=net_pnl,
            profit_factor=profit_factor,
        )

        return OverallPerformanceSummary(
            total_days=total_days,
            total_trades=total_trades,
            tp_wins=tp_wins,
            be_trades=be_trades,
            real_losses=real_losses,
            partial_closed=partial_closed,
            be_moved=be_moved,
            closed_pnl=round(closed_pnl, 2),
            partial_pnl=round(partial_pnl, 2),
            net_pnl=round(net_pnl, 2),
            avg_net_pnl_per_trade=round(avg_net_pnl_per_trade, 2),
            avg_net_pnl_per_day=round(avg_net_pnl_per_day, 2),
            real_winrate=round(real_winrate, 2),
            be_rate=round(be_rate, 2),
            loss_rate=round(loss_rate, 2),
            profit_factor=round(profit_factor, 2) if np.isfinite(profit_factor) else float("inf"),
            expectancy=round(expectancy, 2),
            performance_state=state,
        ).to_dict()

    def _performance_state(
        self,
        total_trades: int,
        real_winrate: float,
        loss_rate: float,
        net_pnl: float,
        profit_factor: float,
    ) -> str:
        if total_trades < 30:
            if net_pnl > 0 and loss_rate == 0:
                return "PROMISING_BUT_LOW_SAMPLE"
            return "LOW_SAMPLE"

        if net_pnl > 0 and real_winrate >= 45 and loss_rate <= 30 and profit_factor >= 1.5:
            return "TARGET_PROFILE_MATCH"

        if net_pnl > 0 and loss_rate <= 25:
            return "PROTECTED_PROFITABLE"

        if net_pnl > 0:
            return "PROFITABLE_NEEDS_OPTIMIZATION"

        return "NOT_READY"