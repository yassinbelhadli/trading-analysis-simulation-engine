# daily_trade_analyzer.py
from dataclasses import dataclass, asdict
from typing import Dict, Any
import ast
import pandas as pd
import numpy as np


@dataclass
class DailyTradeSummary:
    date: str
    trades_count: int
    tp_wins: int
    be_trades: int
    real_losses: int
    partial_closed: int
    be_moved: int
    closed_pnl: float
    partial_pnl: float
    net_pnl: float
    real_winrate: float
    loss_rate: float
    trade_quality_state: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DailyTradeAnalyzer:
    def __init__(self, be_tolerance: float = 0.01):
        self.be_tolerance = be_tolerance

    def analyze(self, trades_df: pd.DataFrame) -> pd.DataFrame:
        if trades_df is None or len(trades_df) == 0:
            return pd.DataFrame()

        df = trades_df.copy()

        if "open_time" not in df.columns:
            raise ValueError("trades_df must contain open_time column")

        df["open_time"] = pd.to_datetime(df["open_time"])
        df["date"] = df["open_time"].dt.date.astype(str)

        df["pnl_money"] = pd.to_numeric(df.get("pnl_money", 0), errors="coerce").fillna(0.0)
        df["partial_pnl_calc"] = df.apply(self._extract_partial_pnl, axis=1)
        df["net_pnl_calc"] = df["pnl_money"] + df["partial_pnl_calc"]

        rows = []

        for date, group in df.groupby("date"):
            trades_count = len(group)

            tp_wins = int((group["close_reason"] == "TP_HIT").sum())

            be_trades = int(
                (
                    (group["close_reason"] == "SL_HIT")
                    & (group["net_pnl_calc"].abs() <= self.be_tolerance)
                ).sum()
            )

            real_losses = int((group["net_pnl_calc"] < -self.be_tolerance).sum())

            partial_closed = int(group.get("partial_closed", pd.Series(False, index=group.index)).fillna(False).astype(bool).sum())
            be_moved = int(group.get("be_moved", pd.Series(False, index=group.index)).fillna(False).astype(bool).sum())

            closed_pnl = float(group["pnl_money"].sum())
            partial_pnl = float(group["partial_pnl_calc"].sum())
            net_pnl = float(group["net_pnl_calc"].sum())

            real_winrate = round((tp_wins / trades_count) * 100, 2) if trades_count > 0 else 0.0
            loss_rate = round((real_losses / trades_count) * 100, 2) if trades_count > 0 else 0.0

            state = self._quality_state(trades_count, real_winrate, loss_rate, net_pnl)

            rows.append(DailyTradeSummary(
                date=date,
                trades_count=trades_count,
                tp_wins=tp_wins,
                be_trades=be_trades,
                real_losses=real_losses,
                partial_closed=partial_closed,
                be_moved=be_moved,
                closed_pnl=round(closed_pnl, 2),
                partial_pnl=round(partial_pnl, 2),
                net_pnl=round(net_pnl, 2),
                real_winrate=real_winrate,
                loss_rate=loss_rate,
                trade_quality_state=state,
            ).to_dict())

        return pd.DataFrame(rows).sort_values("date").reset_index(drop=True)

    def _extract_partial_pnl(self, row) -> float:
        metadata = row.get("metadata", {})

        if isinstance(metadata, str):
            try:
                metadata = ast.literal_eval(metadata)
            except Exception:
                metadata = {}

        if not isinstance(metadata, dict):
            return 0.0

        partial = metadata.get("partial_close", {})
        if not isinstance(partial, dict):
            return 0.0

        try:
            return float(partial.get("partial_pnl_money", 0.0))
        except Exception:
            return 0.0

    def _quality_state(self, trades_count, winrate, loss_rate, net_pnl) -> str:
        if trades_count == 0:
            return "NO_TRADES"

        if net_pnl > 0 and loss_rate == 0:
            return "EXCELLENT_PROTECTED_DAY"

        if net_pnl > 0 and winrate >= 40:
            return "GOOD_DAY"

        if net_pnl >= 0 and loss_rate <= 25:
            return "SAFE_DAY"

        if net_pnl < 0:
            return "BAD_DAY"

        return "NEUTRAL_DAY"

    def summary(self, daily_df: pd.DataFrame) -> Dict[str, Any]:
        if daily_df is None or len(daily_df) == 0:
            return {}

        total_trades = int(daily_df["trades_count"].sum())
        total_tp = int(daily_df["tp_wins"].sum())
        total_be = int(daily_df["be_trades"].sum())
        total_losses = int(daily_df["real_losses"].sum())

        return {
            "days": len(daily_df),
            "total_trades": total_trades,
            "tp_wins": total_tp,
            "be_trades": total_be,
            "real_losses": total_losses,
            "closed_pnl": round(float(daily_df["closed_pnl"].sum()), 2),
            "partial_pnl": round(float(daily_df["partial_pnl"].sum()), 2),
            "net_pnl": round(float(daily_df["net_pnl"].sum()), 2),
            "real_winrate": round((total_tp / total_trades) * 100, 2) if total_trades else 0.0,
            "loss_rate": round((total_losses / total_trades) * 100, 2) if total_trades else 0.0,
        }