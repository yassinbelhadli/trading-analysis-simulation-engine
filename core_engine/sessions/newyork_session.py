# newyork_session.py
import pandas as pd
import numpy as np


class NewYorkSessionEngine:
    def __init__(
        self,
        newyork_start="12:00",
        newyork_end="17:00",
        newyork_open_window_minutes=30,
        london_start="07:00",
        london_end="10:00",
        asian_start="00:00",
        asian_end="06:00",
        min_range_atr_mult=0.20
    ):
        self.newyork_start = newyork_start
        self.newyork_end = newyork_end
        self.newyork_open_window_minutes = newyork_open_window_minutes

        self.london_start = london_start
        self.london_end = london_end

        self.asian_start = asian_start
        self.asian_end = asian_end

        self.min_range_atr_mult = min_range_atr_mult

    def calculate_atr(self, df: pd.DataFrame, period=14):
        high_low = df["High"] - df["Low"]
        high_close = (df["High"] - df["Close"].shift(1)).abs()
        low_close = (df["Low"] - df["Close"].shift(1)).abs()

        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return tr.ewm(alpha=1 / period, adjust=False).mean()

    def _time_to_minutes(self, value: str) -> int:
        h, m = map(int, value.split(":"))
        return h * 60 + m

    def _in_range(self, minutes: int, start: str, end: str) -> bool:
        start_m = self._time_to_minutes(start)
        end_m = self._time_to_minutes(end)

        if start_m <= end_m:
            return start_m <= minutes <= end_m

        return minutes >= start_m or minutes <= end_m

    def _safe_bool(self, row, col):
        try:
            return bool(row.get(col, False))
        except Exception:
            return False

    def process_newyork_session(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError("DataFrame index must be DatetimeIndex")

        if "ATR" not in df.columns:
            df["ATR"] = self.calculate_atr(df)

        n = len(df)

        df["NewYork_Active"] = False
        df["NewYork_Open_Window"] = False
        df["NewYork_Open_Candle"] = False

        df["NewYork_Open"] = np.nan
        df["NewYork_High"] = np.nan
        df["NewYork_Low"] = np.nan
        df["NewYork_Range"] = np.nan
        df["NewYork_Range_ATR"] = np.nan

        df["London_High_Before_NY"] = np.nan
        df["London_Low_Before_NY"] = np.nan
        df["Asian_High_Before_NY"] = np.nan
        df["Asian_Low_Before_NY"] = np.nan

        df["NewYork_Swept_London_High"] = False
        df["NewYork_Swept_London_Low"] = False
        df["NewYork_Swept_Asian_High"] = False
        df["NewYork_Swept_Asian_Low"] = False

        df["NewYork_Bias"] = None
        df["NewYork_Strength"] = 0.0
        df["NewYork_Trade_Allowed"] = False
        df["NewYork_ID"] = None

        current_date = None

        asian_high = np.nan
        asian_low = np.nan

        london_high = np.nan
        london_low = np.nan

        ny_open = np.nan
        ny_high = np.nan
        ny_low = np.nan

        ny_started = False
        ny_open_marked = False

        ny_start_m = self._time_to_minutes(self.newyork_start)
        ny_open_end_m = ny_start_m + self.newyork_open_window_minutes

        for i in range(n):
            ts = df.index[i]
            date = ts.date()
            minutes = ts.hour * 60 + ts.minute

            if date != current_date:
                current_date = date

                asian_high = np.nan
                asian_low = np.nan

                london_high = np.nan
                london_low = np.nan

                ny_open = np.nan
                ny_high = np.nan
                ny_low = np.nan

                ny_started = False
                ny_open_marked = False

            high = df["High"].iloc[i]
            low = df["Low"].iloc[i]
            open_ = df["Open"].iloc[i]
            close = df["Close"].iloc[i]
            atr = df["ATR"].iloc[i]

            in_asian = self._in_range(minutes, self.asian_start, self.asian_end)
            in_london = self._in_range(minutes, self.london_start, self.london_end)
            in_newyork = self._in_range(minutes, self.newyork_start, self.newyork_end)

            if in_asian:
                asian_high = high if pd.isna(asian_high) else max(asian_high, high)
                asian_low = low if pd.isna(asian_low) else min(asian_low, low)

            if in_london:
                london_high = high if pd.isna(london_high) else max(london_high, high)
                london_low = low if pd.isna(london_low) else min(london_low, low)

            if not in_newyork:
                continue

            if not ny_started:
                ny_started = True
                ny_open = open_
                ny_high = high
                ny_low = low
            else:
                ny_high = max(ny_high, high)
                ny_low = min(ny_low, low)

            ny_range = ny_high - ny_low
            range_atr = 0 if pd.isna(atr) or atr <= 0 else ny_range / atr

            open_window = ny_start_m <= minutes <= ny_open_end_m
            open_candle = False

            if open_window and not ny_open_marked:
                open_candle = True
                ny_open_marked = True

            swept_london_high = pd.notna(london_high) and high > london_high and close < london_high
            swept_london_low = pd.notna(london_low) and low < london_low and close > london_low

            swept_asian_high = pd.notna(asian_high) and high > asian_high and close < asian_high
            swept_asian_low = pd.notna(asian_low) and low < asian_low and close > asian_low

            bias = "NEUTRAL"

            if swept_london_low or swept_asian_low:
                bias = "BULLISH"
            elif swept_london_high or swept_asian_high:
                bias = "BEARISH"
            elif close > ny_open:
                bias = "BULLISH"
            elif close < ny_open:
                bias = "BEARISH"

            strength = 0

            if range_atr >= self.min_range_atr_mult:
                strength += 3

            if swept_london_high or swept_london_low:
                strength += 4

            if swept_asian_high or swept_asian_low:
                strength += 2

            if "Valid_Sweep" in df.columns and df["Valid_Sweep"].iloc[i] == True:
                strength += 2

            if "Liquidity_Sweep" in df.columns and df["Liquidity_Sweep"].iloc[i] == True:
                strength += 1

            if "MSS" in df.columns and df["MSS"].iloc[i] == True:
                strength += 3

            if "CHoCH" in df.columns and df["CHoCH"].iloc[i] == True:
                strength += 2

            if "BOS" in df.columns and df["BOS"].iloc[i] == True:
                strength += 1

            if "Candle_Valid_Buy" in df.columns and df["Candle_Valid_Buy"].iloc[i] == True and bias == "BULLISH":
                strength += 1

            if "Candle_Valid_Sell" in df.columns and df["Candle_Valid_Sell"].iloc[i] == True and bias == "BEARISH":
                strength += 1

            strength = min(strength, 10)

            has_setup = (
                bool(df["Confidence_Approved"].iloc[i])
                if "Confidence_Approved" in df.columns
                else False
            )

            trade_allowed = (
                in_newyork
                and bias in ["BULLISH", "BEARISH"]
                and (
                    range_atr >= self.min_range_atr_mult
                    or strength >= 2
                    or has_setup
                )
            )

            df.at[df.index[i], "NewYork_Active"] = True
            df.at[df.index[i], "NewYork_Open_Window"] = open_window
            df.at[df.index[i], "NewYork_Open_Candle"] = open_candle

            df.at[df.index[i], "NewYork_Open"] = ny_open
            df.at[df.index[i], "NewYork_High"] = ny_high
            df.at[df.index[i], "NewYork_Low"] = ny_low
            df.at[df.index[i], "NewYork_Range"] = ny_range
            df.at[df.index[i], "NewYork_Range_ATR"] = range_atr

            df.at[df.index[i], "London_High_Before_NY"] = london_high
            df.at[df.index[i], "London_Low_Before_NY"] = london_low
            df.at[df.index[i], "Asian_High_Before_NY"] = asian_high
            df.at[df.index[i], "Asian_Low_Before_NY"] = asian_low

            df.at[df.index[i], "NewYork_Swept_London_High"] = swept_london_high
            df.at[df.index[i], "NewYork_Swept_London_Low"] = swept_london_low
            df.at[df.index[i], "NewYork_Swept_Asian_High"] = swept_asian_high
            df.at[df.index[i], "NewYork_Swept_Asian_Low"] = swept_asian_low

            df.at[df.index[i], "NewYork_Bias"] = bias
            df.at[df.index[i], "NewYork_Strength"] = strength
            df.at[df.index[i], "NewYork_Trade_Allowed"] = trade_allowed
            df.at[df.index[i], "NewYork_ID"] = f"NEWYORK_{ts.strftime('%Y%m%d_%H%M')}"

        return df

    def is_newyork_active(self, df: pd.DataFrame) -> bool:
        if len(df) == 0:
            return False

        return bool(df.iloc[-1].get("NewYork_Active", False))

    def get_latest_newyork(self, df: pd.DataFrame):
        if len(df) == 0:
            return {}

        latest = df.iloc[-1]

        return {
            "active": latest.get("NewYork_Active", False),
            "bias": latest.get("NewYork_Bias", None),
            "trade_allowed": latest.get("NewYork_Trade_Allowed", False),
            "strength": latest.get("NewYork_Strength", 0),
            "range_atr": latest.get("NewYork_Range_ATR", 0),
            "swept_london_high": latest.get("NewYork_Swept_London_High", False),
            "swept_london_low": latest.get("NewYork_Swept_London_Low", False),
            "swept_asian_high": latest.get("NewYork_Swept_Asian_High", False),
            "swept_asian_low": latest.get("NewYork_Swept_Asian_Low", False),
        }