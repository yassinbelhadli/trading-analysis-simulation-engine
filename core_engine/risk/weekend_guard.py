# weekend_guard.py
import pandas as pd
import numpy as np


class WeekendGuard:
    def __init__(
        self,
        friday_cutoff_hour=19,
        monday_resume_hour=10,
        block_weekend=True,
        timezone="UTC"
    ):
        self.friday_cutoff_hour = friday_cutoff_hour
        self.monday_resume_hour = monday_resume_hour
        self.block_weekend = block_weekend
        self.timezone = timezone

    def _get_block_reason(self, timestamp):
        weekday = timestamp.weekday()
        hour = timestamp.hour

        # Monday = 0
        # Tuesday = 1
        # Wednesday = 2
        # Thursday = 3
        # Friday = 4
        # Saturday = 5
        # Sunday = 6

        if weekday == 4 and hour >= self.friday_cutoff_hour:
            return "FRIDAY_CUTOFF"

        if self.block_weekend and weekday == 5:
            return "SATURDAY_BLOCK"

        if self.block_weekend and weekday == 6:
            return "SUNDAY_BLOCK"

        if weekday == 0 and hour < self.monday_resume_hour:
            return "MONDAY_PRE_OPEN_BLOCK"

        return None

    def process_weekend_guard(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError("DataFrame index must be DatetimeIndex")

        df["Weekend_Block"] = False
        df["Weekend_Block_Reason"] = None
        df["Weekend_Trade_Allowed"] = True
        df["Weekend_Guard_ID"] = None

        for i in range(len(df)):
            ts = df.index[i]
            reason = self._get_block_reason(ts)

            blocked = reason is not None

            df.at[df.index[i], "Weekend_Block"] = blocked
            df.at[df.index[i], "Weekend_Block_Reason"] = reason
            df.at[df.index[i], "Weekend_Trade_Allowed"] = not blocked
            df.at[df.index[i], "Weekend_Guard_ID"] = f"WEEKEND_{ts.strftime('%Y%m%d_%H%M')}"

        return df

    def is_trade_allowed_now(self, df: pd.DataFrame) -> bool:
        if len(df) == 0:
            return False

        latest = df.iloc[-1]
        return bool(latest.get("Weekend_Trade_Allowed", False))

    def get_latest_status(self, df: pd.DataFrame):
        if len(df) == 0:
            return {}

        latest = df.iloc[-1]

        return {
            "blocked": latest.get("Weekend_Block", False),
            "reason": latest.get("Weekend_Block_Reason", None),
            "trade_allowed": latest.get("Weekend_Trade_Allowed", False),
        }