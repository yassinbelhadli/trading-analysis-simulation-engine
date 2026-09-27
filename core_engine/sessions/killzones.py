# killzones.py
import pandas as pd
import numpy as np


class KillzoneEngine:
    def __init__(
        self,
        asian_start="00:00",
        asian_end="06:00",
        london_start="07:00",
        london_end="10:00",
        newyork_start="12:00",
        newyork_end="15:00",
        london_close_start="15:00",
        london_close_end="17:00",
        timezone="UTC",
        min_volatility_atr_mult=0.40
    ):
        self.asian_start = asian_start
        self.asian_end = asian_end

        self.london_start = london_start
        self.london_end = london_end

        self.newyork_start = newyork_start
        self.newyork_end = newyork_end

        self.london_close_start = london_close_start
        self.london_close_end = london_close_end

        self.timezone = timezone
        self.min_volatility_atr_mult = min_volatility_atr_mult

    def calculate_atr(self, df: pd.DataFrame, period=14):
        high_low = df["High"] - df["Low"]
        high_close = (df["High"] - df["Close"].shift(1)).abs()
        low_close = (df["Low"] - df["Close"].shift(1)).abs()

        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return tr.ewm(alpha=1 / period, adjust=False).mean()

    def _time_to_minutes(self, t):
        h, m = map(int, t.split(":"))
        return h * 60 + m

    def _in_time_range(self, current_minutes, start, end):
        start_m = self._time_to_minutes(start)
        end_m = self._time_to_minutes(end)

        if start_m <= end_m:
            return start_m <= current_minutes <= end_m

        return current_minutes >= start_m or current_minutes <= end_m

    def _session_name(self, minutes):
        if self._in_time_range(minutes, self.asian_start, self.asian_end):
            return "ASIAN"

        if self._in_time_range(minutes, self.london_start, self.london_end):
            return "LONDON_KILLZONE"

        if self._in_time_range(minutes, self.newyork_start, self.newyork_end):
            return "NEWYORK_KILLZONE"

        if self._in_time_range(minutes, self.london_close_start, self.london_close_end):
            return "LONDON_CLOSE"

        return "OTHER"

    def process_killzones(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError("DataFrame index must be DatetimeIndex")

        if "ATR" not in df.columns:
            df["ATR"] = self.calculate_atr(df)

        n = len(df)

        df["Session_Name"] = None
        df["Killzone"] = None

        df["In_Killzone"] = False
        df["Asian_Session"] = False
        df["London_Killzone"] = False
        df["NewYork_Killzone"] = False
        df["London_Close"] = False

        df["Session_Open"] = np.nan
        df["Session_High"] = np.nan
        df["Session_Low"] = np.nan
        df["Session_Range"] = np.nan
        df["Session_Range_ATR"] = np.nan

        df["Session_Volatility_OK"] = False
        df["Session_Strength"] = 0.0

        df["Best_Trading_Window"] = False
        df["Session_Trade_Allowed"] = False
        df["Session_ID"] = None

        current_session = None
        session_open = np.nan
        session_high = np.nan
        session_low = np.nan

        for i in range(n):
            ts = df.index[i]
            minutes = ts.hour * 60 + ts.minute

            session = self._session_name(minutes)

            if session != current_session:
                current_session = session
                session_open = df["Open"].iloc[i]
                session_high = df["High"].iloc[i]
                session_low = df["Low"].iloc[i]
            else:
                session_high = max(session_high, df["High"].iloc[i])
                session_low = min(session_low, df["Low"].iloc[i])

            session_range = session_high - session_low
            atr = df["ATR"].iloc[i]

            if pd.isna(atr) or atr <= 0:
                range_atr = 0
            else:
                range_atr = session_range / atr

            volatility_ok = range_atr >= self.min_volatility_atr_mult

            strength = 0

            if session in ["LONDON_KILLZONE", "NEWYORK_KILLZONE"]:
                strength += 4

            if session == "LONDON_CLOSE":
                strength += 2

            if volatility_ok:
                strength += 3

            if "Liquidity_Sweep" in df.columns and df["Liquidity_Sweep"].iloc[i] == True:
                strength += 2

            if "Valid_Sweep" in df.columns and df["Valid_Sweep"].iloc[i] == True:
                strength += 3

            if "MSS" in df.columns and df["MSS"].iloc[i] == True:
                strength += 3

            if "CHoCH" in df.columns and df["CHoCH"].iloc[i] == True:
                strength += 2

            strength = min(strength, 10)

            in_killzone = session in ["LONDON_KILLZONE", "NEWYORK_KILLZONE"]

            best_window = (
                session in ["LONDON_KILLZONE", "NEWYORK_KILLZONE"]
                and volatility_ok
            )

            trade_allowed = (
                in_killzone
                and volatility_ok
            )

            df.at[df.index[i], "Session_Name"] = session
            df.at[df.index[i], "Killzone"] = session if in_killzone else None

            df.at[df.index[i], "Asian_Session"] = session == "ASIAN"
            df.at[df.index[i], "London_Killzone"] = session == "LONDON_KILLZONE"
            df.at[df.index[i], "NewYork_Killzone"] = session == "NEWYORK_KILLZONE"
            df.at[df.index[i], "London_Close"] = session == "LONDON_CLOSE"

            df.at[df.index[i], "In_Killzone"] = in_killzone
            df.at[df.index[i], "Session_Open"] = session_open
            df.at[df.index[i], "Session_High"] = session_high
            df.at[df.index[i], "Session_Low"] = session_low
            df.at[df.index[i], "Session_Range"] = session_range
            df.at[df.index[i], "Session_Range_ATR"] = range_atr
            df.at[df.index[i], "Session_Volatility_OK"] = volatility_ok
            df.at[df.index[i], "Session_Strength"] = strength
            df.at[df.index[i], "Best_Trading_Window"] = best_window
            df.at[df.index[i], "Session_Trade_Allowed"] = trade_allowed
            df.at[df.index[i], "Session_ID"] = f"SESSION_{ts.strftime('%Y%m%d_%H%M')}"

        return df

    def is_trade_allowed_now(self, df: pd.DataFrame):
        if len(df) == 0:
            return False

        latest = df.iloc[-1]

        return bool(latest.get("Session_Trade_Allowed", False))

    def get_latest_session(self, df: pd.DataFrame):
        if len(df) == 0:
            return {}

        latest = df.iloc[-1]

        return {
            "session": latest.get("Session_Name", None),
            "killzone": latest.get("Killzone", None),
            "in_killzone": latest.get("In_Killzone", False),
            "trade_allowed": latest.get("Session_Trade_Allowed", False),
            "strength": latest.get("Session_Strength", 0),
            "range_atr": latest.get("Session_Range_ATR", 0),
        }