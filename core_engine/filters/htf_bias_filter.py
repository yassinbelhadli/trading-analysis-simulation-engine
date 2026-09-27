# htf_bias_filter.py
import pandas as pd
import numpy as np


class HTFBiasFilter:
    def __init__(
        self,
        htf_timeframe="1h",
        swing_left=2,
        swing_right=2,
        bos_buffer_atr_mult=0.10,
        require_htf_bias=False,
        allow_neutral=True,
    ):
        self.htf_timeframe = htf_timeframe
        self.swing_left = swing_left
        self.swing_right = swing_right
        self.bos_buffer_atr_mult = bos_buffer_atr_mult
        self.require_htf_bias = require_htf_bias
        self.allow_neutral = allow_neutral

    def calculate_atr(self, df: pd.DataFrame, period=14):
        high_low = df["High"] - df["Low"]
        high_close = (df["High"] - df["Close"].shift(1)).abs()
        low_close = (df["Low"] - df["Close"].shift(1)).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return tr.ewm(alpha=1 / period, adjust=False).mean()

    def _resample_htf(self, df: pd.DataFrame) -> pd.DataFrame:
        htf = df.resample(self.htf_timeframe).agg({
            "Open": "first",
            "High": "max",
            "Low": "min",
            "Close": "last",
        }).dropna()
        htf["ATR"] = self.calculate_atr(htf)
        return htf

    def _detect_swings(self, htf: pd.DataFrame) -> pd.DataFrame:
        htf = htf.copy()
        htf["HTF_Swing_High"] = False
        htf["HTF_Swing_Low"] = False
        htf["HTF_Swing_High_Price"] = np.nan
        htf["HTF_Swing_Low_Price"] = np.nan

        highs = htf["High"].values
        lows = htf["Low"].values

        for i in range(self.swing_left, len(htf) - self.swing_right):
            high_window = highs[i - self.swing_left:i + self.swing_right + 1]
            low_window = lows[i - self.swing_left:i + self.swing_right + 1]

            if highs[i] == np.max(high_window):
                htf.at[htf.index[i], "HTF_Swing_High"] = True
                htf.at[htf.index[i], "HTF_Swing_High_Price"] = highs[i]

            if lows[i] == np.min(low_window):
                htf.at[htf.index[i], "HTF_Swing_Low"] = True
                htf.at[htf.index[i], "HTF_Swing_Low_Price"] = lows[i]

        return htf

    def _process_htf_bias(self, htf: pd.DataFrame) -> pd.DataFrame:
        htf = htf.copy()

        htf["HTF_BOS_Bullish"] = False
        htf["HTF_BOS_Bearish"] = False
        htf["HTF_Bias"] = "NEUTRAL"
        htf["HTF_Trend"] = "NEUTRAL"
        htf["HTF_Last_Swing_High"] = np.nan
        htf["HTF_Last_Swing_Low"] = np.nan
        htf["HTF_Bias_Reason"] = "NO_STRUCTURE"

        last_swing_high = np.nan
        last_swing_low = np.nan
        current_bias = "NEUTRAL"

        for i in range(len(htf)):
            close = htf["Close"].iloc[i]
            atr = htf["ATR"].iloc[i]
            buffer = atr * self.bos_buffer_atr_mult if pd.notna(atr) and atr > 0 else 0

            if bool(htf["HTF_Swing_High"].iloc[i]):
                last_swing_high = htf["HTF_Swing_High_Price"].iloc[i]

            if bool(htf["HTF_Swing_Low"].iloc[i]):
                last_swing_low = htf["HTF_Swing_Low_Price"].iloc[i]

            bullish_bos = pd.notna(last_swing_high) and close > last_swing_high + buffer
            bearish_bos = pd.notna(last_swing_low) and close < last_swing_low - buffer

            if bullish_bos:
                current_bias = "BULLISH"
                htf.at[htf.index[i], "HTF_BOS_Bullish"] = True
                htf.at[htf.index[i], "HTF_Bias_Reason"] = "BULLISH_BOS"
            elif bearish_bos:
                current_bias = "BEARISH"
                htf.at[htf.index[i], "HTF_BOS_Bearish"] = True
                htf.at[htf.index[i], "HTF_Bias_Reason"] = "BEARISH_BOS"
            else:
                htf.at[htf.index[i], "HTF_Bias_Reason"] = "CARRY_FORWARD"

            htf.at[htf.index[i], "HTF_Bias"] = current_bias
            htf.at[htf.index[i], "HTF_Trend"] = current_bias
            htf.at[htf.index[i], "HTF_Last_Swing_High"] = last_swing_high
            htf.at[htf.index[i], "HTF_Last_Swing_Low"] = last_swing_low

        return htf

    def process_htf_bias(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError("DataFrame index must be DatetimeIndex")

        old_cols = [
            "HTF_Bias", "HTF_Trend", "HTF_BOS_Bullish", "HTF_BOS_Bearish",
            "HTF_Last_Swing_High", "HTF_Last_Swing_Low", "HTF_Bias_Reason",
            "HTF_Bias_Allowed", "HTF_Bias_Block_Reason",
        ]
        df = df.drop(columns=[c for c in old_cols if c in df.columns], errors="ignore")

        htf = self._resample_htf(df)
        htf = self._detect_swings(htf)
        htf = self._process_htf_bias(htf)

        merge_cols = [
            "HTF_Bias", "HTF_Trend", "HTF_BOS_Bullish", "HTF_BOS_Bearish",
            "HTF_Last_Swing_High", "HTF_Last_Swing_Low", "HTF_Bias_Reason",
        ]

        df = pd.merge_asof(
            df.sort_index(),
            htf[merge_cols].sort_index(),
            left_index=True,
            right_index=True,
            direction="backward"
        )

        df["HTF_Bias"] = df["HTF_Bias"].fillna("NEUTRAL")
        df["HTF_Trend"] = df["HTF_Trend"].fillna("NEUTRAL")
        df["HTF_Bias_Reason"] = df["HTF_Bias_Reason"].fillna("NO_HTF_DATA")

        df["HTF_Bias_Allowed"] = True
        df["HTF_Bias_Block_Reason"] = "OK"

        for i in range(len(df)):
            direction = df["Trade_Direction"].iloc[i] if "Trade_Direction" in df.columns else None
            bias = df["HTF_Bias"].iloc[i]

            if not self.require_htf_bias:
                continue

            if bias == "NEUTRAL":
                if self.allow_neutral:
                    continue
                df.at[df.index[i], "HTF_Bias_Allowed"] = False
                df.at[df.index[i], "HTF_Bias_Block_Reason"] = "HTF_NEUTRAL"
                continue

            if direction == "BUY" and bias != "BULLISH":
                df.at[df.index[i], "HTF_Bias_Allowed"] = False
                df.at[df.index[i], "HTF_Bias_Block_Reason"] = "BUY_BLOCKED_BY_HTF_BEARISH"

            elif direction == "SELL" and bias != "BEARISH":
                df.at[df.index[i], "HTF_Bias_Allowed"] = False
                df.at[df.index[i], "HTF_Bias_Block_Reason"] = "SELL_BLOCKED_BY_HTF_BULLISH"

        return df

    def get_latest_bias(self, df: pd.DataFrame):
        if len(df) == 0 or "HTF_Bias" not in df.columns:
            return {
                "bias": "UNKNOWN",
                "trend": "UNKNOWN",
                "allowed": False,
                "reason": "NO_HTF_DATA",
            }

        latest = df.iloc[-1]

        return {
            "bias": latest.get("HTF_Bias", "UNKNOWN"),
            "trend": latest.get("HTF_Trend", "UNKNOWN"),
            "allowed": latest.get("HTF_Bias_Allowed", False),
            "reason": latest.get("HTF_Bias_Block_Reason", None),
            "last_swing_high": latest.get("HTF_Last_Swing_High", np.nan),
            "last_swing_low": latest.get("HTF_Last_Swing_Low", np.nan),
        }
