import pandas as pd
from pathlib import Path


class DailyTradeAnalyzer:
    def __init__(self):
        pass

    def analyze(self, trades_df: pd.DataFrame) -> pd.DataFrame:
        df = trades_df.copy()

        if df.empty:
            return pd.DataFrame()

        if "open_time" not in df.columns:
            raise ValueError("Missing column: open_time")

        df["open_time"] = pd.to_datetime(df["open_time"], errors="coerce")
        df = df.dropna(subset=["open_time"])

        df["date"] = df["open_time"].dt.date

        daily = df.groupby("date").agg(
            trades_count=("trade_id", "count"),
            closed_trades=("close_time", lambda x: x.notna().sum()),
            buy_trades=("direction", lambda x: (x == "BUY").sum()),
            sell_trades=("direction", lambda x: (x == "SELL").sum()),
            total_pnl=("pnl_money", "sum"),
            avg_pnl=("pnl_money", "mean"),
            be_count=("pnl_money", lambda x: (x == 0).sum()),
            wins=("pnl_money", lambda x: (x > 0).sum()),
            losses=("pnl_money", lambda x: (x < 0).sum()),
            partial_closed=("partial_closed", lambda x: (x == True).sum()),
            be_moved=("be_moved", lambda x: (x == True).sum()),
            trailing_active=("trailing_active", lambda x: (x == True).sum()),
        ).reset_index()

        daily["winrate"] = daily.apply(
            lambda r: round((r["wins"] / r["closed_trades"]) * 100, 2)
            if r["closed_trades"] > 0 else 0,
            axis=1
        )

        daily["trade_frequency_state"] = daily["trades_count"].apply(
            self._classify_trade_frequency
        )

        return daily

    def summary(self, daily_df: pd.DataFrame) -> dict:
        if daily_df.empty:
            return {
                "total_days": 0,
                "total_trades": 0,
                "avg_trades_per_day": 0,
                "max_trades_day": 0,
                "min_trades_day": 0,
                "days_below_target": 0,
                "days_in_target": 0,
                "days_above_target": 0,
            }

        return {
            "total_days": int(len(daily_df)),
            "total_trades": int(daily_df["trades_count"].sum()),
            "avg_trades_per_day": round(daily_df["trades_count"].mean(), 2),
            "max_trades_day": int(daily_df["trades_count"].max()),
            "min_trades_day": int(daily_df["trades_count"].min()),
            "days_below_target": int((daily_df["trades_count"] < 3).sum()),
            "days_in_target": int(
                ((daily_df["trades_count"] >= 3) & (daily_df["trades_count"] <= 6)).sum()
            ),
            "days_above_target": int((daily_df["trades_count"] > 6).sum()),
            "total_pnl": round(daily_df["total_pnl"].sum(), 2),
            "avg_daily_pnl": round(daily_df["total_pnl"].mean(), 2),
        }

    def _classify_trade_frequency(self, count: int) -> str:
        if count == 0:
            return "NO_TRADES"

        if count < 3:
            return "LOW_ACTIVITY"

        if 3 <= count <= 6:
            return "TARGET_RANGE"

        return "OVERTRADING"

    def load_and_analyze(self, csv_path: str):
        path = Path(csv_path)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {csv_path}")

        trades_df = pd.read_csv(path)
        daily_df = self.analyze(trades_df)
        return daily_df, self.summary(daily_df)